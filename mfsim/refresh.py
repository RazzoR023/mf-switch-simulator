"""Download the upstream fund list and NAV history and rebuild the SQLite database.

    python -m mfsim.refresh            # skips the rebuild if both upstream files are unchanged
    python -m mfsim.refresh --force    # rebuild anyway

The database is built next to the live one and swapped in with an atomic rename, so the
server never sees a half-built file and a failed run leaves the previous data in place.
This is the only part of the app that needs pyarrow. It runs as its own short-lived
process so the ~350 MB it peaks at while converting is handed back to the OS afterwards.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import io
import logging
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config

log = logging.getLogger("mfsim.refresh")

EPOCH = date(1970, 1, 1)

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
-- day = days since 1970-01-01. WITHOUT ROWID clusters the rows by (code, day), so one
-- scheme's whole history is a single contiguous range read.
CREATE TABLE nav (
    code INTEGER NOT NULL,
    day  INTEGER NOT NULL,
    nav  REAL    NOT NULL,
    PRIMARY KEY (code, day)
) WITHOUT ROWID;
CREATE TABLE funds (
    code            INTEGER PRIMARY KEY,
    name            TEXT,
    nav_name        TEXT,
    amc             TEXT,
    category        TEXT,
    launch_date     TEXT,
    latest_nav_date TEXT,
    nav_start       INTEGER,
    nav_end         INTEGER,
    nav_count       INTEGER,
    last_nav        REAL
);
-- One row per (ISIN column, CSV row). Lookups take the lowest col_rank, then row_rank,
-- which is the order the old pandas code scanned the columns and rows in. Clustered on
-- that key, so an ISIN lookup is one B-tree descent that already holds the code.
CREATE TABLE isins (
    isin     TEXT    NOT NULL,
    col_rank INTEGER NOT NULL,
    row_rank INTEGER NOT NULL,
    code     INTEGER NOT NULL,
    PRIMARY KEY (isin, col_rank, row_rank)
) WITHOUT ROWID;
-- Fund search matches every query word as a substring anywhere in the name, which a
-- B-tree can't serve (LIKE '%word%' scans every row). A trigram index can, for words of
-- 3+ characters. External content: it indexes funds' columns without storing a copy.
CREATE VIRTUAL TABLE funds_fts USING fts5 (
    name, nav_name, content = 'funds', content_rowid = 'code', tokenize = 'trigram'
);
"""

INDEXES = """
INSERT INTO funds_fts (funds_fts) VALUES ('rebuild');
-- Search results come back sorted by name and only funds with NAV history are offered,
-- so this is the order (and the subset) a LIMIT-ed search reads in.
CREATE INDEX funds_by_name ON funds (name, nav_name, code) WHERE nav_count > 0;
-- Planner statistics, so SQLite picks these indexes over scans.
ANALYZE;
"""

# A rebuild that produces less than this is treated as a broken upstream file, and the
# previous database is kept.
MIN_NAV_ROWS = 1_000_000
MIN_FUNDS_WITH_NAV = 1_000


# ─── Column matching ─────────────────────────────────────────────────────────
# The upstream schema isn't stable, so columns are matched fuzzily, first match wins.

def _norm(name: str) -> str:
    """Lowercase + collapse spaces/dashes/dots to underscores for fuzzy matching."""
    return name.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def _match_fund_columns(columns: list[str]) -> tuple[dict[str, str], list[str]]:
    """Map CSV columns to our names. Returns (target -> source column, ISIN columns)."""
    found: dict[str, str] = {}

    def claim(target: str, src: str) -> None:
        found.setdefault(target, src)

    for c in columns:
        lc = _norm(c)
        if ("scheme" in lc and "code" in lc) or lc in ("code", "schemecode"):
            claim("scheme_code", c)
        elif "scheme" in lc and "nav" in lc and "name" in lc:
            claim("nav_name", c)
        elif "scheme" in lc and "name" in lc:
            claim("scheme_name", c)
        elif lc == "amc" or "amc" in lc:
            claim("amc", c)
        elif "category" in lc:
            claim("category", c)
        elif "latest" in lc and "nav" in lc and "date" in lc:
            claim("latest_nav_date", c)
        elif "launch" in lc:
            claim("launch_date", c)
    isin_cols = [c for c in columns if "isin" in c.lower()]
    return found, isin_cols


