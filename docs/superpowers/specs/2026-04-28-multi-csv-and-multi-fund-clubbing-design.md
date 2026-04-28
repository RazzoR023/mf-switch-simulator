# Multi-CSV upload & multi-fund clubbing — Design

**Date:** 2026-04-28
**Scope:** [app.py](../../../app.py)

## Goal

Let users (1) upload multiple Zerodha tradebook CSVs in one go and have them combined into a single purchase set, and (2) select multiple funds from that combined purchase history and compare the pooled real performance against a single alternate fund.

The driving question: *"What if all the money I put across these N funds had gone into this one fund instead?"*

## Non-goals

- No per-fund-vs-alt breakdown columns (one pooled "Actual" column only).
- No reordering of the existing 4-step flow.
- No new charts, no caching changes, no API integrations.
- No safeguards for cross-format file mixing beyond what `parse_zerodha()` already tolerates.

## User flow

```
Step 1  Upload one or more CSVs/XLSX
        → Parse each, concat, dedupe, show per-file + dedupe notice
Step 2  Multi-select funds from the pooled statement
        → Per-fund mini-summary + combined badge
Step 3  ISIN auto-match each selected fund
        → Compact status list; manual search expander per failure
Step 4  Pick a single alternate fund (unchanged)
Run     Pooled-actual vs single-alt comparison
        → Verdict + summary table + per-transaction detail (with Fund col)
```

Selecting one file + one fund collapses cleanly to the current single-fund single-file flow.

## Detailed design

### Step 1 — Multi-file upload

