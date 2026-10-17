"""The comparison: replay the selected transactions in the funds actually bought (pooled)
and in one alternate fund, then line the two up. Everything the UI shows comes from here;
the UI only formats it."""

from __future__ import annotations

from datetime import date

from .db import Db, NavSeries
from .finance import xirr


class CompareError(Exception):
    """A request the comparison can't run for. The message is shown to the user."""


def _direction(t: dict) -> str:
    d = t.get("direction", "buy")
    return d if d in ("buy", "sell") else "buy"


def _by_date(txns: list[dict]) -> list[dict]:
    return sorted(txns, key=lambda t: t["date"])


def _totals(rows: list[dict], current_value: float, today: date) -> dict:
    matched = [r for r in rows if r["status"] == "ok"]
    buys = [r for r in matched if r["direction"] == "buy"]
    sells = [r for r in matched if r["direction"] == "sell"]
    total_bought = float(sum(r["amount"] for r in buys))
    total_sold = float(sum(r["amount"] for r in sells))
    total_proceeds = current_value + total_sold
    absolute_ret = total_proceeds - total_bought

    # Buys are money in (negative), sells money out (positive), plus today's value.
    cf_dates = [r["date"] for r in matched] + [today]
    cf_amounts = [-r["amount"] if r["direction"] == "buy" else r["amount"] for r in matched]
    cf_amounts.append(current_value)

    return {
        "total_bought": total_bought,
        "total_sold": total_sold,
        "net_invested": total_bought - total_sold,
        "total_units": float(sum(r["units"] for r in matched)),
        "current_value": current_value,
        "total_proceeds": total_proceeds,
        "absolute_ret": absolute_ret,
        "return_pct": (absolute_ret / total_bought * 100) if total_bought else 0.0,
        "xirr": xirr(cf_amounts, cf_dates),
        "matched": len(matched),
        "skipped": len(rows) - len(matched),
        "n_buys": len(buys),
        "n_sells": len(sells),
    }


def compute_scenario(txns: list[dict], series: NavSeries, label: str, today: date) -> dict:
    """Every transaction replayed in one fund (the alternate). Buys add units, sells remove
    them. The running balance can go negative when a sell is bigger than what the alternate
    fund was worth by then; those are reported in negative_events."""
    rows, running, negative_events = [], 0.0, []
    for t in _by_date(txns):
        d = date.fromisoformat(t["date"])
        amt = abs(float(t["amount"]))
        direction = _direction(t)
        nav = series.on_or_before(d)
        if nav:
            units = amt / nav if direction == "buy" else -amt / nav
            running += units
            if direction == "sell" and running < 0:
                negative_events.append({"date": d.isoformat(), "running": running, "amount": amt})
        else:
            units = None
        rows.append({
            "date": d, "fund": t.get("scheme_name"), "direction": direction, "amount": amt,
            "nav": nav, "units": units, "status": "ok" if nav else "no_nav",
        })
    current_value = sum(r["units"] for r in rows if r["status"] == "ok") * series.current
    return {"label": label, "current_nav": series.current, **_totals(rows, current_value, today),
            "rows": rows, "negative_events": negative_events}


def compute_scenario_pooled(txns: list[dict], fund_series: dict[str, NavSeries], label: str,
                            today: date) -> dict:
    """The real portfolio: each transaction valued in its own fund's NAV, today's value
    summed per fund at that fund's latest NAV."""
    rows, running, negative_events = [], {}, []
    for t in _by_date(txns):
        fund = t["scheme_name"]
        d = date.fromisoformat(t["date"])
        amt = abs(float(t["amount"]))
        direction = _direction(t)
        series = fund_series.get(fund)
        nav = series.on_or_before(d) if series is not None else None
        if nav:
            units = amt / nav if direction == "buy" else -amt / nav
            running[fund] = running.get(fund, 0.0) + units
            if direction == "sell" and running[fund] < 0:
                negative_events.append(
                    {"fund": fund, "date": d.isoformat(), "running": running[fund], "amount": amt}
                )
        else:
            units = None
        rows.append({
            "date": d, "fund": fund, "direction": direction, "amount": amt,
            "nav": nav, "units": units, "status": "ok" if nav else "no_nav",
        })

    held: dict[str, float] = {}
    for r in rows:
        if r["status"] == "ok":
            held[r["fund"]] = held.get(r["fund"], 0.0) + r["units"]
    current_value = sum(units * fund_series[f].current for f, units in held.items())
    return {"label": label, "current_nav": None, **_totals(rows, current_value, today),
            "rows": rows, "negative_events": negative_events}