def _match_nav_columns(columns: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for c in columns:
        lc = _norm(c)
        if ("scheme" in lc and "code" in lc) or lc in ("code", "schemecode"):
            found.setdefault("scheme_code", c)
        elif "date" in lc:
            found.setdefault("date", c)
        elif lc == "nav" or lc.endswith("_nav") or lc.startswith("nav_") or "net_asset" in lc:
            found.setdefault("nav", c)
    return found


# ─── Value parsing ───────────────────────────────────────────────────────────

def _to_int(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_iso_date(value: str) -> str | None:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


# ─── Download ────────────────────────────────────────────────────────────────

def _download(url: str, dest: Path, known_etag: str | None) -> str | None:
    """Stream url to dest. Returns the response's ETag, or None (and writes nothing) when
    it matches known_etag."""
    req = urllib.request.Request(url, headers={"User-Agent": "mfsim-refresh"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        etag = resp.headers.get("ETag")
        if known_etag and etag == known_etag:
            log.info("%s unchanged (ETag %s)", dest.name, etag)
            return None
        total = int(resp.headers.get("Content-Length") or 0)
        done, next_report, start = 0, 25 << 20, time.monotonic()
        with open(dest, "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if done >= next_report:
                    log.info("  %s: %d / %d MB", dest.name, done >> 20, total >> 20)
                    next_report += 25 << 20
        log.info("%s downloaded: %.1f MB in %.0fs", dest.name, done / 1e6, time.monotonic() - start)
        return etag or ""


# ─── Build ───────────────────────────────────────────────────────────────────

def _load_funds(con: sqlite3.Connection, csv_path: Path) -> str | None:
    """Fill funds and isins from the fund list CSV. Returns the latest NAV date in it."""
    raw = csv_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    columns = [c.strip() for c in (reader.fieldnames or [])]
    reader.fieldnames = columns
    cols, isin_cols = _match_fund_columns(columns)
    if "scheme_code" not in cols:
        raise RuntimeError(f"fund list has no scheme code column; columns: {columns}")

    def get(row: dict, target: str) -> str | None:
        return _clean(row.get(cols[target])) if target in cols else None

    latest = None
    funds, isins = [], []
    for row_rank, row in enumerate(reader):
        code = _to_int(row.get(cols["scheme_code"]))
        if code is None:
            continue
        latest_nav_date = _to_iso_date(get(row, "latest_nav_date") or "")
        if latest_nav_date and (latest is None or latest_nav_date > latest):
            latest = latest_nav_date
        funds.append((
            code,
            get(row, "scheme_name"),
            get(row, "nav_name"),
            get(row, "amc"),
            get(row, "category"),
            _to_iso_date(get(row, "launch_date") or ""),
            latest_nav_date,
        ))
        for col_rank, col in enumerate(isin_cols):
            isin = (row.get(col) or "").strip().upper()
            if isin and isin not in ("-", "NAN"):
                isins.append((isin, col_rank, row_rank, code))

    # A scheme code listed twice keeps its first row, like the old fund_df lookups did.
    con.executemany(
        "INSERT OR IGNORE INTO funds (code, name, nav_name, amc, category, launch_date,"
        " latest_nav_date) VALUES (?,?,?,?,?,?,?)",
        funds,
    )
    con.executemany("INSERT INTO isins VALUES (?,?,?,?)", isins)
    log.info("fund list: %d schemes, %d ISINs, latest NAV date %s", len(funds), len(isins), latest)
    return latest


def _load_nav(con: sqlite3.Connection, parquet_path: Path) -> int:
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(parquet_path)
    cols = _match_nav_columns(pf.schema_arrow.names)
    missing = {"scheme_code", "date", "nav"} - set(cols)
    if missing:
        raise RuntimeError(
            f"NAV parquet is missing {sorted(missing)}; columns: {pf.schema_arrow.names}"
        )

    def ints(arr):
        try:
            return pc.cast(arr, pa.int64(), safe=False).to_pylist()
        except (pa.ArrowInvalid, pa.ArrowNotImplementedError):
            return [_to_int(v) for v in arr.to_pylist()]

    def floats(arr):
        try:
            return pc.cast(arr, pa.float64(), safe=False).to_pylist()
        except (pa.ArrowInvalid, pa.ArrowNotImplementedError):
            out = []
            for v in arr.to_pylist():
                try:
                    out.append(float(v))
                except (TypeError, ValueError):
                    out.append(None)
            return out

    def days(arr):
        if pa.types.is_timestamp(arr.type) or pa.types.is_date(arr.type):
            return pc.cast(pc.cast(arr, pa.date32(), safe=False), pa.int32()).to_pylist()
        # Strings: day-first, as the old loader parsed them.
        out = []
        for v in arr.to_pylist():
            iso = _to_iso_date(str(v)) if v is not None else None
            out.append((date.fromisoformat(iso) - EPOCH).days if iso else None)
        return out

    rows = 0
    start = time.monotonic()
    names = [cols["scheme_code"], cols["date"], cols["nav"]]
    for i, batch in enumerate(pf.iter_batches(batch_size=250_000, columns=names)):
        codes, dys, navs = ints(batch.column(0)), days(batch.column(1)), floats(batch.column(2))
        # NaN != NaN drops unparseable NAVs; a NAV of 0 is kept, as before.
        good = [
            (c, d, n)
            for c, d, n in zip(codes, dys, navs)
            if c is not None and d is not None and n is not None and n == n
        ]
        # A (scheme, date) seen twice keeps the later row.
        con.executemany("INSERT OR REPLACE INTO nav VALUES (?,?,?)", good)
        rows += len(good)
        if i % 20 == 19:
            log.info("  NAV rows: %d (%.0fs)", rows, time.monotonic() - start)
    log.info("NAV history: %d rows in %.0fs", rows, time.monotonic() - start)
    return rows


def build(csv_path: Path, parquet_path: Path, out_path: Path, meta: dict[str, str]) -> dict:
    if out_path.exists():
        out_path.unlink()
    con = sqlite3.connect(out_path)
    try:
        con.executescript(
            "PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA cache_size=-32768;"
        )
        con.executescript(SCHEMA)
        latest = _load_funds(con, csv_path)
        nav_rows = _load_nav(con, parquet_path)

        log.info("indexing")
        con.execute(
            """
            UPDATE funds SET
                nav_start = r.s, nav_end = r.e, nav_count = r.n,
                last_nav  = (SELECT nav FROM nav WHERE nav.code = funds.code AND nav.day = r.e)
            FROM (SELECT code, MIN(day) AS s, MAX(day) AS e, COUNT(*) AS n
                  FROM nav GROUP BY code) AS r
            WHERE r.code = funds.code
            """
        )
        con.executescript(INDEXES)
        funds_with_nav = con.execute(
            "SELECT COUNT(*) FROM funds WHERE nav_count > 0"
        ).fetchone()[0]
        nav_max_day = con.execute("SELECT MAX(day) FROM nav").fetchone()[0]

        if nav_rows < MIN_NAV_ROWS or funds_with_nav < MIN_FUNDS_WITH_NAV:
            raise RuntimeError(
                f"only {nav_rows} NAV rows / {funds_with_nav} funds with NAV - upstream "
                "file looks broken, keeping the previous database"
            )

        stats = {
            **meta,
            "refreshed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "latest_nav_date": latest or "",
            "nav_max_date": (EPOCH + timedelta(days=nav_max_day)).isoformat()
            if nav_max_day is not None else "",
            "nav_rows": str(nav_rows),
            "funds_with_nav": str(funds_with_nav),
        }
        con.executemany("INSERT INTO meta VALUES (?, ?)", stats.items())
        con.commit()
        log.info("compacting")
        con.execute("VACUUM")
    finally:
        con.close()
    return stats


def read_meta(db_path: Path) -> dict[str, str]:
    if not db_path.exists():
        return {}
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            return dict(con.execute("SELECT key, value FROM meta"))
        finally:
            con.close()
    except sqlite3.Error:
        return {}


def refresh(force: bool = False) -> bool:
    """Returns True if a new database was swapped in."""
    data_dir = config.DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    old = {} if force else read_meta(config.DB_PATH)

    csv_path = data_dir / ".fund_list.csv.part"
    parquet_path = data_dir / ".nav_history.parquet.part"
    new_db = data_dir / "mfsim.sqlite.new"
    try:
        csv_etag = _download(config.CSV_URL, csv_path, old.get("csv_etag"))
        parquet_etag = _download(config.PARQUET_URL, parquet_path, old.get("parquet_etag"))
        if csv_etag is None and parquet_etag is None:
            log.info("both upstream files unchanged; nothing to do")
            return False
        # One of the two changed: fetch whichever was skipped, the rebuild needs both.
        if csv_etag is None:
            csv_etag = _download(config.CSV_URL, csv_path, None)
        if parquet_etag is None:
            parquet_etag = _download(config.PARQUET_URL, parquet_path, None)

        stats = build(
            csv_path, parquet_path, new_db,
            {"csv_etag": csv_etag or "", "parquet_etag": parquet_etag or ""},
        )
        os.replace(new_db, config.DB_PATH)
        log.info(
            "database updated: %s funds with NAV, %s rows, latest NAV %s, %.0f MB",
            stats["funds_with_nav"], stats["nav_rows"], stats["nav_max_date"],
            config.DB_PATH.stat().st_size / 1e6,
        )
        return True
    finally:
        for p in (csv_path, parquet_path, new_db):
            p.unlink(missing_ok=True)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
    )
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="rebuild even if upstream is unchanged")
    args = parser.parse_args()

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.DATA_DIR / ".refresh.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.warning("another refresh is already running")
            return 0
        try:
            refresh(force=args.force)
        except Exception:
            log.exception("refresh failed; the previous database (if any) is still in use")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
