"""Keep data/mfsim.sqlite current with AMFI's NAV history.

    python -m mfsim.refresh            # top up from new or changed day files (the daily run)
    python -m mfsim.refresh --full     # rebuild from the full release

Source: https://github.com/captn3m0/historical-mf-data, which archives AMFI's daily NAV
export as data/YYYY/MM/DD.csv and publishes all of it every day as one SQLite release asset
(funds.db.zst).

- **Full build** (no database yet, every FULL_REBUILD_DAYS, or --full): download the release
  (~380 MB, 1.2 GB unpacked), copy it into our schema in a new file next to the live one,
  apply the last week of day files, and swap it in with an atomic rename. A failed build
  leaves the previous database in place. ~4 minutes, under 100 MB of RAM.
- **Top-up** (every other run): list the last TOPUP_MONTHS month folders through the GitHub
  API, download only the day files whose git SHA changed since last time (usually one or
  two, ~1.2 MB each), and apply them to the live database in one transaction. The server
  only reads, and the write lock lasts milliseconds.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config

log = logging.getLogger("mfsim.refresh")

EPOCH = date(1970, 1, 1)
# Bump when the schema changes: a database built by an older version gets a full rebuild.
SCHEMA_VERSION = "2"

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
-- name is AMFI's plan-level name ("... - Direct Plan - Growth"). nav_name is kept for the
-- API's shape but AMFI's data has no separate scheme name, so it stays NULL. amc and
-- category come from the day files' section headers, so schemes that closed before the
-- top-up window have none.
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
-- col_rank 0 = growth / IDCW payout ISIN, 1 = IDCW reinvestment ISIN. Clustered on the key,
-- so an ISIN lookup is one B-tree descent that already holds the code.
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
-- Day files already applied, by repo path, with the git blob SHA they had.
CREATE TABLE day_files (path TEXT PRIMARY KEY, sha TEXT NOT NULL);
"""

INDEXES = """
INSERT INTO funds_fts (funds_fts) VALUES ('rebuild');
-- Search results come back sorted by name and only funds with NAV history are offered,
-- so this is the order (and the subset) a LIMIT-ed search reads in.
CREATE INDEX funds_by_name ON funds (name, nav_name, code) WHERE nav_count > 0;
-- Planner statistics, so SQLite picks these indexes over scans.
ANALYZE;
"""

# A build that produces less than this is treated as a broken upstream file, and the
# previous database is kept.
MIN_NAV_ROWS = 1_000_000
MIN_FUNDS_WITH_NAV = 1_000

DOWNLOAD_ATTEMPTS = 4
# Per connection attempt and per read. GitHub answers from several addresses and one of
# them can be unreachable from a given network; urllib tries the addresses in turn, each
# with the full timeout, so a long one turns a 1 s request into minutes.
DOWNLOAD_TIMEOUT = 15


# ─── HTTP ────────────────────────────────────────────────────────────────────

def _request(url: str, api: bool = False) -> urllib.request.Request:
    headers = {"User-Agent": "mfsim-refresh"}
    if api:
        headers["Accept"] = "application/vnd.github+json"
        if config.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return urllib.request.Request(url, headers=headers)


def _retrying(what: str, fn):
    """Run fn, retrying network errors with backoff. A 404 is returned as None."""
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == DOWNLOAD_ATTEMPTS or e.code not in (403, 429, 500, 502, 503, 504):
                raise
            err = e
        except OSError as e:  # URLError, timeouts and connection resets are all OSErrors
            if attempt == DOWNLOAD_ATTEMPTS:
                raise
            err = e
        wait = 15 * attempt
        log.warning("%s: %s; retrying in %ds", what, err, wait)
        time.sleep(wait)


def _get_json(path: str):
    def go():
        with urllib.request.urlopen(_request(config.GITHUB_API + path, api=True),
                                    timeout=DOWNLOAD_TIMEOUT) as r:
            return json.load(r)
    return _retrying(path, go)


def _get_bytes(url: str) -> bytes | None:
    def go():
        with urllib.request.urlopen(_request(url), timeout=DOWNLOAD_TIMEOUT) as r:
            return r.read()
    return _retrying(url, go)