- `st.file_uploader(..., accept_multiple_files=True)`.
- Iterate the uploaded list; each file goes through the existing `parse_zerodha()`. Parsed DataFrames are concatenated into one `purchases_df`.
- Per-file feedback: one `✓ <filename> → N purchases` line per file, and a `✗ <filename>: <error>` line for any file that fails to parse (other files still process).
- **Dedupe:**
  - If every parsed row has a non-empty `trade_id`, dedupe on `trade_id` (preferred — it's a stable unique key from Zerodha CSV).
  - Otherwise dedupe on the row-key tuple `(scheme_name, date, units, nav, trade_type)`. This covers the legacy-Excel path which doesn't carry `trade_id`.
  - When `units` or `nav` aren't present (Excel fuzzy fallback path with only `amount`), the row-key falls back to `(scheme_name, date, amount, txn_type)`.
- Surface a single notice when dedupe drops rows: `Removed N duplicate rows across files`.

### Step 2 — Multi-select fund

- Replace the `st.selectbox("Your fund (from statement)", ...)` with `st.multiselect(...)`. Default is empty — user picks.
- `selected_funds: list[str]` replaces `selected_fund: str`. Downstream gates check `if selected_funds:` instead of truthy string check.
- Show a compact per-fund summary (one line each):
  - `<fund name> · <N> purchases · <first date> → <last date>`
- Plus one combined `range-badge` covering the union: `<total funds> funds · <total purchases> · <min date> → <max date>`.
- The "Preview transactions" expander shows pooled rows from all selected funds, with a new `Fund` column, sorted by date.

### Step 3 — ISIN matching per fund

- Run the existing ISIN auto-match logic (single-ISIN check + iterate `isin*` columns) once per selected fund.
- Render a compact status list — one line per fund:
  ```
  ✓ Parag Parikh Flexi Cap → Parag Parikh Flexi Cap Reg-G [122639]
  ✓ Quant Small Cap        → Quant Small Cap Fund Reg-G   [120828]
  ✗ <Fund X>               → ISIN HKLM12 not in database
  ```
- For each ✗ entry, render a manual-search expander beneath the list (one per failed fund). Widget keys are namespaced by scheme name (e.g. `actual_q_<idx>`, `actual_results_<idx>`, `actual_sel_<idx>`) to avoid Streamlit widget-key collisions across multiple expanders.
- Internal state: `actual_codes: dict[str, int]` mapping `scheme_name → AMFI scheme_code`.
- "Run Comparison" button is gated on `len(actual_codes) == len(selected_funds)`.

### Step 4 — Alternate fund

Unchanged. Single `st.selectbox` over the full NAV-backed scheme list. Date-coverage warning continues to fire, recomputed against the *pooled* purchase set: count and range of purchases that predate the alt fund's launch.

### Compute layer

Add one new function alongside the existing `compute_scenario`:

```python
def compute_scenario_pooled(
    purchases: pd.DataFrame,           # pooled rows from N selected funds
    name_to_series: dict[str, pd.Series],  # scheme_name → NAV series
    label: str = "Actual (pooled)",
) -> dict:
    ...
```

- For each row, look up the NAV from `name_to_series[row["scheme_name"]]` using the existing `nav_on_or_before` helper.
- "Current value" sums per-fund: for each scheme, `units_in_that_scheme × current_nav_of_that_scheme`.
- XIRR is computed over the pooled cashflow timeline: each purchase is a negative cashflow at its own date, and the single "today" cashflow is the sum of current values across all schemes.
- Returns the same shape as `compute_scenario`, with `detail` carrying an extra `fund` column.

The existing `compute_scenario(...)` is left unchanged and continues to handle the alternate side (one NAV series applied to every pooled purchase row).

### Comparison output

- **Verdict box:** copy adapted to multi-fund:
  > *"Clubbing your N funds (X purchases) into <AltFund> would have added/cost ₹Y (+/-Z% XIRR difference)."*
  When N=1, fall back to the current phrasing.
- **Summary table:** structure unchanged. Two columns (`Actual · pooled` and `Alternate · <alt name>`). Header for the actual column reads `Actual · N funds clubbed` when N>1, or `Actual · <fund name>` when N=1. Existing rows (Total Invested / Matched / Skipped / Current NAV / Total Units / Current Value / Absolute Return / Total Return % / XIRR) are kept; "Current NAV" for the pooled side displays `—` (no single NAV) when N>1.
- **Transaction detail:** rebuilt with columns `Date | Fund | Amount | Actual NAV | Actual Units | Alt NAV | Alt Units | Notes`. One row per purchase, sorted by date. `no_nav` status flagged the same way as today. The current outer-merge-on-date logic is replaced by a row-level join (each detail row is a single purchase, so the actual + alt sides line up 1:1 by row index, not by date).
- **Excel export:**
  - `Summary` sheet: same shape, header label adapted as above.
  - `Transactions` sheet: includes the new `Fund` column.

### Edge cases & failure modes

- **Single file, single fund:** Entire flow collapses to today's behavior. The new `compute_scenario_pooled` with a one-entry `name_to_series` produces the same numbers as the current single-series path.
- **One file fails to parse, others succeed:** Show the error for the failing file, continue with the rest.
- **All files fail to parse:** Same as today's "no purchases" state — downstream sections don't render.
- **User picks 0 funds in Step 2:** Step 3 onward gated off (existing pattern).
- **Some selected funds fail ISIN match, others succeed:** Run is blocked until manual matches are filled in. Successful matches stay visible — user only deals with the failures.
- **Dedupe drops a row that wasn't actually a duplicate:** Mitigated by preferring `trade_id` (a stable Zerodha key). The row-key fallback for legacy Excel is conservative — same scheme + same date + same units + same NAV + same trade type is a dupe in practice.
- **Same scheme appears in multiple uploaded files but with different statement-name spellings:** Out of scope — treated as separate funds in Step 2 (user can pick both, ISIN match will resolve them to the same or different AMFI codes).

## Files touched

- [app.py](../../app.py) — all changes localized here. No new modules.

## Testing

No automated test suite exists. Manual smoke tests:

1. **Single file, single fund** — confirm output is byte-for-byte identical to pre-change behavior on a known input.
2. **Two files with overlap** — upload FY24 + FY24+FY25 export, confirm dedupe notice and that totals match the larger file alone.
3. **Multi-fund club** — pick 3 funds, confirm pooled XIRR + current value reconcile by hand against the per-fund numbers.
4. **ISIN match failure path** — temporarily corrupt one fund's ISIN, confirm the manual-search expander renders for only that fund and "Run" stays gated.
5. **Excel export** — confirm `Fund` column present in Transactions sheet for multi-fund runs.
