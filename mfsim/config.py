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

# NAV data comes from https://github.com/InertExpert2911/Mutual_Fund_Data, refreshed daily
# upstream. The parquet is ~150 MB (Git LFS), the CSV ~5 MB.
PARQUET_URL = os.environ.get(
    "PARQUET_URL",
    "https://github.com/InertExpert2911/Mutual_Fund_Data/raw/main/mutual_fund_nav_history.parquet",
)
CSV_URL = os.environ.get(
    "CSV_URL",
    "https://raw.githubusercontent.com/InertExpert2911/Mutual_Fund_Data/main/mutual_fund_data.csv",
)

# Largest request body the API accepts (base64-encoded tradebooks).
MAX_BODY_BYTES = 25 * 1024 * 1024
