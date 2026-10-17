# MF Switch Simulator

A self-hosted web app that answers one question: **"What would my returns have been if I had invested in a different mutual fund?"**

Upload your Zerodha Coin tradebook, pick an alternate fund, and get a side-by-side XIRR and returns comparison. Your real purchase and sale dates and amounts are replayed against the alternate fund's historical NAV.

NAV data comes from the [InertExpert2911/Mutual_Fund_Data](https://github.com/InertExpert2911/Mutual_Fund_Data) GitHub repository. A refresh job downloads it once a day into a local SQLite database. Comparisons don't call any external API.

---

## Features

- Parses Zerodha Coin CSV tradebooks (direct column mapping), with a fuzzy fallback for other CSV/Excel exports
- Combines several statements, dropping rows that appear in more than one file
- Clubs several funds into one "actual" portfolio
- Auto-matches each fund to the AMFI scheme list by ISIN, with a searchable manual override
- Includes sells: they're cash out on both sides, and only remaining units count towards today's value. A toggle treats every bought unit as still held instead.
- Shows the alternate fund's NAV range and flags transactions that predate it
- Side-by-side summary (XIRR, returns, current value), per-transaction detail and an Excel report
- Light and dark mode, works on a phone

## How it's built

```
browser ── React + Mantine UI (web/, built to static files)
   │  JSON
   ▼
python -m mfsim.server ── standard library only (http.server + sqlite3), openpyxl for Excel
   │  read-only
   ▼
data/mfsim.sqlite  ◄── python -m mfsim.refresh (daily; the only part that needs pyarrow)
```

The UI only presents: parsing, matching, the comparison maths and the Excel report all run in Python. The server keeps no per-user state, because the browser sends the parsed transactions back with each request. It idles at about 15 MB of RAM. The old Streamlit version held the full 22M-row NAV history in memory, about 600 MB.

| Path | What it is |
|---|---|
| `mfsim/refresh.py` | Downloads the fund list CSV and NAV parquet, builds `data/mfsim.sqlite`, swaps it in atomically. It skips the work when the upstream ETags haven't changed. |
| `mfsim/db.py` | Read-only queries: fund search, ISIN match, NAV series |
| `mfsim/tradebook.py` | Statement parsing and cross-file de-duplication |
| `mfsim/finance.py` | XIRR, using a port of scipy's Brent solver so results match the old app |
| `mfsim/compare.py` | The comparison and everything the results screen shows |
| `mfsim/report.py` | The Excel report |
| `mfsim/server.py` | The HTTP API, and serves the built UI |
| `web/` | The React app (Vite, TypeScript, Mantine) |

---

## Running it

### With Docker

```bash
docker build -t mfsim .
docker run -d --name mfsim -p 8501:8501 -v "$PWD/data:/data" mfsim
docker exec mfsim python -m mfsim.refresh     # first time: builds data/mfsim.sqlite (~2 min, ~450 MB)
```

Open http://localhost:8501. Run the refresh again, by hand or on a schedule, to pick up new NAVs.

### For development

Needs Python 3.11+ and Node 22+.

```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m mfsim.refresh                              # builds data/mfsim.sqlite
python -m mfsim.server                               # API (and built UI) on :8501

cd web && npm install && npm run dev                 # UI with hot reload on :5173, /api proxied to :8501
```

Tests: `python -m unittest discover -s tests`. Type-check the UI: `cd web && npm run typecheck`.

---

## Exporting your tradebook from Zerodha Coin

1. Log in to [coin.zerodha.com](https://coin.zerodha.com)
2. Go to **Portfolio** → **Transaction History**
3. Click **Download** and choose **CSV**
4. Upload the file (named like `tradebook-XXXXXX-MF.csv`) in the app

---

## Data sources

| Source | What it provides |
|---|---|
| [InertExpert2911/Mutual_Fund_Data](https://github.com/InertExpert2911/Mutual_Fund_Data) | Daily NAV history and fund metadata for 16,000+ Indian MF schemes |
| AMFI (via the above) | Scheme codes, ISINs, fund names, launch dates |

The banner at the top of the app shows the latest NAV date in the data. If the upstream repository stops updating, the banner turns yellow.

---

## Disclaimer

This tool is for **informational and analytical purposes only**. It replays past NAV history; the returns from a real switch would differ because of exit loads, STT, capital gains tax and execution timing. This is not investment advice.

---

## License

MIT
