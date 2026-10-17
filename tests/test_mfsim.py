"""Unit tests: python -m unittest discover -s tests (no network, no real database)."""

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = tempfile.mkdtemp(prefix="mfsim-test-")
os.environ["DATA_DIR"] = TMP

from mfsim import compare, config, finance, refresh, tradebook  # noqa: E402
from mfsim.db import Db, NavSeries, date_to_day  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def build_db():
    """Two schemes with daily NAVs over 2020-2023: A grows 10%/yr, B is flat at 10."""
    config.DB_PATH.unlink(missing_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.executescript(refresh.SCHEMA)
    start = date(2020, 1, 1)
    rows = []
    for i in range(4 * 365):
        d = date_to_day(start + timedelta(days=i))
        rows.append((1, d, 10 * 1.1 ** (i / 365)))
        rows.append((2, d, 10.0))
    con.executemany("INSERT INTO nav VALUES (?,?,?)", rows)
    con.executemany(
        "INSERT INTO funds (code, name, nav_name) VALUES (?,?,?)",
        [(1, "Growing Fund", "Growing Fund - Direct - Growth"), (2, "Flat Fund", "Flat Fund - Direct")],
    )
    con.execute("INSERT INTO isins VALUES ('INF000A01', 0, 0, 1)")
    refresh._update_fund_stats(con)
    con.executescript(refresh.INDEXES)
    con.execute("INSERT INTO meta VALUES ('latest_nav_date', '2023-12-30')")
    con.commit()
    con.close()


class FinanceTests(unittest.TestCase):
    def test_xirr_one_year_ten_percent(self):
        r = finance.xirr([-1000, 1100], [date(2021, 1, 1), date(2022, 1, 1)])
        self.assertAlmostEqual(r, 0.1, places=9)

    def test_xirr_needs_a_sign_change(self):
        self.assertIsNone(finance.xirr([-1000, -50], [date(2021, 1, 1), date(2022, 1, 1)]))
        self.assertIsNone(finance.xirr([-1000], [date(2021, 1, 1)]))

    def test_xirr_total_loss_is_none_not_an_error(self):
        self.assertIsNone(finance.xirr([-1000, 0.0], [date(2021, 1, 1), date(2022, 1, 1)]))


class TradebookTests(unittest.TestCase):
    def test_zerodha_csv_and_dedupe(self):
        rows = []
        for name in ("tradebook-a.csv", "tradebook-b.csv"):
            parsed, warnings = tradebook.parse_file(name, (FIXTURES / name).read_bytes())
            self.assertEqual(warnings, [])
            rows += parsed
        self.assertEqual(len(rows), 72)
        unique, dropped, method = tradebook.dedupe(rows)
        self.assertEqual((len(unique), dropped, method), (62, 10, "trade ID"))
        self.assertEqual({r["direction"] for r in unique}, {"buy", "sell"})
        self.assertTrue(all(r["amount"] > 0 for r in unique))

    def test_fuzzy_layout_with_day_first_dates(self):
        csv = (
            "Date,Scheme Name,Transaction Type,Amount\n"
            "05/01/2021,Some Fund,SIP Purchase,\"5,000\"\n"
            "05/02/2021,Some Fund,Redemption,2000\n"
            "05/03/2021,Some Fund,Unknown,-1000\n"
        ).encode()
        rows, _ = tradebook.parse_file("export.csv", csv)
        self.assertEqual([r["date"] for r in rows], ["2021-01-05", "2021-02-05", "2021-03-05"])
        self.assertEqual([r["direction"] for r in rows], ["buy", "sell", "sell"])
        self.assertEqual([r["amount"] for r in rows], [5000.0, 2000.0, 1000.0])

    def test_missing_columns_is_a_readable_error(self):
        with self.assertRaises(tradebook.TradebookError):
            tradebook.parse_file("x.csv", b"foo,bar\n1,2\n")


DAY_FILE_NEW = """Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Multi Cap Fund )


Aditya Birla Sun Life Mutual Fund
148921;Aditya Birla Sun Life Multi-Cap Fund-Direct Growth;Direct Plan;GROWTH;INF209KB1Y49;;21.90;16-Oct-2026
148920;Aditya Birla Sun Life Multi-Cap Fund-Direct IDCW Payout;Direct Plan;IDCW Payout;iinf209kb1y56;INF209KB1Y57;1,018.02;16-Oct-2026

Bajaj Finserv Mutual Fund
153309;BAJAJ FINSERV MULTI CAP FUND - DIRECT - GROWTH;Direct Plan;Growth;NOTAPP;;N.A.;16-Oct-2026
"""

DAY_FILE_OLD = """Scheme Code;Scheme Name;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Repurchase Price;Sale Price;Date

Close Ended Schemes ( Income )

Some AMC Mutual Fund

100001;Some Income Fund - Growth;INF000X01011;;12.5;;;05-Jan-2010
"""


class DayFileTests(unittest.TestCase):
    def test_current_format(self):
        rows, schemes, isins = refresh.parse_day_file(DAY_FILE_NEW, date(2026, 10, 16))
        day = date_to_day(date(2026, 10, 16))
        self.assertEqual(rows, [(148921, day, 21.9), (148920, day, 1018.02)])  # N.A. dropped
        self.assertEqual(
            schemes[148920],
            ("Aditya Birla Sun Life Multi-Cap Fund-Direct IDCW Payout",
             "Aditya Birla Sun Life Mutual Fund", "Equity Scheme - Multi Cap Fund"),
        )
        self.assertEqual(schemes[153309][1], "Bajaj Finserv Mutual Fund")
        # Lowercase and the extra leading I fixed; NOTAPP dropped.
        self.assertEqual(sorted(isins), [
            ("INF209KB1Y49", 0, 148921), ("INF209KB1Y56", 0, 148920), ("INF209KB1Y57", 1, 148920),
        ])

    def test_old_format(self):
        rows, schemes, isins = refresh.parse_day_file(DAY_FILE_OLD, date(2010, 1, 5))
        self.assertEqual(rows, [(100001, date_to_day(date(2010, 1, 5)), 12.5)])
        self.assertEqual(schemes[100001], ("Some Income Fund - Growth", "Some AMC Mutual Fund", "Income"))
        self.assertEqual(isins, [("INF000X01011", 0, 100001)])

    def test_not_a_day_file(self):
        self.assertEqual(refresh.parse_day_file("<html>error</html>", date(2026, 1, 1)), ([], {}, []))


class CompareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_db()

    def test_nav_on_or_before(self):
        s = NavSeries([10, 12, 15], [1.0, 2.0, 3.0])
        on = lambda d: s.on_or_before(date(1970, 1, 1) + timedelta(days=d))  # noqa: E731
        self.assertEqual([on(9), on(10), on(11), on(14), on(99)], [None, 1.0, 1.0, 2.0, 3.0])

    def test_search_and_isin(self):
        with Db() as db:
            self.assertEqual([f["code"] for f in db.search_funds("grow direct")], [1])
            self.assertEqual([f["code"] for f in db.search_funds("2")], [2])
            self.assertEqual(db.match_isin("inf000a01")["code"], 1)
            self.assertIsNone(db.match_isin("INF999"))

    def test_switch_from_flat_to_growing_fund(self):
        txns = [
            {"date": "2020-01-01", "scheme_name": "Mine", "direction": "buy", "amount": 1000},
            {"date": "2021-01-01", "scheme_name": "Mine", "direction": "sell", "amount": 500},
            {"date": "2019-06-01", "scheme_name": "Mine", "direction": "buy", "amount": 100},
        ]
        with Db() as db:
            res = compare.run(db, txns, ["Mine"], {"Mine": 2}, 1, False, today=date(2023, 12, 30))
        a, b = res["actual"], res["alternate"]
        # The 2019 buy predates both NAV histories: skipped on both sides.
        self.assertEqual((a["skipped"], b["skipped"]), (1, 1))
        self.assertEqual((a["total_bought"], a["total_sold"]), (1000.0, 500.0))
        self.assertAlmostEqual(a["current_value"], 500.0)  # flat fund: 50 units x 10
        self.assertGreater(b["current_value"], a["current_value"])
        self.assertGreater(res["verdict"]["value_diff"], 0)
        self.assertEqual([r["date"] for r in res["detail"]], ["2019-06-01", "2020-01-01", "2021-01-01"])
        self.assertEqual(b["label"], "Growing Fund - Direct - Growth")

    def test_alt_units_can_go_negative(self):
        txns = [
            {"date": "2020-01-01", "scheme_name": "Mine", "direction": "buy", "amount": 1000},
            {"date": "2023-01-01", "scheme_name": "Mine", "direction": "sell", "amount": 1300},
        ]
        with Db() as db:
            res = compare.run(db, txns, ["Mine"], {"Mine": 1}, 2, False, today=date(2023, 12, 30))
        self.assertEqual(len(res["alternate"]["negative_events"]), 1)

    def test_unmatched_fund_is_an_error(self):
        with Db() as db, self.assertRaises(compare.CompareError):
            compare.run(db, [], ["Mine"], {}, 1, False)


class TopUpTests(unittest.TestCase):
    """top_up() against a throwaway database, with the GitHub calls stubbed out."""

    def setUp(self):
        build_db()
        self.addCleanup(lambda: config.DB_PATH.unlink(missing_ok=True))
        self.files = [{"path": "data/2026/10/16.csv", "sha": "a1", "date": date(2026, 10, 16)}]
        self.fetched = []
        self._list, self._get = refresh._list_day_files, refresh._get_bytes
        refresh._list_day_files = lambda months: list(self.files)
        refresh._get_bytes = lambda url: self.fetched.append(url) or DAY_FILE_NEW.encode()
        self.addCleanup(lambda: setattr(refresh, "_list_day_files", self._list))
        self.addCleanup(lambda: setattr(refresh, "_get_bytes", self._get))
        refresh.MIN_NAV_ROWS, refresh.MIN_FUNDS_WITH_NAV = 1, 1

    def test_applies_new_files_once(self):
        self.assertTrue(refresh.top_up())
        with Db() as db:
            fund = db.fund(148920)
            self.assertEqual(fund["amc"], "Aditya Birla Sun Life Mutual Fund")
            self.assertEqual(fund["nav_end"], "2026-10-16")
            self.assertEqual(fund["last_nav"], 1018.02)
            self.assertEqual(db.match_isin("INF209KB1Y57")["code"], 148920)
            self.assertEqual([f["code"] for f in db.search_funds("multi-cap direct idcw")], [148920])
            self.assertEqual(db.meta()["latest_nav_date"], "2026-10-16")
        # Same SHA again: nothing to fetch.
        self.assertFalse(refresh.top_up())
        self.assertEqual(len(self.fetched), 1)
        # A re-published file (new SHA) is fetched again.
        self.files[0]["sha"] = "b2"
        self.assertTrue(refresh.top_up())
        self.assertEqual(len(self.fetched), 2)


if __name__ == "__main__":
    unittest.main()