def _download(url: str, dest: Path) -> None:
    def go():
        with urllib.request.urlopen(_request(url), timeout=DOWNLOAD_TIMEOUT) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done, next_report, start = 0, 50 << 20, time.monotonic()
            with open(dest, "wb") as f:
                while chunk := resp.read(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if done >= next_report:
                        log.info("  %s: %d / %d MB", dest.name, done >> 20, total >> 20)
                        next_report += 50 << 20
            log.info("%s downloaded: %.0f MB in %.0fs", dest.name, done / 1e6,
                     time.monotonic() - start)
    _retrying(dest.name, go)


# ─── Day files ───────────────────────────────────────────────────────────────

CATEGORY_RE = re.compile(r"^\s*\w[\w\s-]*Schemes?\s*\(\s*(.*?)\s*\)\s*$", re.IGNORECASE)
BAD_NAVS = {"-", "#N/A", "#DIV/0!", "N.A.", "NA", "B.C.", "B. C."}


def clean_isin(isin: str) -> str | None:
    """Fix the common typos in AMFI's ISINs, as the upstream release does; None if it
    still isn't one."""
    isin = isin.strip().upper()
    if isin.startswith("IIN"):
        isin = isin[1:]
    if isin.startswith("NF"):
        isin = "I" + isin
    if isin.startswith("IN9"):
        isin = "INF9" + isin[3:]
    return isin if isin.startswith("INF") and len(isin) == 12 else None


def clean_nav(value: str) -> float | None:
    value = value.strip()
    if value in BAD_NAVS:
        return None
    try:
        nav = float(value.replace(",", "").replace("`", "").replace("-", ""))
    except ValueError:
        return None
    return nav or None


def parse_day_file(text: str, fallback: date) -> tuple[list, dict, list]:
    """One AMFI NAV export. Returns (nav rows (code, day, nav), schemes {code: (name, amc,
    category)}, isins [(isin, col_rank, code)]). Rows are grouped under section lines: a
    category ("Open Ended Schemes ( Equity Scheme - Multi Cap Fund )") then the AMC."""
    lines = text.splitlines()
    try:
        header_at = next(i for i, l in enumerate(lines) if l.startswith("Scheme Code"))
    except StopIteration:
        return [], {}, []
    header = [h.strip() for h in lines[header_at].split(";")]

    def col(*names):
        return next((header.index(n) for n in names if n in header), None)

    i_code, i_name = col("Scheme Code"), col("NAV Name", "Scheme Name")
    i_isin, i_reinv = col("ISIN Div Payout/ISIN Growth"), col("ISIN Div Reinvestment")
    i_nav, i_date = col("Net Asset Value"), col("Date")
    if i_code is None or i_nav is None:
        return [], {}, []

    rows, schemes, isins = [], {}, []
    category = amc = None
    for line in lines[header_at + 1:]:
        if not line.strip():
            continue
        if ";" not in line:
            m = CATEGORY_RE.match(line)
            if m:
                category, amc = m.group(1), None
            else:
                amc = line.strip()
            continue
        f = [x.strip() for x in line.split(";")]
        try:
            code = int(f[i_code])
        except (ValueError, IndexError):
            continue
        if i_name is not None and i_name < len(f) and f[i_name]:
            schemes[code] = (f[i_name], amc, category)
        for rank, i in ((0, i_isin), (1, i_reinv)):
            isin = clean_isin(f[i]) if i is not None and i < len(f) else None
            if isin:
                isins.append((isin, rank, code))
        nav = clean_nav(f[i_nav]) if i_nav < len(f) else None
        if nav is None:
            continue
        d = fallback
        if i_date is not None and i_date < len(f):
            try:
                d = datetime.strptime(f[i_date], "%d-%b-%Y").date()
            except ValueError:
                pass
        rows.append((code, (d - EPOCH).days, nav))
    return rows, schemes, isins


def _list_day_files(months: int) -> list[dict]:
    """Day files in the last `months` month folders, oldest first: {path, sha, date}."""
    today = date.today()
    out = []
    for back in range(months - 1, -1, -1):
        y, m = divmod(today.year * 12 + today.month - 1 - back, 12)
        path = f"data/{y:04d}/{m + 1:02d}"
        for entry in _get_json(f"/repos/{config.NAV_REPO}/contents/{path}") or []:
            name = entry.get("name", "")
            if entry.get("type") == "file" and re.fullmatch(r"\d{2}\.csv", name):
                out.append({"path": entry["path"], "sha": entry["sha"],
                            "date": date(y, m + 1, int(name[:2]))})
    return sorted(out, key=lambda e: e["path"])


def _apply_day_files(con: sqlite3.Connection, files: list[dict]) -> set[int]:
    """Download and upsert the given day files, oldest first so newer names win. Returns
    the scheme codes touched."""
    touched: set[int] = set()
    for e in files:
        raw = _get_bytes(f"https://raw.githubusercontent.com/{config.NAV_REPO}/main/{e['path']}")
        if raw is None:
            continue
        rows, schemes, isins = parse_day_file(raw.decode("utf-8", "replace"), e["date"])
        con.executemany("INSERT OR REPLACE INTO nav VALUES (?,?,?)", rows)
        con.executemany(
            "INSERT INTO funds (code, name, amc, category) VALUES (?,?,?,?)"
            " ON CONFLICT (code) DO UPDATE SET name = excluded.name,"
            " amc = coalesce(excluded.amc, amc), category = coalesce(excluded.category, category)",
            [(c, n, a, k) for c, (n, a, k) in schemes.items()],
        )
        con.executemany("INSERT OR REPLACE INTO isins VALUES (?,?,0,?)", isins)
        con.execute("INSERT OR REPLACE INTO day_files VALUES (?,?)", (e["path"], e["sha"]))
        touched.update(c for c, _, _ in rows)
        touched.update(schemes)
        log.info("  %s: %d NAVs, %d schemes", e["path"], len(rows), len(schemes))
    return touched


# ─── Shared finishing steps ──────────────────────────────────────────────────

def _update_fund_stats(con: sqlite3.Connection, codes: set[int] | None = None) -> None:
    """Recompute each fund's NAV range, count and last NAV (all funds, or just `codes`)."""
    con.execute("CREATE TEMP TABLE IF NOT EXISTS touched (code INTEGER PRIMARY KEY)")
    con.execute("DELETE FROM temp.touched")
    where = ""
    if codes is not None:
        con.executemany("INSERT OR IGNORE INTO temp.touched VALUES (?)", ((c,) for c in codes))
        where = "WHERE code IN (SELECT code FROM temp.touched)"
    # Schemes with NAVs but no name anywhere still need a row to be searchable by code.
    con.execute(f"INSERT OR IGNORE INTO funds (code, name) SELECT DISTINCT code, 'Scheme ' || code FROM nav {where}")
    con.execute(f"""
        UPDATE funds SET
            nav_start = r.s, nav_end = r.e, nav_count = r.n,
            latest_nav_date = date(r.e * 86400, 'unixepoch'),
            last_nav = (SELECT nav FROM nav WHERE nav.code = funds.code AND nav.day = r.e)
        FROM (SELECT code, MIN(day) AS s, MAX(day) AS e, COUNT(*) AS n
              FROM nav {where} GROUP BY code) AS r
        WHERE r.code = funds.code
    """)


def _write_meta(con: sqlite3.Connection, extra: dict[str, str]) -> dict[str, str]:
    nav_rows = con.execute("SELECT COUNT(*) FROM nav").fetchone()[0]
    funds_with_nav = con.execute("SELECT COUNT(*) FROM funds WHERE nav_count > 0").fetchone()[0]
    max_day = con.execute("SELECT MAX(day) FROM nav").fetchone()[0]
    if nav_rows < MIN_NAV_ROWS or funds_with_nav < MIN_FUNDS_WITH_NAV:
        raise RuntimeError(
            f"only {nav_rows} NAV rows / {funds_with_nav} funds with NAV - upstream "
            "data looks broken, keeping the previous database"
        )
    latest = (EPOCH + timedelta(days=max_day)).isoformat() if max_day is not None else ""
    stats = {
        **extra,
        "schema": SCHEMA_VERSION,
        "refreshed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latest_nav_date": latest,
        "nav_max_date": latest,
        "nav_rows": str(nav_rows),
        "funds_with_nav": str(funds_with_nav),
    }
    con.executemany("INSERT OR REPLACE INTO meta VALUES (?, ?)", stats.items())
    return stats


# ─── Full build ──────────────────────────────────────────────────────────────

def _decompress(src: Path, dest: Path) -> None:
    import zstandard

    with open(src, "rb") as f, open(dest, "wb") as out:
        zstandard.ZstdDecompressor().copy_stream(f, out, read_size=1 << 20, write_size=1 << 20)


def full_build() -> dict[str, str]:
    data = config.DATA_DIR
    release = _get_json(f"/repos/{config.NAV_REPO}/releases/latest")
    if not release:
        raise RuntimeError(f"no releases found in {config.NAV_REPO}")
    asset = next((a for a in release.get("assets", []) if a["name"] == "funds.db.zst"), None)
    if not asset:
        raise RuntimeError(f"release {release.get('tag_name')} has no funds.db.zst")
    tag = release["tag_name"]
    log.info("full build from release %s (%.0f MB)", tag, asset["size"] / 1e6)

    zst, src, new = data / ".funds.db.zst.part", data / ".funds.db.part", data / "mfsim.sqlite.new"
    try:
        _download(asset["browser_download_url"], zst)
        _decompress(zst, src)
        zst.unlink()

        new.unlink(missing_ok=True)
        # uri=True so the ATTACH below can open the release read-only.
        con = sqlite3.connect(f"file:{new}", uri=True)
        try:
            con.executescript(
                "PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA cache_size=-32768;"
            )
            con.executescript(SCHEMA)
            con.execute("ATTACH ? AS src", (f"file:{src}?mode=ro",))
            start = time.monotonic()
            con.execute("""
                INSERT OR REPLACE INTO nav (code, day, nav)
                SELECT scheme_code, CAST(julianday(date) - 2440587.5 AS INTEGER), nav
                FROM src.nav
                WHERE scheme_code IS NOT NULL AND julianday(date) IS NOT NULL
                  AND typeof(nav) IN ('real', 'integer') AND nav != 0
            """)
            con.execute("""
                INSERT OR IGNORE INTO funds (code, name)
                SELECT scheme_code, trim(scheme_name) FROM src.schemes WHERE scheme_code IS NOT NULL
            """)
            con.execute("""
                INSERT OR REPLACE INTO isins (isin, col_rank, row_rank, code)
                SELECT upper(trim(isin)), coalesce(type, 0), 0, scheme_code
                FROM src.securities WHERE isin IS NOT NULL AND scheme_code IS NOT NULL
            """)
            con.commit()
            con.execute("DETACH src")
            src.unlink()
            log.info("release copied: %d NAV rows in %.0fs",
                     con.execute("SELECT COUNT(*) FROM nav").fetchone()[0], time.monotonic() - start)

            # The release was built from the repo as it stood when it was tagged. Day files
            # from its last week are applied anyway (they may have been re-published since,
            # and they carry AMC/category); older ones are recorded as already included.
            release_day = date.fromisoformat(tag.lstrip("v").replace(".", "-"))
            files = _list_day_files(config.TOPUP_MONTHS)
            recent = [e for e in files if e["date"] >= release_day - timedelta(days=7)]
            con.executemany("INSERT OR REPLACE INTO day_files VALUES (?,?)",
                            [(e["path"], e["sha"]) for e in files if e not in recent])
            log.info("applying %d recent day files", len(recent))
            _apply_day_files(con, recent)

            log.info("indexing")
            _update_fund_stats(con)
            con.executescript(INDEXES)
            stats = _write_meta(con, {
                "release_tag": tag,
                "full_built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
            con.commit()
            log.info("compacting")
            con.execute("VACUUM")
        finally:
            con.close()
        os.replace(new, config.DB_PATH)
        log.info("database rebuilt: %s funds with NAV, %s rows, latest NAV %s, %.0f MB",
                 stats["funds_with_nav"], stats["nav_rows"], stats["latest_nav_date"],
                 config.DB_PATH.stat().st_size / 1e6)
        return stats
    finally:
        for p in (zst, src, new):
            p.unlink(missing_ok=True)


# ─── Top-up ──────────────────────────────────────────────────────────────────

def top_up() -> bool:
    """Apply new or changed day files to the live database. True if anything changed."""
    files = _list_day_files(config.TOPUP_MONTHS)
    # Short timeout: the server holds no locks, and the only other writer would be another
    # refresh, which the lock file already rules out.
    con = sqlite3.connect(config.DB_PATH, timeout=30)
    try:
        known = dict(con.execute("SELECT path, sha FROM day_files"))
        changed = [e for e in files if known.get(e["path"]) != e["sha"]]
        if not changed:
            log.info("up to date: no new or changed day files")
            return False
        log.info("applying %d new/changed day files", len(changed))
        with con:  # one transaction: the server never sees half a top-up
            touched = _apply_day_files(con, changed)
            _update_fund_stats(con, touched)
            con.execute("INSERT INTO funds_fts (funds_fts) VALUES ('rebuild')")
            stats = _write_meta(con, {})
        log.info("database updated: latest NAV %s, %s funds with NAV",
                 stats["latest_nav_date"], stats["funds_with_nav"])
        return True
    finally:
        con.close()


# ─── Entry point ─────────────────────────────────────────────────────────────

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


def _full_build_due(meta: dict[str, str]) -> str | None:
    """Why a full build is needed, or None."""
    if not meta:
        return "no database yet"
    if meta.get("schema") != SCHEMA_VERSION:
        return "the database was built by an older version"
    if config.FULL_REBUILD_DAYS > 0:
        built = datetime.fromisoformat(meta.get("full_built_at", "1970-01-01T00:00:00+00:00"))
        age = datetime.now(timezone.utc) - built
        if age > timedelta(days=config.FULL_REBUILD_DAYS):
            return f"last full build was {age.days} days ago"
    return None


def refresh(full: bool = False) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    reason = "--full" if full else _full_build_due(read_meta(config.DB_PATH))
    if reason:
        log.info("full build: %s", reason)
        full_build()
    else:
        top_up()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
    )
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--full", "--force", action="store_true",
                        help="rebuild from the full release instead of topping up")
    args = parser.parse_args()

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.DATA_DIR / ".refresh.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.warning("another refresh is already running")
            return 0
        try:
            refresh(full=args.full)
        except Exception:
            log.exception("refresh failed; the previous database (if any) is still in use")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
