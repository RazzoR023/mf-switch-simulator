# MF Switch Simulator

A self-hosted Streamlit app that answers one question: **"What would my returns have been if I had invested in a different mutual fund?"**

Upload your Zerodha Coin tradebook, pick an alternate fund, and get a side-by-side XIRR and returns comparison — using your real purchase dates and amounts replayed against the alternate fund's historical NAV.

All NAV data is sourced from the [InertExpert2911/Mutual_Fund_Data](https://github.com/InertExpert2911/Mutual_Fund_Data) GitHub repository and cached locally. No external API calls at runtime.

---

## Features

- Parses Zerodha Coin CSV tradebook (direct column mapping, no guessing)
- Auto-matches your fund to AMFI database via ISIN — no manual lookup needed
- Shows alternate fund NAV data availability range and flags missing dates
- Computes XIRR and total returns for both actual and hypothetical scenarios
- Side-by-side comparison table with green/red highlighting
- Transaction-level detail with missing NAV warnings per row
- Exports a full Excel report (Summary + Transactions sheets)
- NAV database auto-refreshes daily from GitHub; shows actual data freshness from `Latest_NAV_Date`

---

## Prerequisites

Before you begin, make sure you have the following installed on your machine:

### 1. Python 3.11 or higher

Check if you have it:
```bash
python3 --version
```

If not, download it from [python.org/downloads](https://www.python.org/downloads/). During installation on Windows, check **"Add Python to PATH"**.

### 2. pip (Python package manager)

pip comes bundled with Python. Verify it works:
```bash
pip --version
```

---

## Installation

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-username/mf-switch-simulator.git
cd mf-switch-simulator
```

### Step 2 — (Recommended) Create a virtual environment

This keeps the app's dependencies isolated from your system Python.

```bash
# Create the environment
python3 -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

You'll see `(venv)` appear in your terminal prompt when it's active.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs Streamlit, pandas, scipy, and the other required libraries. It may take a minute or two.

---

## Running the App

```bash
streamlit run app.py
```

Streamlit will start a local web server and open the app in your browser automatically. If it doesn't, navigate to:

```
http://localhost:8501
```

### First run

On first launch, the app will download two files from GitHub:

| File | Size | Purpose |
|---|---|---|
| `fund_list.csv` | ~5 MB | Fund metadata, scheme codes, ISINs |
| `nav_history.parquet` | ~100–200 MB | Full historical NAV for all funds |

This is a one-time download. Subsequent startups use the cached files and complete in a few seconds. The data refreshes automatically if the cached files are older than 23 hours.

> **RAM usage:** Loading the NAV history into memory requires approximately **500–600 MB RAM** at steady state, with a peak of ~1 GB during startup. Ensure your machine has at least 2 GB of available RAM.

---

## Exporting Your Tradebook from Zerodha Coin

1. Log in to [coin.zerodha.com](https://coin.zerodha.com)
2. Go to **Portfolio** → **Transaction History** (or **Orders**)
3. Click **Download** and select **CSV**
4. The file will be named something like `tradebook-XXXXXX-MF.csv`

Upload this file directly in the app.

---

## Project Structure

```
mf-switch-simulator/
├── app.py               # Main Streamlit application
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── fund_list.csv        # Auto-downloaded on first run (gitignored)
└── nav_history.parquet  # Auto-downloaded on first run (gitignored)
```

Add the following to your `.gitignore` to avoid committing the large data files:

```
fund_list.csv
nav_history.parquet
```

---

## Data Sources

| Source | What it provides |
|---|---|
| [InertExpert2911/Mutual_Fund_Data](https://github.com/InertExpert2911/Mutual_Fund_Data) | Daily NAV history + fund metadata for 16,000+ Indian MF schemes, updated daily via Kaggle |
| AMFI (via above) | Scheme codes, ISINs, fund names, launch dates |

---

## Disclaimer

This tool is for **informational and analytical purposes only**. Past NAV history is used for simulation — actual returns from a real switch would differ due to exit loads, STT, capital gains tax, and execution timing. This is not investment advice.

---

## License

MIT
