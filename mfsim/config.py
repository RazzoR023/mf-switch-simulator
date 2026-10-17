"""Paths and upstream URLs, overridable through the environment."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "mfsim.sqlite"

# The React build. In the Docker image it's copied next to the package.
WEB_DIR = Path(os.environ.get("WEB_DIR", ROOT / "web" / "dist"))

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8501"))

# NAV data comes from https://github.com/captn3m0/historical-mf-data: AMFI's daily NAV
# exports, one CSV per day under data/YYYY/MM/DD.csv (~1.2 MB), plus a daily release of all
# of them as one SQLite database (funds.db.zst, ~380 MB).
NAV_REPO = os.environ.get("NAV_REPO", "captn3m0/historical-mf-data")
GITHUB_API = "https://api.github.com"
# Optional: lifts GitHub's 60 requests/hour limit for unauthenticated API calls (a daily
# top-up makes about 4).
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or None

# The full release is downloaded when there's no database yet and then every this many days
# (0 = never again), to pick up upstream corrections older than the top-up window.
FULL_REBUILD_DAYS = int(os.environ.get("FULL_REBUILD_DAYS", "30"))
# Daily top-ups re-check this many months of day files (the current one included): upstream
# re-fetches the last 90 days from AMFI every day, so recent days can change.
TOPUP_MONTHS = int(os.environ.get("TOPUP_MONTHS", "3"))

# Largest request body the API accepts (base64-encoded tradebooks).
MAX_BODY_BYTES = 25 * 1024 * 1024