# ─── Request-level helpers ───────────────────────────────────────────────────

def fund_summaries(db: Db, txns: list[dict]) -> list[dict]:
    """One entry per fund in the statement: counts, date range and the ISIN match."""
    by_fund: dict[str, list[dict]] = {}
    for t in txns:
        if t.get("scheme_name"):
            by_fund.setdefault(t["scheme_name"], []).append(t)
    out = []
    for name in sorted(by_fund):
        ftx = by_fund[name]
        isins = [t["isin"].strip() for t in ftx if (t.get("isin") or "").strip()]
        isin = isins[0] if isins else None
        match = db.match_isin(isin)
        if match and not match["nav_count"]:
            reason, match = "no_nav", None
        elif match:
            reason = None
        else:
            reason = "isin_not_found" if isin else "no_isin"
        dates = [t["date"] for t in ftx]
        out.append({
            "name": name,
            "isin": isin,
            "n_txns": len(ftx),
            "n_buys": sum(1 for t in ftx if t.get("direction") == "buy"),
            "n_sells": sum(1 for t in ftx if t.get("direction") == "sell"),
            "first_date": min(dates),
            "last_date": max(dates),
            "match": match,
            "match_problem": reason,
        })
    return out


def coverage(db: Db, txns: list[dict], funds: list[str], alt_code: int) -> dict:
    """How the selected transactions line up with the alternate fund's NAV history."""
    fund = db.fund(alt_code)
    if not fund or not fund["nav_count"]:
        raise CompareError(f"Scheme code {alt_code} has no NAV history in the database.")
    selected = [t for t in txns if t.get("scheme_name") in set(funds)]
    before = sorted(t["date"] for t in selected if t["date"] < fund["nav_start"])
    return {
        "fund": fund,
        "n_before": len(before),
        "first_before": before[0] if before else None,
        "last_before": before[-1] if before else None,
    }


def _cls(a: float | None, b: float | None) -> tuple[str, str]:
    """Which side wins a metric where higher is better."""
    if a is None or b is None or a == b:
        return "neutral", "neutral"
    return ("better", "worse") if a > b else ("worse", "better")


def _metrics(actual: dict, alt: dict, sells_present: bool) -> list[dict]:
    def row(key, label, kind, a, b, cls=("neutral", "neutral")):
        return {"key": key, "label": label, "kind": kind, "actual": a, "alternate": b,
                "actual_cls": cls[0], "alternate_cls": cls[1]}

    value_cls = _cls(actual["current_value"], alt["current_value"])
    rows = []
    if sells_present:
        rows += [
            row("total_bought", "Total Bought", "money", actual["total_bought"], alt["total_bought"]),
            row("total_sold", "Total Sold", "money", actual["total_sold"], alt["total_sold"]),
            row("net_invested", "Net Invested", "money", actual["net_invested"], alt["net_invested"]),
            row("n_buys", "Buy transactions", "count", actual["n_buys"], alt["n_buys"]),
            row("n_sells", "Sell transactions", "count", actual["n_sells"], alt["n_sells"]),
        ]
    else:
        rows += [
            row("net_invested", "Total Invested", "money", actual["net_invested"], alt["net_invested"]),
            row("matched", "Transactions matched", "count", actual["matched"], alt["matched"]),
        ]
    rows += [
        row("skipped", "Transactions skipped (no NAV)", "count", actual["skipped"], alt["skipped"]),
        row("current_nav", "Current NAV", "nav", actual["current_nav"], alt["current_nav"]),
        row("total_units", "Remaining Units" if sells_present else "Total Units", "units",
            actual["total_units"], alt["total_units"]),
        row("current_value", "Current Value", "money", actual["current_value"],
            alt["current_value"], value_cls),
    ]
    if sells_present:
        rows.append(row("total_proceeds", "Total Proceeds (current + sold)", "money",
                        actual["total_proceeds"], alt["total_proceeds"],
                        _cls(actual["total_proceeds"], alt["total_proceeds"])))
    rows += [
        row("absolute_ret", "Absolute Return", "money", actual["absolute_ret"],
            alt["absolute_ret"], value_cls),
        row("return_pct", "Total Return %", "pct", actual["return_pct"], alt["return_pct"],
            _cls(actual["return_pct"], alt["return_pct"])),
        row("xirr", "XIRR", "xirr", actual["xirr"], alt["xirr"],
            _cls(actual["xirr"] or 0.0, alt["xirr"] or 0.0)),
    ]
    return rows


