# Include sells in calculation — Design

**Date:** 2026-04-28
**Scope:** [app.py](../../../app.py)

## Goal

Account for sell/redemption transactions in the comparison instead of silently dropping them. Default is realistic — sells are positive cashflows and current value uses remaining units only. A toggle lets users opt back into the old "pretend held everything" behavior.

## Non-goals

- No FIFO/LIFO cost-basis tracking. Units only.
- No tax/STCG/LTCG calculations.
- No detection of "user sold more than they bought" in source data (treat statement as truth).
- No new UI section — toggle lives next to the Run button.

## Behavior change

| | Before | After (default) | After (toggle on) |
|---|---|---|---|
| Sells in parser | Dropped | Kept | Kept (filtered before compute) |
| Current value | All bought units × NAV | Remaining units × NAV | All bought units × NAV |
| XIRR cashflows | Buys only | Buys + sells + terminal | Buys + terminal |

## Detailed design

### Parser ([`parse_zerodha`])

- **Zerodha CSV branch:** stop filtering on `trade_type == "buy"`. Keep both `buy` and `sell`. Set `direction = trade_type.lower()`.
- **Legacy Excel fallback:** extend keyword matching:
  - Buy keywords: existing list (`purchase`, `buy`, `sip`, `lumpsum`, `invest`, `switch in`).
  - Sell keywords (new): `redeem`, `sell`, `switch out`.
  - Normalize `direction` from whichever matches; rows where `txn_type` matches neither but `amount < 0` are treated as `sell`.
- All output rows carry positive `amount`; `direction` carries the sign semantics.

### Toggle UI

Single `st.checkbox` rendered above the "Run Comparison" button:

> ☐ Exclude sells from calculation (treat all bought units as still held)

- Default unchecked.
- Hidden entirely when the pooled selection contains zero sell rows.

When checked, the pre-compute step filters `direction == "sell"` rows out before passing to the scenario functions.

### Compute layer

Both `compute_scenario` and `compute_scenario_pooled` updated to honor `direction`:

```
for each row:
    nav = nav_on_or_before(series, date)
    units = amount / nav
    if direction == "buy":
        cashflow = -amount
        fund_units += units
    elif direction == "sell":
        cashflow = +amount
        fund_units -= units      # alt path: alt units may go negative
```

**Per-fund current value:** `remaining_units × current_nav_of_that_fund`.
**Pooled actual:** sum of per-fund current values.

**Headline metrics (when sells exist in scope):**

- `Total bought` = Σ buy amounts
- `Total sold` = Σ sell amounts
- `Net invested` = bought − sold
- `Current Value` = remaining units × current NAV
- `Total Proceeds` = current_value + sold *(apples-to-apples for return %)*
- `Total Return %` = (proceeds − bought) / bought × 100
- `XIRR` over the full cashflow timeline + terminal current_value

When no sells in scope (or toggle on): summary table reverts to today's shape — the new rows are conditionally hidden.

### Alt-fund "negative units" edge case

If a sell on date D would redeem more cash than the running alt-fund balance at `alt_nav(D)`, alt units go negative for math consistency (cashflow is mirrored exactly). A warning surfaces above the summary table:

> ⚠️ On <date> your sell of ₹X exceeded the alt fund's value at that date. Alt units went negative — the comparison is still computed but the alt scenario's remaining units is not physically realizable.

### Transaction detail table

- Add `Type` column (`Buy` / `Sell`).
- Sell rows: `Amount` displayed as `−₹X`; `Actual Units` and `Alt Units` displayed as negative numbers.
- Existing `no_nav` warnings unchanged.

### Excel export

- `Summary` sheet: includes the new rows when applicable.
- `Transactions` sheet: includes `Type` column.

## Files touched

- [app.py](../../app.py) — all changes localized here.

## Testing

Manual smoke tests:

1. **Buys only (no sells in statement):** behavior unchanged from current state. Toggle hidden.
2. **Buys + sells, toggle off (default):** verify net invested, total proceeds, and XIRR reconcile by hand.
3. **Buys + sells, toggle on:** output matches the buys-only output for the same data (verifies the toggle bypass).
4. **Full redemption** (sold everything): remaining units = 0, XIRR meaningful from buy/sell timeline.
5. **Negative alt units:** craft a case where alt underperformed and a sell exceeded alt balance — confirm warning fires and math still completes.
