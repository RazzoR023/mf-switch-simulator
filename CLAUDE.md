# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Activate the virtualenv before running anything:

```bash
# Windows (this dev environment)
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

Common commands:

- Install deps: `pip install -r requirements.txt`
- Run the app: `streamlit run app.py` (serves on http://localhost:8501)
- Force a fresh data download: delete `fund_list.csv` and/or `nav_history.parquet` — the app re-downloads anything older than 23 hours (`MAX_AGE_H` in [app.py](app.py))

There is no test suite, linter, or build step — this is a single-file Streamlit app.

## Architecture

The entire app lives in [app.py](app.py). The flow is a strict linear pipeline driven by Streamlit's top-to-bottom re-execution model — each UI step gates the next via `if` checks on prior state (`purchases_df`, `selected_fund`, `actual_code`, `alt_code`).

### Data layer

NAV data is **not** fetched from an API at runtime. Two files are downloaded once from the [InertExpert2911/Mutual_Fund_Data](https://github.com/InertExpert2911/Mutual_Fund_Data) GitHub repo and cached locally:

- `fund_list.csv` (~5 MB) — scheme metadata: scheme code, scheme name, AMC, ISIN, latest NAV date
- `nav_history.parquet` (~100–200 MB) — full historical NAV time series for ~16k schemes

`load_data()` is wrapped in `@st.cache_resource` so it runs once per Streamlit process. It builds a `dict[scheme_code -> pd.Series(nav, index=DatetimeIndex)]` (`nav_index`) and **deletes the source DataFrame** to cut steady-state memory roughly in half (~500 MB instead of ~1 GB peak). All NAV lookups go through `nav_on_or_before()` which uses `pd.Series.asof()` for O(log n) date-based lookup against the sorted index — do not replace this with linear scans.

Column names from the upstream files are normalised to snake_case via fuzzy matching (e.g. `Scheme_Code`, `scheme code`, `Code` all map to `scheme_code`). Preserve this pattern when adding new columns — the upstream schema is not stable.

### Tradebook parsing

`parse_zerodha()` has two paths:

1. **Zerodha Coin CSV tradebook** — detected by the exact column set `{symbol, trade_date, quantity, price, trade_type}`. This is the happy path; columns are mapped directly with no guessing. ISIN is preserved here and is what powers auto-matching in Step 3.
2. **Legacy Excel exports** — fuzzy column detection fallback with header-row autodetection.

When extending parser support, prefer adding another exact-match branch over loosening the fuzzy fallback.

### Fund matching

Step 3 of the UI tries to auto-match the user's fund to the AMFI database via ISIN before falling back to manual search. The ISIN comes from the Zerodha CSV; the lookup checks every column in `fund_df` whose name contains "isin" (the upstream uses both `isin` and `ISIN_Div_Payout/Growth`-style columns). Manual search via `search_funds()` is a substring AND-match across whitespace-split tokens.

### Finance

`xirr()` uses `scipy.optimize.brentq` with bounds `[-0.9999, 50.0]`. Returns `None` (not raises) when cashflows have no sign change or the solver fails — callers must handle `None`.

`compute_scenario()` is the core comparison primitive: given purchases + a NAV series + current NAV, it returns invested/units/current value/XIRR plus a per-row `detail` DataFrame with `status ∈ {"ok", "no_nav"}`. Rows with `no_nav` (purchase predates fund launch) are excluded from totals but kept for the transaction-detail UI.

### Styling

A single `<style>` block at the top of [app.py](app.py) defines an IBM Plex–based design system with CSS custom properties. UI sections use `box-{blue,yellow,green,red}` for callouts and `step-label` for section headers. Prefer editing these classes over adding inline styles.
