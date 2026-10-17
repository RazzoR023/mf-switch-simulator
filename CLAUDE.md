# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -r requirements.txt          # openpyxl (Excel), zstandard (refresh job only)
python -m mfsim.refresh [--full]         # top up data/mfsim.sqlite (or rebuild it from the release)
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

`mfsim/refresh.py` keeps the database current from [captn3m0/historical-mf-data](https://github.com/captn3m0/historical-mf-data), an archive of AMFI's daily NAV exports (`data/YYYY/MM/DD.csv`, semicolon-separated, with category and AMC section lines between the rows), released daily as one SQLite file (`funds.db.zst`). A **full build** (no database, a `SCHEMA_VERSION` change, every `FULL_REBUILD_DAYS`, or `--full`) downloads the release, copies it into our schema with SQL in `data/mfsim.sqlite.new`, applies the last week of day files and `os.replace`s it over the live DB, so readers never see a partial file and a failed build keeps the old one. A **top-up** (every other run) lists the last `TOPUP_MONTHS` month folders through the GitHub API, downloads only day files whose git SHA isn't in `day_files`, and applies them to the live DB in one transaction. Both refuse a result with implausibly few rows.

Tables:
- `nav (code, day, nav)`, `WITHOUT ROWID` with primary key `(code, day)`. One scheme's history is one contiguous range read. `day` = days since 1970-01-01.
- `funds`: one row per scheme code, with NAV range, count and last NAV precomputed.
- `isins (isin, col_rank, row_rank, code)`: clustered for one-descent ISIN lookups. `col_rank` 0 = growth/IDCW payout ISIN, 1 = IDCW reinvestment; `row_rank` is always 0 (kept so lookups can order by it).
- `day_files (path, sha)`: the upstream day files already applied, with the git SHA they had.
- `funds_fts`: an FTS5 trigram index over the name columns. Search ANDs every query word as a substring. Words under 3 characters fall back to `LIKE` because trigrams can't match them.

`parse_day_file()` finds columns by header name because AMFI's header changed over the years (older files have `Scheme Name` and repurchase/sale price columns, newer ones `NAV Name`, `Plan`, `Option`). ISINs and NAV values get the same clean-ups the upstream release applies (`clean_isin`, `clean_nav`). AMFI has no separate scheme name, so `funds.name` is the plan-level name and `nav_name` stays NULL; AMC and category exist only for schemes seen in a day file since the last full build.

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
