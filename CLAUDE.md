# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -r requirements.txt          # openpyxl (Excel), pyarrow (refresh job only)
python -m mfsim.refresh [--force]        # build/refresh data/mfsim.sqlite from upstream
python -m mfsim.server                   # API + built UI on :8501 (DATA_DIR, WEB_DIR, PORT env vars)
python -m unittest discover -s tests     # unit tests, no network

cd web && npm install
npm run dev                              # UI on :5173, proxies /api to :8501
npm run build                            # type-check + build to web/dist (served by mfsim.server)
```

`docker build .` produces one image that runs either `python -m mfsim.server` (the default) or `python -m mfsim.refresh`.

## Architecture

A Python server (standard library only: `http.server`, `sqlite3`) plus a React/Mantine UI in `web/`. The split is deliberate: **all logic lives in Python** (parsing, matching, the comparison maths, the Excel report), and the UI only presents what the API returns and formats numbers. Keep new features in that shape. The server is stateless: the browser holds the parsed transactions and posts them back with each `/api/compare` or `/api/report` call.

Keep the runtime lean: the server process must not import pandas, numpy, scipy or pyarrow. Low RAM (~15 MB idle) is the point of this design. openpyxl is imported lazily, only for `.xlsx` uploads and the report.

### Data layer

`mfsim/refresh.py` downloads two upstream files from [InertExpert2911/Mutual_Fund_Data](https://github.com/InertExpert2911/Mutual_Fund_Data) (fund list CSV ~5 MB, NAV parquet ~150 MB). It builds `data/mfsim.sqlite.new` and `os.replace`s it over the live DB, so readers never see a partial file and a failed run keeps the old one. It skips work when both ETags are unchanged and refuses a result with implausibly few rows.

Tables:
- `nav (code, day, nav)`, `WITHOUT ROWID` with primary key `(code, day)`. One scheme's history is one contiguous range read. `day` = days since 1970-01-01.
- `funds`: one row per scheme code, with NAV range, count and last NAV precomputed.
- `isins (isin, col_rank, row_rank, code)`: clustered for one-descent ISIN lookups. The ordering reproduces the old app's "first ISIN column, then first row" matching.
- `funds_fts`: an FTS5 trigram index over the name columns. Search ANDs every query word as a substring. Words under 3 characters fall back to `LIKE` because trigrams can't match them.

The upstream schema isn't stable, so column names are matched fuzzily (`_match_fund_columns`, `_match_nav_columns`), first match wins. Preserve that when adding columns.

`db.Db` opens a fresh read-only connection per request, so a swapped-in database is picked up without a restart. `NavSeries.on_or_before()` is a binary search (`bisect`). Don't replace it with a scan.

### Tradebook parsing

`tradebook.parse_file()` has two paths:

1. **Zerodha Coin tradebook**, detected by the exact column set `{symbol, trade_date, quantity, price, trade_type}`. Columns are mapped directly; the ISIN is kept and powers auto-matching.
2. **Fuzzy fallback** for other CSV/XLSX exports: header-row detection for Excel, keyword-based buy/sell detection, day-first dates.

When extending parser support, prefer adding another exact-match branch over loosening the fuzzy fallback. `dedupe()` removes rows repeated across files, by `trade_id` when every row has one.

### Finance

`finance.xirr()` is a port of `scipy.optimize.brentq` (same tolerances) over `[-0.9999, 50.0]`. It returns `None`, not an exception, when cashflows have no sign change or there's no root, so callers must handle `None`.

`compare.compute_scenario()` replays transactions in the alternate fund. `compute_scenario_pooled()` replays them in each fund actually bought. Buys add units (cash in), sells remove units (cash out). Rows before a fund's first NAV get `status="no_nav"`: they're kept in the detail table and left out of totals and XIRR. Alternate-side units may go negative when a sell exceeds what the alternate was worth; those show up in `negative_events`. `compare.run()` assembles everything the results screen shows (metrics, verdict, detail).

### UI

`web/src/App.tsx` holds the step-by-step state: upload → pick funds → match → alternate → run. Components live in `web/src/components/`, number formatting in `web/src/format.ts` (en-IN grouping), and the API types in `web/src/types.ts`. Keep those types in sync with what `compare.py` and `server.py` return. The theme (`web/src/theme.ts`) keeps the original IBM Plex look, with the fonts self-hosted via @fontsource.
