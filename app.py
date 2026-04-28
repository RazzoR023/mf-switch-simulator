import streamlit as st
import pandas as pd
import numpy as np
import requests
import io
import time
from datetime import datetime, date
from pathlib import Path
from scipy.optimize import brentq

# ─── Config ──────────────────────────────────────────────────────────────────
PARQUET_PATH  = Path("nav_history.parquet")
CSV_PATH      = Path("fund_list.csv")
PARQUET_URL   = "https://github.com/InertExpert2911/Mutual_Fund_Data/raw/main/mutual_fund_nav_history.parquet"
CSV_URL       = "https://raw.githubusercontent.com/InertExpert2911/Mutual_Fund_Data/main/mutual_fund_data.csv"
MAX_AGE_H     = 23

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="MF Switch Simulator", page_icon="📊", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Serif:ital,wght@0,400;1,400&display=swap');
:root {
  --bg:#f7f6f3; --surface:#ffffff; --ink:#141414; --muted:#5c5c5c;
  --border:#dedad4; --accent:#1a56db; --green:#15803d; --red:#b91c1c;
  --yellow-bg:#fefce8; --yellow-border:#fde047;
  --blue-bg:#eff6ff; --blue-border:#bfdbfe;
}
html,body,[class*="css"]{font-family:'IBM Plex Sans',sans-serif;background:var(--bg);color:var(--ink);}
.stApp{background:var(--bg);}

/* header */
.page-header{border-bottom:2px solid var(--ink);padding-bottom:1.25rem;margin-bottom:2rem;}
.page-header h1{font-family:'IBM Plex Serif',serif;font-size:2.4rem;letter-spacing:-.02em;margin:0;line-height:1.15;}
.page-header .mono{font-family:'IBM Plex Mono',monospace;font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-top:.4rem;}

/* section labels */
.step-label{font-family:'IBM Plex Mono',monospace;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--border);padding-bottom:.35rem;margin:1.6rem 0 .9rem;}