def run(db: Db, txns: list[dict], funds: list[str], actual_codes: dict[str, int],
        alt_code: int, exclude_sells: bool, today: date | None = None) -> dict:
    today = today or date.today()
    if not funds:
        raise CompareError("Pick at least one fund from your statement.")
    unmatched = [f for f in funds if f not in actual_codes]
    if unmatched:
        raise CompareError(f"Match these funds to a scheme first: {', '.join(unmatched)}.")

    selected = [t for t in txns if t.get("scheme_name") in set(funds)]
    if exclude_sells:
        selected = [t for t in selected if t.get("direction") != "sell"]
    if not selected:
        raise CompareError("There are no transactions to compare for the selected funds.")

    fund_series: dict[str, NavSeries] = {}
    for fund in funds:
        series = db.nav_series(int(actual_codes[fund]))
        if series is None:
            raise CompareError(f"Scheme code {actual_codes[fund]} for '{fund}' has no NAV history.")
        fund_series[fund] = series
    alt_series = db.nav_series(int(alt_code))
    alt_fund = db.fund(int(alt_code))
    if alt_series is None or alt_fund is None:
        raise CompareError(f"Scheme code {alt_code} has no NAV history.")

    actual_label = funds[0] if len(funds) == 1 else f"{len(funds)} funds clubbed"
    actual = compute_scenario_pooled(selected, fund_series, actual_label, today)
    # The plan-level name ("... - Direct Plan - Growth"): the scheme name alone is shared by
    # its Regular, Direct, IDCW and Growth variants.
    alt = compute_scenario(selected, alt_series, alt_fund["nav_name"] or alt_fund["name"], today)
    sells_present = actual["n_sells"] + alt["n_sells"] > 0

    # Both sides walked the same date-sorted transactions, so their rows line up 1:1.
    detail = [
        {
            "date": a["date"].isoformat(), "fund": a["fund"], "direction": a["direction"],
            "amount": a["amount"],
            "actual_nav": a["nav"], "actual_units": a["units"], "actual_status": a["status"],
            "alt_nav": b["nav"], "alt_units": b["units"], "alt_status": b["status"],
        }
        for a, b in zip(actual["rows"], alt["rows"])
    ]

    def side(res: dict) -> dict:
        return {k: v for k, v in res.items() if k != "rows"}

    return {
        "as_of": today.isoformat(),
        "actual": side(actual),
        "alternate": side(alt) | {"fund": alt_fund},
        "funds": funds,
        "exclude_sells": exclude_sells,
        "n_txns": len(selected),
        "sells_present": sells_present,
        "verdict": {
            "value_diff": alt["current_value"] - actual["current_value"],
            "xirr_diff": ((alt["xirr"] or 0.0) - (actual["xirr"] or 0.0)) * 100,
        },
        "metrics": _metrics(actual, alt, sells_present),
        "detail": detail,
        "missing": {
            "actual": sum(1 for r in detail if r["actual_status"] == "no_nav"),
            "alternate": sum(1 for r in detail if r["alt_status"] == "no_nav"),
        },
    }
