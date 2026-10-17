"""Read-only access to the SQLite database built by mfsim.refresh."""

from __future__ import annotations

import sqlite3
from bisect import bisect_right
from datetime import date, timedelta

from . import config

EPOCH = date(1970, 1, 1)

FUND_COLUMNS = (
    "code, name, nav_name, amc, category, launch_date, latest_nav_date,"
    " nav_start, nav_end, nav_count, last_nav"
)


class DataNotReady(Exception):
    """The database hasn't been built yet (first start, refresh still running)."""


def day_to_date(day: int) -> date:
    return EPOCH + timedelta(days=day)


def date_to_day(d: date) -> int:
    return (d - EPOCH).days


class NavSeries:
    """One scheme's NAV history, sorted by date, one value per date."""

    __slots__ = ("days", "navs")

    def __init__(self, days: list[int], navs: list[float]):
        self.days = days
        self.navs = navs

    @property
    def start(self) -> date:
        return day_to_date(self.days[0])

    @property
    def end(self) -> date:
        return day_to_date(self.days[-1])

    @property
    def current(self) -> float:
        return self.navs[-1]

    def on_or_before(self, d: date) -> float | None:
        """The NAV on d, or the last one published before it (holidays, weekends).
        None before the scheme's first NAV. Binary search, O(log n)."""
        day = date_to_day(d)
        i = bisect_right(self.days, day) - 1
        return self.navs[i] if i >= 0 else None


def _fund_dict(row) -> dict:
    (code, name, nav_name, amc, category, launch_date, latest_nav_date,
     nav_start, nav_end, nav_count, last_nav) = row
    return {
        "code": code,
        "name": name or f"Scheme {code}",
        "nav_name": nav_name,
        "amc": amc,
        "category": category,
        "launch_date": launch_date,
        "latest_nav_date": latest_nav_date,
        "nav_start": day_to_date(nav_start).isoformat() if nav_start is not None else None,
        "nav_end": day_to_date(nav_end).isoformat() if nav_end is not None else None,
        "nav_count": nav_count or 0,
        "last_nav": last_nav,
    }


class Db:
    """A short-lived read-only connection: open one per request. The refresh job replaces
    the file with a rename, and a new connection always sees the newest database."""

    def __init__(self):
        if not config.DB_PATH.exists():
            raise DataNotReady()
        self.con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)

    def __enter__(self) -> "Db":
        return self

    def __exit__(self, *exc) -> None:
        self.con.close()

    def meta(self) -> dict[str, str]:
        return dict(self.con.execute("SELECT key, value FROM meta"))

    def fund(self, code: int) -> dict | None:
        row = self.con.execute(f"SELECT {FUND_COLUMNS} FROM funds WHERE code = ?", (code,)).fetchone()
        return _fund_dict(row) if row else None

    def search_funds(self, query: str, limit: int = 30) -> list[dict]:
        """Schemes with NAV history whose name contains every word of the query (any
        order, case-insensitive). A number also matches the scheme code."""
        words = query.strip().split()
        if not words:
            return []
        where, args = ["nav_count > 0"], []
        # Words of 3+ characters go through the trigram index (funds_fts), each as a quoted
        # phrase so it's matched as a plain substring. The trigram index can't match
        # anything shorter, so 1-2 character words ("50", "g") filter with LIKE instead.
        long_words = [w for w in words if len(w) >= 3]
        if long_words:
            where.append("code IN (SELECT rowid FROM funds_fts WHERE funds_fts MATCH ?)")
            args.append(" AND ".join('"' + w.replace('"', '""') + '"' for w in long_words))
        for w in words:
            if len(w) < 3:
                pattern = "%" + w.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                where.append("(name || ' ' || coalesce(nav_name, '')) LIKE ? ESCAPE '\\'")
                args.append(pattern)
        sql = (
            f"SELECT {FUND_COLUMNS} FROM funds WHERE "
            + " AND ".join(where)
            + " ORDER BY name, nav_name, code LIMIT ?"
        )
        rows = self.con.execute(sql, (*args, limit)).fetchall()
        if len(words) == 1 and words[0].isdigit():
            exact = self.fund(int(words[0]))
            if exact and exact["nav_count"] and all(r[0] != exact["code"] for r in rows):
                return [exact] + [_fund_dict(r) for r in rows][: limit - 1]
        return [_fund_dict(r) for r in rows]

    def match_isin(self, isin: str | None) -> dict | None:
        """The scheme whose ISIN columns contain this ISIN (first column, then first row)."""
        if not isin:
            return None
        row = self.con.execute(
            "SELECT code FROM isins WHERE isin = ? ORDER BY col_rank, row_rank LIMIT 1",
            (isin.strip().upper(),),
        ).fetchone()
        return self.fund(row[0]) if row else None

    def nav_series(self, code: int) -> NavSeries | None:
        rows = self.con.execute(
            "SELECT day, nav FROM nav WHERE code = ? ORDER BY day", (code,)
        ).fetchall()
        if not rows:
            return None
        days, navs = zip(*rows)
        return NavSeries(list(days), list(navs))