/* callout boxes */
.box{border-radius:6px;padding:.8rem 1rem;font-size:.84rem;margin:.6rem 0;}
.box-blue{background:var(--blue-bg);border:1px solid var(--blue-border);color:#1e40af;}
.box-yellow{background:var(--yellow-bg);border:1px solid var(--yellow-border);color:#713f12;}
.box-green{background:#f0fdf4;border:1px solid #bbf7d0;color:#14532d;}
.box-red{background:#fef2f2;border:1px solid #fecaca;color:#7f1d1d;}

/* date range badge */
.range-badge{display:inline-block;background:#f1f5f9;border:1px solid #cbd5e1;border-radius:4px;font-family:'IBM Plex Mono',monospace;font-size:.75rem;padding:.25rem .7rem;margin:.3rem 0;}

/* summary table */
.summary-table{width:100%;border-collapse:collapse;font-size:.88rem;margin-top:.5rem;}
.summary-table th{font-family:'IBM Plex Mono',monospace;font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);border-bottom:2px solid var(--ink);padding:.5rem .75rem;text-align:left;}
.summary-table td{padding:.6rem .75rem;border-bottom:1px solid var(--border);}
.summary-table tr:last-child td{border-bottom:none;}
.summary-table .metric-col{color:var(--muted);font-size:.82rem;}
.better{color:var(--green);font-weight:600;}
.worse{color:var(--red);font-weight:600;}
.neutral{color:var(--ink);}
.winner-col{background:#f0fdf4;}

/* stButton */
.stButton>button{background:var(--ink)!important;color:#fff!important;border:none!important;border-radius:5px!important;font-family:'IBM Plex Sans',sans-serif!important;font-weight:500!important;padding:.45rem 1.4rem!important;}
.stButton>button:hover{opacity:.8!important;}

/* labels */
.stSelectbox label,.stTextInput label,.stFileUploader label,.stNumberInput label{
  font-family:'IBM Plex Mono',monospace!important;font-size:.68rem!important;
  letter-spacing:.08em!important;text-transform:uppercase!important;color:var(--muted)!important;}

hr{border-color:var(--border);margin:1.6rem 0;}

/* native progress bar — match accent ink */
.stProgress > div > div > div > div{background-color:var(--ink)!important;}
.stProgress > div > div > div{background-color:var(--border)!important;border-radius:3px!important;}
.stProgress p,.stProgress div[data-testid="stProgressLabel"]{
  font-family:'IBM Plex Mono',monospace!important;font-size:.72rem!important;
  letter-spacing:.04em!important;color:var(--muted)!important;}

/* native spinner text */
.stSpinner > div{font-family:'IBM Plex Mono',monospace!important;font-size:.72rem!important;
  letter-spacing:.08em!important;text-transform:uppercase!important;color:var(--muted)!important;}
.stSpinner svg{stroke:var(--ink)!important;}

/* small caption used under progress bars */
[data-testid="stCaptionContainer"]{font-family:'IBM Plex Mono',monospace!important;
  font-size:.7rem!important;color:var(--muted)!important;letter-spacing:.04em!important;}

/* phased loader pill */
.phase{display:flex;align-items:center;gap:.6rem;padding:.7rem 1rem;
  background:#fff;border:1px solid var(--border);border-radius:6px;margin:.5rem 0;
  font-family:'IBM Plex Mono',monospace;font-size:.78rem;color:var(--ink);}
.phase .dot{width:8px;height:8px;border-radius:50%;background:var(--ink);
  animation:pulse 1.2s ease-in-out infinite;}
.phase .label{flex:1;}
.phase .detail{color:var(--muted);font-size:.72rem;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.3;}}
</style>
""", unsafe_allow_html=True)


# ─── Data download & caching ─────────────────────────────────────────────────

def is_stale(path: Path) -> bool:
    if not path.exists():
        return True
    return (time.time() - path.stat().st_mtime) / 3600 > MAX_AGE_H


def download_file(url: str, dest: Path, label: str):
    r = requests.get(url, stream=True, timeout=300)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    bar  = st.progress(0.0, text=f"Starting {label}…")
    info = st.empty()
    chunks, downloaded = [], 0
    start = time.time()
    for chunk in r.iter_content(chunk_size=512 * 1024):
        chunks.append(chunk)
        downloaded += len(chunk)
        elapsed = max(time.time() - start, 0.001)
        speed   = downloaded / elapsed / 1024 / 1024  # MB/s
        mb_done = downloaded / 1024 / 1024
        if total:
            pct      = min(downloaded / total, 1.0)
            mb_total = total / 1024 / 1024
            eta_s    = (total - downloaded) / (downloaded / elapsed) if downloaded else 0
            bar.progress(
                pct,
                text=f"{label}: {mb_done:.1f} / {mb_total:.1f} MB  ({pct*100:.0f}%)",
            )
            info.caption(f"⏱ {speed:.2f} MB/s · ETA {eta_s:.0f}s")
        else:
            bar.progress(0.0, text=f"{label}: {mb_done:.1f} MB downloaded (size unknown)…")
            info.caption(f"⏱ {speed:.2f} MB/s")
    dest.write_bytes(b"".join(chunks))
    bar.empty()
    info.empty()


def ensure_data_files():
    """
    Download any missing/stale data files BEFORE the cached loader runs.

    Kept outside @st.cache_resource so the progress bar and status messages
    render in the live page (UI created inside cached functions can be hidden
    or stripped by Streamlit's caching layer).
    """
    needed = []
    if is_stale(CSV_PATH):
        needed.append((CSV_URL,     CSV_PATH,     "Fund list CSV",      "~5 MB"))
    if is_stale(PARQUET_PATH):
        needed.append((PARQUET_URL, PARQUET_PATH, "NAV history",        "~100–200 MB"))

    if not needed:
        return

    st.markdown(
        '<div class="box box-blue">'
        '<strong>First-time setup</strong> &nbsp;·&nbsp; downloading mutual fund data from GitHub. '
        'This is a one-time operation — subsequent launches will use the cached files and start in seconds.'
        '</div>',
        unsafe_allow_html=True,
    )

    for i, (url, dest, label, size_hint) in enumerate(needed, start=1):
        st.markdown(
            f'<div class="step-label">File {i} of {len(needed)} · {label} ({size_hint})</div>',
            unsafe_allow_html=True,
        )
        try:
            download_file(url, dest, label)
            st.markdown(
                f'<div class="box box-green">✓ {label} downloaded ({dest.stat().st_size/1024/1024:.1f} MB)</div>',
                unsafe_allow_html=True,
            )
        except Exception as e:
            st.markdown(
                f'<div class="box box-red">✗ Failed to download {label}: {e}</div>',
                unsafe_allow_html=True,
            )
            st.stop()


# Module-level singleton — survives Streamlit reruns within one process, like
# @st.cache_resource, but without recording/replaying any Streamlit UI calls
# (which is what the @st.cache_resource version did to the phase placeholder).
_DATA_CACHE: dict = {}


def load_data(_phase=lambda *a, **kw: None):
    """
    Returns:
        fund_df   : DataFrame of scheme metadata (Scheme_Code, Scheme_Name, AMC, …)
        nav_index : dict[scheme_code -> pd.Series(NAV, index=DatetimeIndex, sorted)]

    Assumes ensure_data_files() has already run — files are present on disk.
    `_phase(label, detail="")` is a callback for status updates, called only on
    first load (cache miss).
    """
    if "data" in _DATA_CACHE:
        return _DATA_CACHE["data"]

    def _norm(name: str) -> str:
        """Lowercase + collapse spaces/dashes/dots to underscores for fuzzy matching."""
        return (
            name.strip().lower()
            .replace(" ", "_").replace("-", "_").replace(".", "_")
        )

    # ── Load & normalise CSV ─────────────────────────────────────────────────
    csv_mb = CSV_PATH.stat().st_size / 1024 / 1024
    _phase("Reading fund list CSV", f"{csv_mb:.1f} MB")
    fund_df = pd.read_csv(CSV_PATH, low_memory=False)
    fund_df.columns = [c.strip() for c in fund_df.columns]

    # Normalise column names to snake_case — first match wins per target name
    # to avoid collapsing two source columns into the same name (which would
    # turn fund_df["scheme_name"] into a 2-column DataFrame and break .str ops)
    rename: dict[str, str] = {}
    taken: set[str] = set()
    def _claim(src, target):
        if target not in taken:
            rename[src] = target
            taken.add(target)
    for c in fund_df.columns:
        lc = _norm(c)
        if ("scheme" in lc and "code" in lc) or lc in ("code", "schemecode"):
            _claim(c, "scheme_code")
        elif "scheme" in lc and "name" in lc:
            _claim(c, "scheme_name")
        elif lc == "amc" or "amc" in lc:
            _claim(c, "amc")
        elif "nav" in lc and "name" not in lc and "date" not in lc:
            _claim(c, "nav_current")
        elif "launch" in lc:
            _claim(c, "launch_date")
    fund_df = fund_df.rename(columns=rename)
    # Belt-and-braces: drop any remaining duplicate columns (keeps first occurrence)
    fund_df = fund_df.loc[:, ~fund_df.columns.duplicated()]
    fund_df["scheme_code"] = pd.to_numeric(fund_df.get("scheme_code", pd.Series(dtype=int)), errors="coerce")
    fund_df = fund_df.dropna(subset=["scheme_code"])
    fund_df["scheme_code"] = fund_df["scheme_code"].astype(int)

    # ── Load & normalise Parquet ─────────────────────────────────────────────
    parquet_mb = PARQUET_PATH.stat().st_size / 1024 / 1024
    _phase("Reading NAV history parquet", f"{parquet_mb:.0f} MB on disk · expanding to ~500 MB in RAM")
    nav_df = pd.read_parquet(PARQUET_PATH)
    # Upstream sometimes stores scheme_code as the index — promote it to a column
    if nav_df.index.name or (isinstance(nav_df.index, pd.MultiIndex) and nav_df.index.names):
        nav_df = nav_df.reset_index()
    nav_df.columns = [str(c).strip() for c in nav_df.columns]

    col_map: dict[str, str] = {}
    nav_taken: set[str] = set()
    def _nav_claim(src, target):
        if target not in nav_taken:
            col_map[src] = target
            nav_taken.add(target)
    for c in nav_df.columns:
        lc = _norm(c)
        if ("scheme" in lc and "code" in lc) or lc in ("code", "schemecode"):
            _nav_claim(c, "scheme_code")
        elif "date" in lc:
            _nav_claim(c, "date")
        elif lc == "nav" or lc.endswith("_nav") or lc.startswith("nav_") or "net_asset" in lc:
            _nav_claim(c, "nav")
    nav_df = nav_df.rename(columns=col_map)
    nav_df = nav_df.loc[:, ~nav_df.columns.duplicated()]

    required = {"scheme_code", "date", "nav"}
    missing  = required - set(nav_df.columns)
    if missing:
        st.error(
            f"NAV parquet is missing required columns {sorted(missing)}.\n\n"
            f"Columns found in the file: {list(nav_df.columns)}\n\n"
            f"The upstream schema may have changed. Update the column matching "
            f"logic in load_data() to map the new names."
        )
        st.stop()

    _phase("Normalising columns & coercing types", f"{len(nav_df):,} rows")
    nav_df["scheme_code"] = pd.to_numeric(nav_df["scheme_code"], errors="coerce")
    nav_df["nav"]         = pd.to_numeric(nav_df["nav"],         errors="coerce")
    nav_df["date"]        = pd.to_datetime(nav_df["date"],       errors="coerce", dayfirst=True)
    nav_df = nav_df.dropna(subset=["scheme_code", "date", "nav"])
    nav_df["scheme_code"] = nav_df["scheme_code"].astype(int)

    _phase("Sorting NAV history by scheme & date", f"{len(nav_df):,} rows")
    nav_df = nav_df.sort_values(["scheme_code", "date"])

    # Build lookup: scheme_code → Series(nav, index=date) — sorted for .asof()
    n_schemes = nav_df["scheme_code"].nunique()
    _phase("Building per-scheme NAV index", f"{n_schemes:,} schemes")
    nav_index: dict[int, pd.Series] = {}
    for code, grp in nav_df.groupby("scheme_code", sort=False):
        s = grp.set_index("date")["nav"].sort_index()
        s = s[~s.index.duplicated(keep="last")]
        nav_index[int(code)] = s

    _phase("Freeing intermediate memory")
    del nav_df  # free ~480 MB — dict of Series holds the same data

    # Latest NAV date from CSV (actual data freshness check)
    latest_nav_date = None
    if "latest_nav_date" in fund_df.columns:
        latest_nav_date = pd.to_datetime(fund_df["latest_nav_date"], errors="coerce").max()
    elif "Latest_NAV_Date" in fund_df.columns:
        latest_nav_date = pd.to_datetime(fund_df["Latest_NAV_Date"], errors="coerce").max()

    _DATA_CACHE["data"] = (fund_df, nav_index, latest_nav_date)
    return _DATA_CACHE["data"]


# ─── Lookup helpers ───────────────────────────────────────────────────────────

def nav_on_or_before(series: pd.Series, target: date) -> float | None:
    """Binary search using pandas .asof() — O(log n)."""
    ts = pd.Timestamp(target)
    if ts < series.index[0]:
        return None
    val = series.asof(ts)
    return None if pd.isna(val) else float(val)


def fund_date_range(series: pd.Series) -> tuple[date, date]:
    return series.index[0].date(), series.index[-1].date()


def search_funds(fund_df: pd.DataFrame, query: str, top: int = 20):
    words = query.strip().lower().split()
    mask  = pd.Series([True] * len(fund_df), index=fund_df.index)
    for w in words:
        mask &= fund_df["scheme_name"].str.lower().str.contains(w, na=False)
    return fund_df[mask].head(top)


# ─── Finance ─────────────────────────────────────────────────────────────────

def xirr(cashflows: list[float], dates: list) -> float | None:
    if len(cashflows) < 2:
        return None
    if not any(c > 0 for c in cashflows) or not any(c < 0 for c in cashflows):
        return None
    base  = min(dates)
    years = [(d - base).days / 365.0 for d in dates]
    def npv(r):
        return sum(cf / (1 + r) ** t for cf, t in zip(cashflows, years))
    try:
        return brentq(npv, -0.9999, 50.0, maxiter=2000)
    except Exception:
        return None


# ─── Zerodha parser ──────────────────────────────────────────────────────────

def parse_zerodha(uploaded) -> pd.DataFrame | None:
    """
    Supports Zerodha Coin tradebook CSV format:
      symbol, isin, trade_date, exchange, segment, series,
      trade_type, auction, quantity, price, trade_id, order_id, order_execution_time

    Also attempts to parse legacy Excel exports with fuzzy column detection.
    """
    fname = uploaded.name.lower()

    try:
        if fname.endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            # Excel: scan for header row
            raw = pd.read_excel(uploaded, header=None, sheet_name=0)
            header_row = None
            for i, row in raw.iterrows():
                vals = [str(v).lower() for v in row.values]
                if any("date" in v for v in vals) and any("scheme" in v or "nav" in v or "symbol" in v for v in vals):
                    header_row = i
                    break
            if header_row is None:
                st.error("Could not detect header row. First 15 rows:")
                st.dataframe(raw.head(15))
                return None
            df = pd.read_excel(uploaded, header=header_row, sheet_name=0)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return None

    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    cols = set(df.columns)

    # ── Zerodha CSV tradebook (exact columns) ────────────────────────────────
    if {"symbol", "trade_date", "quantity", "price", "trade_type"}.issubset(cols):
        df = df.rename(columns={"symbol": "scheme_name", "trade_date": "date"})
        df["date"]      = pd.to_datetime(df["date"], errors="coerce")
        df["units"]     = pd.to_numeric(df["quantity"], errors="coerce").abs()
        df["nav"]       = pd.to_numeric(df["price"],    errors="coerce")
        df["amount"]    = df["units"] * df["nav"]
        df["direction"] = df["trade_type"].astype(str).str.lower().str.strip()
        df = df.dropna(subset=["date", "amount"])
        out = df[df["direction"].isin(["buy", "sell"])]
        if out.empty:
            st.warning("No buy/sell transactions found — showing all rows.")
            out = df
        return out.reset_index(drop=True)

    # ── Fuzzy fallback for Excel exports ────────────────────────────────────
    col_map = {}
    for c in df.columns:
        lc = c.lower()
        if "date" in lc:                           col_map[c] = "date"
        elif "scheme" in lc or "fund name" in lc: col_map[c] = "scheme_name"
        elif "transaction" in lc or "type" in lc: col_map[c] = "txn_type"
        elif "unit" in lc:                         col_map[c] = "units"
        elif "nav" in lc or "price" in lc:        col_map[c] = "nav"
        elif "amount" in lc or "value" in lc:     col_map[c] = "amount"
    df = df.rename(columns=col_map)

    if "amount" not in df.columns and {"units", "nav"}.issubset(df.columns):
        df["amount"] = pd.to_numeric(df["units"], errors="coerce") * pd.to_numeric(df["nav"], errors="coerce")

    missing = {"date", "scheme_name", "amount"} - set(df.columns)
    if missing:
        st.error(f"Missing columns {missing}. Found: {list(df.columns)}")
        st.dataframe(df.head(8))
        return None

    df["date"]   = pd.to_datetime(df["date"],   errors="coerce", dayfirst=True)
    df["amount"] = pd.to_numeric(df["amount"],   errors="coerce")
    df = df.dropna(subset=["date", "amount"])

    buy_kw  = ["purchase", "buy", "sip", "lumpsum", "invest", "switch in"]
    sell_kw = ["redeem", "redemption", "sell", "switch out", "withdraw"]

    if "txn_type" in df.columns:
        txn = df["txn_type"].astype(str).str.lower()
        is_buy  = txn.str.contains("|".join(buy_kw),  na=False)
        is_sell = txn.str.contains("|".join(sell_kw), na=False)
        df["direction"] = pd.Series([None] * len(df), index=df.index, dtype=object)
        df.loc[is_buy,  "direction"] = "buy"
        df.loc[is_sell, "direction"] = "sell"
        # Unknown txn_type → infer from amount sign
        unknown = df["direction"].isna()
        df.loc[unknown & (df["amount"] < 0), "direction"] = "sell"
        df.loc[unknown & (df["amount"] > 0), "direction"] = "buy"
        out = df[df["direction"].isin(["buy", "sell"])].copy()
    else:
        # No txn_type — infer purely from amount sign
        out = df.copy()
        out["direction"] = np.where(out["amount"] >= 0, "buy", "sell")

    # Normalize amount + units to positive; direction carries the sign semantics
    out["amount"] = out["amount"].abs()
    if "units" in out.columns:
        out["units"] = pd.to_numeric(out["units"], errors="coerce").abs()

    return out.reset_index(drop=True)


# ─── Scenario computation ────────────────────────────────────────────────────

def compute_scenario(
    purchases: pd.DataFrame,
    nav_series: pd.Series,
    current_nav: float,
    label: str,
) -> dict:
    """
    Single-NAV-series scenario, used for the alternate-fund side. Honors
    `direction`: buys add units (cashflow -amount), sells remove units
    (cashflow +amount). Tracks a running unit balance to flag rows where
    the alt fund's units would go negative (sell exceeded available value).
    """
    today = date.today()
    purchases = purchases.sort_values("date").reset_index(drop=True)

    rows = []
    running_units = 0.0
    negative_events = []
    for _, r in purchases.iterrows():
        d         = r["date"].date()
        amt       = abs(float(r["amount"]))
        direction = r.get("direction", "buy")
        if direction not in ("buy", "sell"):
            direction = "buy"
        nav = nav_on_or_before(nav_series, d)
        if nav:
            row_units    = amt / nav
            signed_units = row_units if direction == "buy" else -row_units
            running_units += signed_units
            if direction == "sell" and running_units < 0:
                negative_events.append({"date": d, "running": running_units, "amount": amt})
        else:
            signed_units = None
        rows.append({
            "date":      d,
            "direction": direction,
            "amount":    amt,
            "nav":       nav,
            "units":     signed_units,
            "status":    "ok" if nav else "no_nav",
        })

    df_rows = pd.DataFrame(rows)
    matched = df_rows[df_rows["status"] == "ok"]
    buys    = matched[matched["direction"] == "buy"]
    sells   = matched[matched["direction"] == "sell"]

    total_bought    = float(buys["amount"].sum())
    total_sold      = float(sells["amount"].sum())
    net_invested    = total_bought - total_sold
    remaining_units = float(matched["units"].sum())  # signed
    current_value   = remaining_units * current_nav
    total_proceeds  = current_value + total_sold
    absolute_ret    = total_proceeds - total_bought
    return_pct      = (absolute_ret / total_bought * 100) if total_bought else 0

    # Cashflows: buys negative, sells positive, plus terminal current_value
    cf_dates   = []
    cf_amounts = []
    for _, r in matched.iterrows():
        cf_dates.append(r["date"])
        cf_amounts.append(-r["amount"] if r["direction"] == "buy" else r["amount"])
    cf_dates.append(today)
    cf_amounts.append(current_value)
    xi = xirr(
        cf_amounts,
        [datetime.combine(d, datetime.min.time()) for d in cf_dates],
    )

    return {
        "label":           label,
        "nav_series":      nav_series,
        "current_nav":     current_nav,
        "total_bought":    total_bought,
        "total_sold":      total_sold,
        "total_invested":  net_invested,    # alias (back-compat for older callers)
        "net_invested":    net_invested,
        "total_units":     remaining_units,
        "current_value":   current_value,
        "total_proceeds":  total_proceeds,
        "absolute_ret":    absolute_ret,
        "return_pct":      return_pct,
        "xirr":            xi,
        "detail":          df_rows,
        "matched":         len(matched),
        "skipped":         len(df_rows) - len(matched),
        "n_buys":          len(buys),
        "n_sells":         len(sells),
        "negative_events": negative_events,
    }


def compute_scenario_pooled(
    purchases: pd.DataFrame,
    name_to_series: dict,
    label: str = "Actual (pooled)",
) -> dict:
    """
    Pooled-actual scenario: each purchase row is valued in its own fund's NAV.
    Honors `direction` per row: buys add units, sells remove units.
    Per-fund running balance is tracked; the actual side typically shouldn't
    go negative (user can't have sold more than they owned), but if the data
    says otherwise we record it for transparency.
    """
    today = date.today()
    purchases = purchases.sort_values("date").reset_index(drop=True)

    rows    = []
    running = {}   # fund -> running unit balance
    negative_events = []
    for _, r in purchases.iterrows():
        fund      = r["scheme_name"]
        d         = r["date"].date()
        amt       = abs(float(r["amount"]))
        direction = r.get("direction", "buy")
        if direction not in ("buy", "sell"):
            direction = "buy"
        series = name_to_series.get(fund)
        nav    = nav_on_or_before(series, d) if series is not None else None
        if nav:
            row_units    = amt / nav
            signed_units = row_units if direction == "buy" else -row_units
            running[fund] = running.get(fund, 0.0) + signed_units
            if direction == "sell" and running[fund] < 0:
                negative_events.append(
                    {"fund": fund, "date": d, "running": running[fund], "amount": amt}
                )
        else:
            signed_units = None
        rows.append({
            "date":      d,
            "fund":      fund,
            "direction": direction,
            "amount":    amt,
            "nav":       nav,
            "units":     signed_units,
            "status":    "ok" if nav else "no_nav",
        })

    df_rows = pd.DataFrame(rows)
    matched = df_rows[df_rows["status"] == "ok"]
    buys    = matched[matched["direction"] == "buy"]
    sells   = matched[matched["direction"] == "sell"]

    total_bought = float(buys["amount"].sum())
    total_sold   = float(sells["amount"].sum())
    net_invested = total_bought - total_sold
    total_units  = float(matched["units"].sum())  # signed cross-fund sum

    # Current value: per-fund (remaining_units × that fund's current NAV), summed
    current_value = 0.0
    if not matched.empty:
        for fund, grp in matched.groupby("fund"):
            series = name_to_series.get(fund)
            if series is None or series.empty:
                continue
            cur_nav = float(series.iloc[-1])
            current_value += float(grp["units"].sum()) * cur_nav

    total_proceeds = current_value + total_sold
    absolute_ret   = total_proceeds - total_bought
    return_pct     = (absolute_ret / total_bought * 100) if total_bought else 0

    cf_dates   = []
    cf_amounts = []
    for _, r in matched.iterrows():
        cf_dates.append(r["date"])
        cf_amounts.append(-r["amount"] if r["direction"] == "buy" else r["amount"])
    cf_dates.append(today)
    cf_amounts.append(current_value)
    xi = xirr(
        cf_amounts,
        [datetime.combine(d, datetime.min.time()) for d in cf_dates],
    )

    return {
        "label":           label,
        "nav_series":      None,
        "current_nav":     None,
        "total_bought":    total_bought,
        "total_sold":      total_sold,
        "total_invested":  net_invested,
        "net_invested":    net_invested,
        "total_units":     total_units,
        "current_value":   current_value,
        "total_proceeds":  total_proceeds,
        "absolute_ret":    absolute_ret,
        "return_pct":      return_pct,
        "xirr":            xi,
        "detail":          df_rows,
        "matched":         len(matched),
        "skipped":         len(df_rows) - len(matched),
        "n_buys":          len(buys),
        "n_sells":         len(sells),
        "negative_events": negative_events,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="page-header">
  <h1>MF Switch Simulator</h1>
  <div class="mono">What if I had invested in a different fund?</div>
</div>
""", unsafe_allow_html=True)

# ─── Bootstrap data ──────────────────────────────────────────────────────────
ensure_data_files()  # downloads (if needed) with visible progress before caching

# Phased status reporter — only renders during cache-miss; cache hits return instantly.
_phase_slot = st.empty()

def _phase(label: str, detail: str = ""):
    detail_html = f'<span class="detail">{detail}</span>' if detail else ""
    _phase_slot.markdown(
        f'<div class="phase"><span class="dot"></span>'
        f'<span class="label">{label}</span>{detail_html}</div>',
        unsafe_allow_html=True,
    )

fund_df, nav_index, latest_nav_date = load_data(_phase=_phase)
_phase_slot.empty()

mtime = datetime.fromtimestamp(PARQUET_PATH.stat().st_mtime).strftime("%d %b %Y %H:%M")

# Data freshness check
if latest_nav_date is not None:
    days_stale = (pd.Timestamp.today().normalize() - latest_nav_date).days
    # Skip weekends: 0-1 days behind is fine (NAV not published on weekends/holidays)
    if days_stale <= 3:
        freshness_html = f'Latest NAV in data: <strong>{latest_nav_date.strftime("%d %b %Y")}</strong> ✓ Fresh'
        banner_cls = "box-blue"
    else:
        freshness_html = (
            f'Latest NAV in data: <strong>{latest_nav_date.strftime("%d %b %Y")}</strong> '
            f'⚠️ <strong>{days_stale} days behind today</strong> — repo may not have updated'
        )
        banner_cls = "box-yellow"
else:
    freshness_html = "Latest NAV date not available in CSV"
    banner_cls = "box-blue"

st.markdown(
    f'<div class="box {banner_cls}">'
    f'NAV database loaded &nbsp;·&nbsp; <strong>{len(nav_index):,} funds</strong> &nbsp;·&nbsp; '
    f'File updated {mtime} &nbsp;·&nbsp; {freshness_html}'
    f'</div>',
    unsafe_allow_html=True,
)

# ─── Step 1 · Upload ─────────────────────────────────────────────────────────
st.markdown('<div class="step-label">Step 1 · Upload Zerodha Coin statement(s)</div>', unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "Zerodha Coin Excel/CSV exports",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True,
    help="Coin → Portfolio → Transaction History → Download CSV or Excel. Upload multiple files to combine them.",
)

purchases_df    = None
selected_funds  = []

if uploaded_files:
    parsed_frames = []
    for f in uploaded_files:
        with st.spinner(f"Parsing {f.name}…"):
            df = parse_zerodha(f)
        if df is not None and not df.empty:
            parsed_frames.append(df)
            st.success(f"✓ {f.name} → {len(df)} purchase transactions")
        else:
            st.error(f"✗ {f.name}: could not parse (skipped)")

    if parsed_frames:
        combined = pd.concat(parsed_frames, ignore_index=True)
        before   = len(combined)

        # Prefer trade_id when every row carries a non-empty value (Zerodha CSV path).
        use_trade_id = False
        if "trade_id" in combined.columns:
            tid = combined["trade_id"].astype(str).str.strip()
            if tid.notna().all() and (tid != "").all() and (tid.str.lower() != "nan").all():
                use_trade_id = True

        if use_trade_id:
            combined = combined.drop_duplicates(subset=["trade_id"]).reset_index(drop=True)
        else:
            # Row-key fallback covers legacy Excel which lacks trade_id.
            if {"units", "nav"}.issubset(combined.columns):
                keycols = [c for c in ["scheme_name", "date", "units", "nav", "trade_type", "direction"] if c in combined.columns]
            else:
                keycols = [c for c in ["scheme_name", "date", "amount", "txn_type", "direction"] if c in combined.columns]
            if keycols:
                combined = combined.drop_duplicates(subset=keycols).reset_index(drop=True)

        dropped = before - len(combined)
        if dropped > 0:
            method = "trade_id" if use_trade_id else "scheme/date/units/nav"
            st.markdown(
                f'<div class="box box-yellow">Removed <strong>{dropped}</strong> duplicate row(s) across files '
                f'(deduped by {method}).</div>',
                unsafe_allow_html=True,
            )
        purchases_df = combined

# ─── Step 2 · Select fund(s) from statement ──────────────────────────────────
actual_codes: dict = {}   # scheme_name (from statement) -> AMFI scheme_code
alt_code = None

if purchases_df is not None:
    st.markdown('<div class="step-label">Step 2 · Select fund(s) from your statement</div>', unsafe_allow_html=True)

    funds_in_file = sorted(purchases_df["scheme_name"].dropna().unique().tolist())
    selected_funds = st.multiselect(
        "Your fund(s) — pick one or more to club into a combined real portfolio",
        funds_in_file,
        default=[],
    )

    if selected_funds:
        def _txn_blurb(frame: pd.DataFrame) -> str:
            """'12 buys, 3 sells' or '12 purchases' depending on whether sells exist."""
            if "direction" in frame.columns:
                buys  = (frame["direction"] == "buy").sum()
                sells = (frame["direction"] == "sell").sum()
                if sells > 0:
                    return f"{buys} buys, {sells} sells"
            return f"{len(frame)} purchases"

        # Per-fund mini-summary
        badges = []
        for fund in selected_funds:
            ftx = purchases_df[purchases_df["scheme_name"] == fund]
            badges.append(
                f'<span class="range-badge">{fund} &nbsp;·&nbsp; '
                f'{_txn_blurb(ftx)} &nbsp;·&nbsp; '
                f'{ftx["date"].min().strftime("%d %b %Y")} → '
                f'{ftx["date"].max().strftime("%d %b %Y")}</span>'
            )
        st.markdown("<br>".join(badges), unsafe_allow_html=True)

        # Combined badge
        pooled = purchases_df[purchases_df["scheme_name"].isin(selected_funds)]
        plural = "s" if len(selected_funds) > 1 else ""
        st.markdown(
            f'<div class="box box-blue" style="margin-top:.6rem"><strong>Combined:</strong> '
            f'{len(selected_funds)} fund{plural} &nbsp;·&nbsp; '
            f'{_txn_blurb(pooled)} &nbsp;·&nbsp; '
            f'{pooled["date"].min().strftime("%d %b %Y")} → '
            f'{pooled["date"].max().strftime("%d %b %Y")}</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Preview transactions"):
            cols = ["date", "scheme_name"]
            for c in ["direction", "txn_type", "trade_type", "amount", "units", "nav"]:
                if c in pooled.columns:
                    cols.append(c)
            disp = pooled[cols].sort_values("date").rename(columns={"scheme_name": "fund"}).copy()
            disp["date"] = disp["date"].dt.strftime("%d %b %Y")
            st.dataframe(disp, use_container_width=True, hide_index=True)

# ─── Step 3 · Identify each actual fund in AMFI data ─────────────────────────
if purchases_df is not None and selected_funds:
    st.markdown('<div class="step-label">Step 3 · Match your fund(s) in AMFI database</div>', unsafe_allow_html=True)

    isin_cols = [c for c in fund_df.columns if "isin" in c.lower()]

    def _match_isin(isin_val: str):
        """Return (scheme_code, scheme_name) on hit, else None."""
        if not isin_val:
            return None
        target = isin_val.upper()
        for col in isin_cols:
            m = fund_df[fund_df[col].astype(str).str.upper() == target]
            if not m.empty:
                code = int(m.iloc[0]["scheme_code"])
                name = m.iloc[0].get("scheme_name", f"Scheme {code}")
                return code, name
        return None

    failures = []  # [(idx, fund_name, isin_or_None)]
    status_lines = []

    for idx, fund in enumerate(selected_funds):
        ftx = purchases_df[purchases_df["scheme_name"] == fund]
        isin_val = None
        if "isin" in ftx.columns:
            isins = ftx["isin"].dropna().astype(str).str.strip()
            isins = isins[isins != ""].unique()
            if len(isins) >= 1:
                isin_val = isins[0]

        match = _match_isin(isin_val)
        if match:
            code, matched_name = match
            actual_codes[fund] = code
            status_lines.append(
                f'<div class="box box-green">✓ <strong>{fund}</strong> → '
                f'{matched_name} <code>[{code}]</code></div>'
            )
        else:
            reason = (
                f"ISIN <code>{isin_val}</code> not in database"
                if isin_val else "no ISIN in statement"
            )
            status_lines.append(
                f'<div class="box box-yellow">✗ <strong>{fund}</strong> → {reason}. '
                f'Search manually below.</div>'
            )
            failures.append((idx, fund))

    st.markdown("\n".join(status_lines), unsafe_allow_html=True)

    # Manual-search expander per failure (keys namespaced by index to avoid collisions)
    for idx, fund in failures:
        with st.expander(f"Manual match · {fund}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                q = st.text_input("Search", value=fund[:50], key=f"actual_q_{idx}")
            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Search", key=f"actual_q_btn_{idx}"):
                    st.session_state[f"actual_results_{idx}"] = (
                        search_funds(fund_df, q).to_dict("records")
                    )
            results = st.session_state.get(f"actual_results_{idx}", [])
            if results:
                opts = {
                    f"{r.get('scheme_name','?')}  [{r['scheme_code']}]": int(r["scheme_code"])
                    for r in results
                }
                chosen = st.selectbox(
                    "Select fund", list(opts.keys()), key=f"actual_sel_{idx}"
                )
                actual_codes[fund] = opts[chosen]
            else:
                manual = st.number_input(
                    "Or enter scheme code",
                    min_value=0, step=1, value=0,
                    key=f"actual_manual_{idx}",
                )
                if manual:
                    actual_codes[fund] = int(manual)

    matched_n = len(actual_codes)
    total_n   = len(selected_funds)
    if matched_n < total_n:
        st.markdown(
            f'<div class="box box-yellow">'
            f'<strong>{matched_n} of {total_n}</strong> fund(s) matched. '
            f'Resolve the rest above to enable the comparison.</div>',
            unsafe_allow_html=True,
        )

# ─── Step 4 · Alternate fund ─────────────────────────────────────────────────
all_actuals_matched = (
    purchases_df is not None
    and bool(selected_funds)
    and len(actual_codes) == len(selected_funds)
)

if all_actuals_matched:
    st.markdown('<div class="step-label">Step 4 · Pick the alternate fund to compare</div>', unsafe_allow_html=True)

    # Build the autocomplete option list once per process and stash on the
    # _DATA_CACHE singleton so we don't rebuild 16k strings on every rerun.
    if "alt_options" not in _DATA_CACHE:
        nav_codes  = set(nav_index.keys())
        in_nav     = (
            fund_df[fund_df["scheme_code"].isin(nav_codes)]
            [["scheme_name", "scheme_code"]]
            .dropna(subset=["scheme_name"])
            .sort_values("scheme_name")
        )
        labels = [
            f"{name}  [{int(code)}]"
            for name, code in zip(in_nav["scheme_name"], in_nav["scheme_code"])
        ]
        _DATA_CACHE["alt_options"] = (labels, dict(zip(labels, in_nav["scheme_code"].astype(int))))

    alt_labels, alt_label_to_code = _DATA_CACHE["alt_options"]

    alt_label = st.selectbox(
        f"Select alternate fund ({len(alt_labels):,} schemes with NAV data)",
        options=alt_labels,
        index=None,
        placeholder="Type to search — e.g. Parag Parikh Flexi Cap",
        key="alt_sel",
    )
    alt_code = alt_label_to_code[alt_label] if alt_label else None

    # Show alternate fund availability range — coverage check uses pooled purchases
    if alt_code:
        if alt_code in nav_index:
            alt_start, alt_end = fund_date_range(nav_index[alt_code])
            pooled_txns = purchases_df[purchases_df["scheme_name"].isin(selected_funds)]

            missing_before = pooled_txns[pooled_txns["date"].dt.date < alt_start]
            color = "box-green" if len(missing_before) == 0 else "box-yellow"
            warn = (
                f"⚠️ {len(missing_before)} of your purchases ({missing_before['date'].min().strftime('%d %b %Y')} – "
                f"{missing_before['date'].max().strftime('%d %b %Y')}) predate this fund's launch. "
                f"They will be excluded from the comparison."
            ) if len(missing_before) else "✓ All your purchase dates fall within this fund's data range."

            st.markdown(
                f'<div class="box {color}">'
                f'<strong>Alternate fund NAV data:</strong> '
                f'<span class="range-badge" style="display:inline">'
                f'{alt_start.strftime("%d %b %Y")} → {alt_end.strftime("%d %b %Y")}'
                f'</span><br>{warn}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.warning(f"Scheme code {alt_code} not found in the NAV database.")
            alt_code = None

# ─── Run ─────────────────────────────────────────────────────────────────────
exclude_sells = False
if all_actuals_matched and alt_code:
    st.markdown("---")

    pooled_for_toggle = purchases_df[purchases_df["scheme_name"].isin(selected_funds)]
    has_sells_in_scope = (
        "direction" in pooled_for_toggle.columns
        and (pooled_for_toggle["direction"] == "sell").any()
    )
    if has_sells_in_scope:
        exclude_sells = st.checkbox(
            "Exclude sells from calculation (treat all bought units as still held)",
            value=False,
            key="exclude_sells",
        )

    run = st.button("⚡  Run Comparison")

    if run:
        if alt_code not in nav_index:
            st.error(f"Alternate fund scheme code {alt_code} not found in NAV data.")
        else:
            pooled_txns = purchases_df[purchases_df["scheme_name"].isin(selected_funds)].copy()

            if exclude_sells and "direction" in pooled_txns.columns:
                pooled_txns = pooled_txns[pooled_txns["direction"] == "buy"].copy()

            # Build name → NAV-series map for the pooled actual side.
            name_to_series: dict = {}
            missing_codes = []
            for fund, code in actual_codes.items():
                if code in nav_index:
                    name_to_series[fund] = nav_index[code]
                else:
                    missing_codes.append((fund, code))

            if missing_codes:
                for fund, code in missing_codes:
                    st.error(f"Scheme code {code} for '{fund}' not found in NAV data.")
            else:
                alt_series  = nav_index[alt_code]
                alt_cur_nav = float(alt_series.iloc[-1])
                alt_name_arr = fund_df[fund_df["scheme_code"] == alt_code]["scheme_name"].values
                alt_name     = alt_name_arr[0] if len(alt_name_arr) else f"Fund {alt_code}"

                n_funds      = len(selected_funds)
                actual_label = (
                    selected_funds[0] if n_funds == 1
                    else f"{n_funds} funds clubbed"
                )

                with st.spinner("Computing…"):
                    actual_res = compute_scenario_pooled(pooled_txns, name_to_series, actual_label)
                    alt_res    = compute_scenario(pooled_txns, alt_series, alt_cur_nav, alt_name)

                sells_present = (actual_res["n_sells"] + alt_res["n_sells"]) > 0

                # ── Verdict ───────────────────────────────────────────────────
                # current_value comparison is mathematically equivalent to
                # total_proceeds comparison (cash extracted is mirrored), so
                # we use current_value for the verdict diff.
                val_diff  = alt_res["current_value"] - actual_res["current_value"]
                xirr_diff = ((alt_res["xirr"] or 0) - (actual_res["xirr"] or 0)) * 100
                verdict_color = "box-green" if val_diff >= 0 else "box-red"
                verdict_sign  = "+" if val_diff >= 0 else ""

                if n_funds == 1:
                    lead = f"Switching to <em>{alt_name}</em>"
                else:
                    lead = (
                        f"Clubbing your {n_funds} funds "
                        f"({len(pooled_txns)} transactions) into <em>{alt_name}</em>"
                    )
                if exclude_sells:
                    lead += " <span style=\"opacity:.7\">(sells excluded)</span>"

                st.markdown(
                    f'<div class="box {verdict_color}">'
                    f'<strong>Verdict:</strong> {lead} would have '
                    f'{"added" if val_diff >= 0 else "cost"} you '
                    f'<strong>₹{abs(val_diff):,.0f}</strong> '
                    f'({verdict_sign}{xirr_diff:.2f}% XIRR difference).'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Negative-units warning (alt side) ─────────────────────────
                neg = alt_res.get("negative_events") or []
                if neg:
                    first = neg[0]
                    extra = f" (and {len(neg) - 1} more such event(s))" if len(neg) > 1 else ""
                    st.markdown(
                        f'<div class="box box-yellow">'
                        f'⚠️ On <strong>{first["date"].strftime("%d %b %Y")}</strong> your sell of '
                        f'<strong>₹{first["amount"]:,.0f}</strong> exceeded the alt fund\'s value '
                        f'at that date{extra}. Alt units went negative for math consistency — '
                        f'the comparison still computes but the alt scenario\'s remaining units '
                        f'is not physically realizable.</div>',
                        unsafe_allow_html=True,
                    )

                # ── Summary stats table ───────────────────────────────────────
                st.markdown('<div class="step-label">Comparison Summary</div>', unsafe_allow_html=True)

                xi_a = f"{actual_res['xirr']*100:.2f}%" if actual_res["xirr"] else "N/A"
                xi_b = f"{alt_res['xirr']*100:.2f}%"    if alt_res["xirr"]    else "N/A"

                def _cls(a_val, b_val, higher_is_better=True):
                    if a_val is None or b_val is None:
                        return "neutral", "neutral"
                    better = a_val > b_val if higher_is_better else a_val < b_val
                    return ("better", "worse") if better else ("worse", "better")

                cv_a, cv_b         = _cls(actual_res["current_value"], alt_res["current_value"])
                pr_a, pr_b         = _cls(actual_res["total_proceeds"], alt_res["total_proceeds"])
                ret_a, ret_b       = _cls(actual_res["return_pct"],    alt_res["return_pct"])
                xi_cls_a, xi_cls_b = _cls(actual_res["xirr"] or 0, alt_res["xirr"] or 0)

                actual_nav_str = (
                    f"₹{actual_res['current_nav']:,.4f}"
                    if actual_res.get("current_nav") is not None else "—"
                )
                a_col_hdr = (
                    f"Actual · {selected_funds[0][:55]}" if n_funds == 1
                    else f"Actual · {n_funds} funds clubbed"
                )
                b_col_hdr = f"Alternate · {alt_name[:55]}"

                # Build metrics list. Sell-aware rows surface only when sells are present.
                metrics = []

                if sells_present:
                    metrics.extend([
                        ("Total Bought",
                            f"₹{actual_res['total_bought']:,.0f}",
                            f"₹{alt_res['total_bought']:,.0f}",
                            "neutral", "neutral"),
                        ("Total Sold",
                            f"₹{actual_res['total_sold']:,.0f}",
                            f"₹{alt_res['total_sold']:,.0f}",
                            "neutral", "neutral"),
                        ("Net Invested",
                            f"₹{actual_res['net_invested']:,.0f}",
                            f"₹{alt_res['net_invested']:,.0f}",
                            "neutral", "neutral"),
                    ])
                else:
                    metrics.append(
                        ("Total Invested",
                            f"₹{actual_res['total_invested']:,.0f}",
                            f"₹{alt_res['total_invested']:,.0f}",
                            "neutral", "neutral"),
                    )

                metrics.extend([
                    ("Buy transactions" if sells_present else "Transactions matched",
                        str(actual_res["n_buys"] if sells_present else actual_res["matched"]),
                        str(alt_res["n_buys"]    if sells_present else alt_res["matched"]),
                        "neutral", "neutral"),
                ])
                if sells_present:
                    metrics.append(
                        ("Sell transactions",
                            str(actual_res["n_sells"]),
                            str(alt_res["n_sells"]),
                            "neutral", "neutral"),
                    )
                metrics.extend([
                    ("Transactions skipped (no NAV)",
                        str(actual_res["skipped"]),
                        str(alt_res["skipped"]),
                        "neutral", "neutral"),
                    ("Current NAV",
                        actual_nav_str,
                        f"₹{alt_res['current_nav']:,.4f}",
                        "neutral", "neutral"),
                    ("Remaining Units" if sells_present else "Total Units",
                        f"{actual_res['total_units']:,.4f}",
                        f"{alt_res['total_units']:,.4f}",
                        "neutral", "neutral"),
                    ("Current Value",
                        f"₹{actual_res['current_value']:,.0f}",
                        f"₹{alt_res['current_value']:,.0f}",
                        cv_a, cv_b),
                ])
                if sells_present:
                    metrics.append(
                        ("Total Proceeds (current + sold)",
                            f"₹{actual_res['total_proceeds']:,.0f}",
                            f"₹{alt_res['total_proceeds']:,.0f}",
                            pr_a, pr_b),
                    )
                metrics.extend([
                    ("Absolute Return",
                        f"₹{actual_res['absolute_ret']:,.0f}",
                        f"₹{alt_res['absolute_ret']:,.0f}",
                        cv_a, cv_b),
                    ("Total Return %",
                        f"{actual_res['return_pct']:+.2f}%",
                        f"{alt_res['return_pct']:+.2f}%",
                        ret_a, ret_b),
                    ("XIRR", xi_a, xi_b, xi_cls_a, xi_cls_b),
                ])

                rows_html = ""
                for label, a_val, b_val, cls_a, cls_b in metrics:
                    rows_html += (
                        f"<tr>"
                        f"<td class='metric-col'>{label}</td>"
                        f"<td class='{cls_a}'>{a_val}</td>"
                        f"<td class='{cls_b}'>{b_val}</td>"
                        f"</tr>"
                    )

                st.markdown(f"""
                <table class="summary-table">
                  <thead><tr>
                    <th style="width:30%">Metric</th>
                    <th>{a_col_hdr}</th>
                    <th class="winner-col">{b_col_hdr}</th>
                  </tr></thead>
                  <tbody>{rows_html}</tbody>
                </table>
                """, unsafe_allow_html=True)

                # ── Transaction-level table (row-level join) ──────────────────
                st.markdown('<div class="step-label" style="margin-top:2rem">Transaction Detail</div>', unsafe_allow_html=True)

                d_actual = actual_res["detail"].reset_index(drop=True).rename(
                    columns={"nav": "actual_nav", "units": "actual_units", "status": "actual_status"}
                )
                d_alt = alt_res["detail"].reset_index(drop=True).rename(
                    columns={"nav": "alt_nav", "units": "alt_units", "status": "alt_status"}
                )
                # Both came from pooled_txns iterated row-by-row, so positions align 1:1.
                merged = pd.concat(
                    [
                        d_actual[["date", "fund", "direction", "amount", "actual_nav", "actual_units", "actual_status"]],
                        d_alt[["alt_nav", "alt_units", "alt_status"]],
                    ],
                    axis=1,
                ).sort_values("date").reset_index(drop=True)

                def fmt_nav(x):   return f"₹{x:,.4f}" if pd.notna(x) else "—"
                def fmt_units(x): return f"{x:,.4f}"  if pd.notna(x) else "—"
                def fmt_amt_signed(amt, direction):
                    if pd.isna(amt):
                        return "—"
                    if direction == "sell":
                        return f"−₹{abs(amt):,.0f}"
                    return f"₹{amt:,.0f}"
                def fmt_status(actual_s, alt_s):
                    parts = []
                    if actual_s == "no_nav": parts.append("⚠ no NAV (actual)")
                    if alt_s    == "no_nav": parts.append("⚠ no NAV (alt)")
                    return ", ".join(parts) if parts else "✓"

                display = pd.DataFrame({
                    "Date":         merged["date"].apply(lambda x: x.strftime("%d %b %Y") if hasattr(x, "strftime") else str(x)),
                    "Fund":         merged["fund"],
                    "Type":         merged["direction"].astype(str).str.title(),
                    "Amount":       [fmt_amt_signed(a, d) for a, d in zip(merged["amount"], merged["direction"])],
                    "Actual NAV":   merged["actual_nav"].apply(fmt_nav),
                    "Actual Units": merged["actual_units"].apply(fmt_units),
                    "Alt NAV":      merged["alt_nav"].apply(fmt_nav),
                    "Alt Units":    merged["alt_units"].apply(fmt_units),
                    "Notes":        merged.apply(
                        lambda r: fmt_status(r.get("actual_status"), r.get("alt_status")), axis=1
                    ),
                })

                missing_actual = (merged["actual_status"] == "no_nav").sum()
                missing_alt    = (merged["alt_status"]    == "no_nav").sum()
                if missing_actual or missing_alt:
                    st.markdown(
                        f'<div class="box box-yellow">'
                        f'Missing NAV data → Actual: <strong>{missing_actual}</strong> rows, '
                        f'Alternate: <strong>{missing_alt}</strong> rows. '
                        f'These rows are excluded from XIRR and return calculations.</div>',
                        unsafe_allow_html=True,
                    )

                st.dataframe(display, use_container_width=True, hide_index=True)

                # ── Excel export ──────────────────────────────────────────────
                st.markdown('<div class="step-label">Export</div>', unsafe_allow_html=True)

                summary_df = pd.DataFrame([
                    {"Metric": m[0], "Actual": m[1], "Alternate": m[2]}
                    for m in metrics
                ])
                export_df = display.copy()

                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as w:
                    summary_df.to_excel(w, sheet_name="Summary",     index=False)
                    export_df.to_excel(w,  sheet_name="Transactions", index=False)
                buf.seek(0)
                st.download_button(
                    "⬇ Download Excel Report",
                    data=buf,
                    file_name=f"mf_compare_{date.today().isoformat()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )


# ─── Empty state ─────────────────────────────────────────────────────────────
if not uploaded_files:
    st.markdown("""
    <div class="box box-yellow">
    <strong>Export from Zerodha Coin:</strong>
    Login → Coin → Portfolio → Transaction History → Download Excel
    </div>
    <div style="margin-top:1.5rem;max-width:500px;font-size:.88rem;line-height:1.9;color:#333;">
    <strong>How it works</strong><br>
    1. Parses your purchase dates &amp; amounts from the statement<br>
    2. Replays the same timeline in the alternate fund using its historical NAV<br>
    3. Shows XIRR and returns side-by-side in a comparison table<br>
    4. Flags dates where NAV data is missing for either fund<br>
    5. All data is local — no external API calls after first download
    </div>
    """, unsafe_allow_html=True)
