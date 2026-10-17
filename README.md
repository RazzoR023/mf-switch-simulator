# MF Switch Simulator

A self-hosted web app that answers one question: **"What would my returns have been if I had invested in a different mutual fund?"**

Sign in, upload your Zerodha Coin tradebook once, pick an alternate fund, and get a side-by-side XIRR and returns comparison. Your real purchase and sale dates and amounts are replayed against the alternate fund's historical NAV.

NAV data is AMFI's official daily NAV export, as archived by [captn3m0/historical-mf-data](https://github.com/captn3m0/historical-mf-data). A refresh job keeps a local SQLite database current: one full download to start, then only each new day's file. Comparisons don't call any external API.

---

## Features

- Username/password accounts: each user's statements, fund matches and saved comparisons are stored on the server
- Parses Zerodha Coin CSV tradebooks (direct column mapping), with a fuzzy fallback for other CSV/Excel exports
- Combines several statements, dropping rows that appear in more than one file
- Clubs several funds into one "actual" portfolio
- Auto-matches each fund to the AMFI scheme list by ISIN, with a searchable manual override
- Includes sells: they're cash out on both sides, and only remaining units count towards today's value. A toggle treats every bought unit as still held instead.
- Shows the alternate fund's NAV range and flags transactions that predate it
- Side-by-side summary (XIRR, returns, current value), per-transaction detail and an Excel report
- Save comparisons and re-run them later with current NAVs
- Light and dark mode, works on a phone

## How it's built

```
browser ── React + Mantine UI (web/, built to static files)
   │  JSON
   ▼
python -m mfsim.server ── standard library only (http.server + sqlite3), openpyxl for Excel
   │  read-only                              │  read-write
   ▼                                         ▼
data/mfsim.sqlite                       state/users.sqlite (accounts, sessions,
   ▲                                      uploaded statements, matches, saved comparisons)
   └── python -m mfsim.refresh (daily top-up from AMFI day files; monthly full rebuild)
```

The UI only presents: parsing, matching, the comparison maths and the Excel report all run in Python. Uploaded files are parsed once and stored (original file plus parsed rows) in the users database, so comparisons run against what's on the server. The server idles at about 15 MB of RAM. The old Streamlit version held the full 22M-row NAV history in memory, about 600 MB.

| Path | What it is |
|---|---|
| `mfsim/refresh.py` | Full build: downloads the upstream release (`funds.db.zst`, ~380 MB), converts it into `data/mfsim.sqlite` and swaps it in atomically. Daily: applies only new or changed AMFI day files (~1.2 MB each). |
| `mfsim/db.py` | Read-only queries: fund search, ISIN match, NAV series |
| `mfsim/tradebook.py` | Statement parsing and cross-file de-duplication |
| `mfsim/finance.py` | XIRR, using a port of scipy's Brent solver so results match the old app |
| `mfsim/compare.py` | The comparison and everything the results screen shows |
| `mfsim/report.py` | The Excel report |
| `mfsim/store.py` | Accounts (PBKDF2 password hashes), login sessions, uploads, fund matches and saved comparisons |
| `mfsim/users.py` | Command-line account management |
| `mfsim/server.py` | The HTTP API, and serves the built UI |
| `web/` | The React app (Vite, TypeScript, Mantine) |

---

## Running it

### With Docker

```bash
docker build -t mfsim .
docker run -d --name mfsim -p 8501:8501 -v "$PWD/data:/data" -v "$PWD/state:/state" mfsim
docker exec mfsim python -m mfsim.refresh     # first time: builds data/mfsim.sqlite (~8 min incl. download, ~750 MB)
```

Open http://localhost:8501 and create an account. Run the refresh again, by hand or on a schedule, to pick up new NAVs.

### For development

Needs Python 3.11+ and Node 22+.

```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m mfsim.refresh                              # builds data/mfsim.sqlite
python -m mfsim.server                               # API (and built UI) on :8501

cd web && npm install && npm run dev                 # UI with hot reload on :5173, /api proxied to :8501
```

Data lands in `data/` and `state/` next to the code (`DATA_DIR`, `STATE_DIR` override them). Tests: `python -m unittest discover -s tests`. Type-check the UI: `cd web && npm run typecheck`.

---

## Accounts

The login page offers **Create account** unless the server runs with `ALLOW_SIGNUP=false`. Usernames are 3–32 letters, digits, `.`, `-` or `_` (case-insensitive); passwords need 8+ characters. Sessions are an HttpOnly cookie that lasts `SESSION_DAYS` (30). After 10 failed logins for a username in 15 minutes, logins for it are refused for a while.

There's no email or password reset by mail. Manage accounts from the command line instead (`docker exec -it mfsim ...` in Docker):

```bash
python -m mfsim.users list
python -m mfsim.users add NAME        # prompts for a password
python -m mfsim.users passwd NAME     # resets it and signs NAME out everywhere
python -m mfsim.users delete NAME     # removes the account and everything it uploaded
```

Put the app behind HTTPS (a reverse proxy that sets `X-Forwarded-Proto: https`) so the session cookie is marked `Secure`.

---

## Exporting your tradebook from Zerodha Coin

1. Log in to [coin.zerodha.com](https://coin.zerodha.com)
2. Go to **Portfolio** → **Transaction History**
3. Click **Download** and choose **CSV**
4. Upload the file (named like `tradebook-XXXXXX-MF.csv`) on the **Statements** page. It stays in your account; add newer files as you go.

---

## Data sources

| Source | What it provides |
|---|---|
| [AMFI](https://www.amfiindia.com/net-asset-value) via [captn3m0/historical-mf-data](https://github.com/captn3m0/historical-mf-data) | Every NAV AMFI has published since 2006 for ~38,000 scheme codes (closed schemes included), with ISINs, AMC and category |
| AMFI (via the above) | Scheme codes, ISINs, fund names, launch dates |

The badge in the app's header shows the latest NAV date in the data. If the upstream repository stops updating, it turns yellow.

---

## Disclaimer

This tool is for **informational and analytical purposes only**. It replays past NAV history; the returns from a real switch would differ because of exit loads, STT, capital gains tax and execution timing. This is not investment advice.

---

## License

MIT
