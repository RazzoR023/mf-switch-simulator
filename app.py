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
        df["date"]   = pd.to_datetime(df["date"], errors="coerce")
        df["units"]  = pd.to_numeric(df["quantity"], errors="coerce")
        df["nav"]    = pd.to_numeric(df["price"],    errors="coerce")
        df["amount"] = df["units"] * df["nav"]
        df = df.dropna(subset=["date", "amount"])
        out = df[df["trade_type"].astype(str).str.lower() == "buy"]
        if out.empty:
            st.warning("No buy transactions found — showing all rows.")
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

    if "txn_type" in df.columns:
        kw   = ["purchase", "buy", "sip", "lumpsum", "invest", "switch in"]
        mask = df["txn_type"].astype(str).str.lower().str.contains("|".join(kw), na=False)
        out  = df[mask] if not df[mask].empty else df[df["amount"] > 0]
    else:
        out = df[df["amount"] > 0]

    return out.reset_index(drop=True)


# ─── Scenario computation ────────────────────────────────────────────────────

def compute_scenario(
    purchases: pd.DataFrame,
    nav_series: pd.Series,
    current_nav: float,
    label: str,
) -> dict:
    today = date.today()
    rows  = []
    for _, r in purchases.iterrows():
        d   = r["date"].date()
        amt = abs(float(r["amount"]))
        nav = nav_on_or_before(nav_series, d)
        rows.append({
            "date":   d,
            "amount": amt,
            "nav":    nav,
            "units":  amt / nav if nav else None,
            "status": "ok" if nav else "no_nav",
        })

    df_rows = pd.DataFrame(rows)
    matched = df_rows[df_rows["status"] == "ok"]

    total_invested = matched["amount"].sum()
    total_units    = matched["units"].sum()
    current_value  = total_units * current_nav

    # XIRR
    cf_dates   = list(matched["date"]) + [today]
    cf_amounts = [-r for r in matched["amount"]] + [current_value]
    xi = xirr(
        cf_amounts,
        [datetime.combine(d, datetime.min.time()) for d in cf_dates],
    )

    return {
        "label":          label,
        "nav_series":     nav_series,
        "current_nav":    current_nav,
        "total_invested": total_invested,
        "total_units":    total_units,
        "current_value":  current_value,
        "absolute_ret":   current_value - total_invested,
        "return_pct":     ((current_value - total_invested) / total_invested * 100) if total_invested else 0,
        "xirr":           xi,
        "detail":         df_rows,
        "matched":        len(matched),
        "skipped":        len(df_rows) - len(matched),
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
st.markdown('<div class="step-label">Step 1 · Upload Zerodha Coin statement</div>', unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Zerodha Coin Excel export",
    type=["csv", "xlsx", "xls"],
    help="Coin → Portfolio → Transaction History → Download CSV or Excel",
)

purchases_df  = None
selected_fund = None

if uploaded:
    with st.spinner("Parsing…"):
        purchases_df = parse_zerodha(uploaded)
    if purchases_df is not None:
        st.success(f"✓ {len(purchases_df)} purchase transactions parsed")

# ─── Step 2 · Select fund from statement ─────────────────────────────────────
actual_code = None
alt_code    = None

if purchases_df is not None:
    st.markdown('<div class="step-label">Step 2 · Select fund from your statement</div>', unsafe_allow_html=True)

    funds_in_file = sorted(purchases_df["scheme_name"].dropna().unique().tolist())
    selected_fund = st.selectbox("Your fund (from statement)", funds_in_file)

    if selected_fund:
        fund_txns = purchases_df[purchases_df["scheme_name"] == selected_fund].copy()
        date_range_str = (
            f"{fund_txns['date'].min().strftime('%d %b %Y')} → "
            f"{fund_txns['date'].max().strftime('%d %b %Y')}"
        )
        st.markdown(
            f'<span class="range-badge">{len(fund_txns)} purchases &nbsp;·&nbsp; {date_range_str}</span>',
            unsafe_allow_html=True,
        )

        with st.expander("Preview transactions"):
            show = [c for c in ["date","txn_type","amount","units","nav"] if c in fund_txns.columns]
            st.dataframe(
                fund_txns[show].sort_values("date").assign(
                    date=lambda x: x["date"].dt.strftime("%d %b %Y")
                ),
                use_container_width=True, hide_index=True,
            )

# ─── Step 3 · Identify actual fund in AMFI data ───────────────────────────────
if purchases_df is not None and selected_fund:
    st.markdown('<div class="step-label">Step 3 · Match your actual fund in AMFI database</div>', unsafe_allow_html=True)

    # Try ISIN auto-match first — Zerodha CSV tradebook includes ISIN
    fund_txns_for_isin = purchases_df[purchases_df["scheme_name"] == selected_fund]
    isin_val = None
    if "isin" in fund_txns_for_isin.columns:
        isins = fund_txns_for_isin["isin"].dropna().unique()
        if len(isins) == 1:
            isin_val = isins[0]

    auto_matched_code = None
    if isin_val and "isin" in fund_df.columns:
        isin_match = fund_df[fund_df["isin"].astype(str).str.upper() == isin_val.upper()]
        if not isin_match.empty:
            auto_matched_code = int(isin_match.iloc[0]["scheme_code"])
            matched_name = isin_match.iloc[0].get("scheme_name", f"Scheme {auto_matched_code}")
            st.markdown(
                f'<div class="box box-green">✓ Auto-matched via ISIN <code>{isin_val}</code> → '
                f'<strong>{matched_name}</strong> [{auto_matched_code}]</div>',
                unsafe_allow_html=True,
            )

    # Also check ISIN_Div_Payout/Growth column which InertExpert2911 uses
    if auto_matched_code is None and isin_val:
        for col in fund_df.columns:
            if "isin" in col.lower():
                match = fund_df[fund_df[col].astype(str).str.upper() == isin_val.upper()]
                if not match.empty:
                    auto_matched_code = int(match.iloc[0]["scheme_code"])
                    matched_name = match.iloc[0].get("scheme_name", f"Scheme {auto_matched_code}")
                    st.markdown(
                        f'<div class="box box-green">✓ Auto-matched via ISIN <code>{isin_val}</code> → '
                        f'<strong>{matched_name}</strong> [{auto_matched_code}]</div>',
                        unsafe_allow_html=True,
                    )
                    break

    actual_code = auto_matched_code

    # Manual fallback if ISIN match failed
    if actual_code is None:
        if isin_val:
            st.markdown(
                f'<div class="box box-yellow">⚠ ISIN <code>{isin_val}</code> not found in database. '
                f'Search manually below.</div>',
                unsafe_allow_html=True,
            )
        with st.expander("Search manually" if actual_code is None else "Override auto-match"):
            c1, c2 = st.columns([3, 1])
            with c1:
                actual_q = st.text_input("Search actual fund", value=selected_fund[:50], key="aq")
            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Search", key="aq_btn"):
                    st.session_state["actual_results"] = search_funds(fund_df, actual_q).to_dict("records")

            if "actual_results" not in st.session_state:
                st.session_state["actual_results"] = []

            if st.session_state["actual_results"]:
                opts = {
                    f"{r.get('scheme_name','?')}  [{r['scheme_code']}]": int(r["scheme_code"])
                    for r in st.session_state["actual_results"]
                }
                actual_code = opts[st.selectbox("Select actual fund", list(opts.keys()), key="actual_sel")]
            else:
                manual = st.number_input("Or enter scheme code", min_value=0, step=1, value=0, key="actual_manual")
                actual_code = int(manual) if manual else None

    # Show actual fund data range
    if actual_code and actual_code in nav_index:
        a_start, a_end = fund_date_range(nav_index[actual_code])
        st.markdown(
            f'<span class="range-badge">Actual fund NAV data: {a_start.strftime("%d %b %Y")} → {a_end.strftime("%d %b %Y")}</span>',
            unsafe_allow_html=True,
        )

# ─── Step 4 · Alternate fund ─────────────────────────────────────────────────
if purchases_df is not None and selected_fund and actual_code:
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

    # Show alternate fund availability range
    if alt_code:
        if alt_code in nav_index:
            alt_start, alt_end = fund_date_range(nav_index[alt_code])
            fund_txns  = purchases_df[purchases_df["scheme_name"] == selected_fund]
            txn_start  = fund_txns["date"].min().date()
            txn_end    = fund_txns["date"].max().date()

            # Warn if purchases predate the fund
            missing_before = fund_txns[fund_txns["date"].dt.date < alt_start]
            coverage_pct   = round((1 - len(missing_before) / len(fund_txns)) * 100)

            color = "box-green" if len(missing_before) == 0 else "box-yellow"
            warn  = (
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
if purchases_df is not None and selected_fund and actual_code and alt_code:
    st.markdown("---")
    run = st.button("⚡  Run Comparison")

    if run:
        if actual_code not in nav_index:
            st.error(f"Actual fund scheme code {actual_code} not found in NAV data.")
        elif alt_code not in nav_index:
            st.error(f"Alternate fund scheme code {alt_code} not found in NAV data.")
        else:
            fund_txns = purchases_df[purchases_df["scheme_name"] == selected_fund].copy()

            actual_series  = nav_index[actual_code]
            alt_series     = nav_index[alt_code]
            actual_cur_nav = float(actual_series.iloc[-1])
            alt_cur_nav    = float(alt_series.iloc[-1])

            actual_name = fund_df[fund_df["scheme_code"] == actual_code]["scheme_name"].values
            alt_name    = fund_df[fund_df["scheme_code"] == alt_code]["scheme_name"].values
            actual_name = actual_name[0] if len(actual_name) else f"Fund {actual_code}"
            alt_name    = alt_name[0]    if len(alt_name)    else f"Fund {alt_code}"

            with st.spinner("Computing…"):
                actual_res = compute_scenario(fund_txns, actual_series, actual_cur_nav, actual_name)
                alt_res    = compute_scenario(fund_txns, alt_series,    alt_cur_nav,    alt_name)

            # ── Summary stats table ───────────────────────────────────────────
            st.markdown('<div class="step-label">Comparison Summary</div>', unsafe_allow_html=True)

            xi_a = f"{actual_res['xirr']*100:.2f}%" if actual_res["xirr"] else "N/A"
            xi_b = f"{alt_res['xirr']*100:.2f}%"    if alt_res["xirr"]    else "N/A"

            # Determine which is better for each metric
            def _cls(a_val, b_val, higher_is_better=True):
                if a_val is None or b_val is None:
                    return "neutral", "neutral"
                better = a_val > b_val if higher_is_better else a_val < b_val
                return ("better", "worse") if better else ("worse", "better")

            cv_a, cv_b       = _cls(actual_res["current_value"], alt_res["current_value"])
            ret_a, ret_b     = _cls(actual_res["return_pct"],    alt_res["return_pct"])
            xi_cls_a, xi_cls_b = _cls(
                actual_res["xirr"] or 0, alt_res["xirr"] or 0
            )

            val_diff  = alt_res["current_value"] - actual_res["current_value"]
            xirr_diff = ((alt_res["xirr"] or 0) - (actual_res["xirr"] or 0)) * 100
            winner    = alt_name if val_diff >= 0 else actual_name

            verdict_color = "box-green" if val_diff >= 0 else "box-red"
            verdict_sign  = "+" if val_diff >= 0 else ""
            st.markdown(
                f'<div class="box {verdict_color}">'
                f'<strong>Verdict:</strong> Switching to <em>{alt_name}</em> would have '
                f'{"added" if val_diff >= 0 else "cost"} you '
                f'<strong>₹{abs(val_diff):,.0f}</strong> '
                f'({verdict_sign}{xirr_diff:.2f}% XIRR difference).'
                f'</div>',
                unsafe_allow_html=True,
            )

            a_col_hdr = f"Actual · {actual_name[:55]}"
            b_col_hdr = f"Alternate · {alt_name[:55]}"

            rows_html = ""
            metrics = [
                ("Total Invested",   f"₹{actual_res['total_invested']:,.0f}",  f"₹{alt_res['total_invested']:,.0f}",  "neutral", "neutral"),
                ("Transactions matched",
                    str(actual_res["matched"]),
                    str(alt_res["matched"]),
                    "neutral", "neutral"),
                ("Transactions skipped (no NAV)",
                    str(actual_res["skipped"]),
                    str(alt_res["skipped"]),
                    "neutral", "neutral"),
                ("Current NAV",      f"₹{actual_res['current_nav']:,.4f}",     f"₹{alt_res['current_nav']:,.4f}",     "neutral", "neutral"),
                ("Total Units",      f"{actual_res['total_units']:,.4f}",       f"{alt_res['total_units']:,.4f}",       "neutral", "neutral"),
                ("Current Value",    f"₹{actual_res['current_value']:,.0f}",   f"₹{alt_res['current_value']:,.0f}",   cv_a,    cv_b),
                ("Absolute Return",  f"₹{actual_res['absolute_ret']:,.0f}",    f"₹{alt_res['absolute_ret']:,.0f}",    cv_a,    cv_b),
                ("Total Return %",   f"{actual_res['return_pct']:+.2f}%",      f"{alt_res['return_pct']:+.2f}%",      ret_a,   ret_b),
                ("XIRR",             xi_a,                                      xi_b,                                  xi_cls_a, xi_cls_b),
            ]
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

            # ── Transaction-level table ───────────────────────────────────────
            st.markdown('<div class="step-label" style="margin-top:2rem">Transaction Detail</div>', unsafe_allow_html=True)

            d_actual = actual_res["detail"].rename(columns={"nav": "actual_nav", "units": "actual_units", "status": "actual_status"})
            d_alt    = alt_res["detail"].rename(columns={"nav": "alt_nav",    "units": "alt_units",    "status": "alt_status"})

            merged = d_actual[["date","amount","actual_nav","actual_units","actual_status"]].merge(
                d_alt[["date","alt_nav","alt_units","alt_status"]], on="date", how="outer"
            ).sort_values("date").reset_index(drop=True)

            # Friendly formatting
            def fmt_nav(x):
                return f"₹{x:,.4f}" if pd.notna(x) else "—"
            def fmt_units(x):
                return f"{x:,.4f}" if pd.notna(x) else "—"
            def fmt_amt(x):
                return f"₹{x:,.0f}" if pd.notna(x) else "—"
            def fmt_status(actual_s, alt_s):
                parts = []
                if actual_s == "no_nav": parts.append("⚠ no NAV (actual)")
                if alt_s    == "no_nav": parts.append("⚠ no NAV (alt)")
                return ", ".join(parts) if parts else "✓"

            display = pd.DataFrame({
                "Date":         merged["date"].apply(lambda x: x.strftime("%d %b %Y") if hasattr(x,"strftime") else str(x)),
                "Amount":       merged["amount"].apply(fmt_amt),
                "Actual NAV":   merged["actual_nav"].apply(fmt_nav),
                "Actual Units": merged["actual_units"].apply(fmt_units),
                "Alt NAV":      merged["alt_nav"].apply(fmt_nav),
                "Alt Units":    merged["alt_units"].apply(fmt_units),
                "Notes":        merged.apply(lambda r: fmt_status(r.get("actual_status"), r.get("alt_status")), axis=1),
            })

            # Count missing
            missing_actual = (merged["actual_status"] == "no_nav").sum()
            missing_alt    = (merged["alt_status"]    == "no_nav").sum()
            if missing_actual or missing_alt:
                st.markdown(
                    f'<div class="box box-yellow">'
                    f'Missing NAV data → Actual fund: <strong>{missing_actual}</strong> dates, '
                    f'Alternate fund: <strong>{missing_alt}</strong> dates. '
                    f'These rows are excluded from XIRR and return calculations.</div>',
                    unsafe_allow_html=True,
                )

            st.dataframe(display, use_container_width=True, hide_index=True)

            # ── Excel export ──────────────────────────────────────────────────
            st.markdown('<div class="step-label">Export</div>', unsafe_allow_html=True)

            summary_df = pd.DataFrame([
                {"Metric": m[0], "Actual Fund": m[1], "Alternate Fund": m[2]}
                for m in metrics
            ])
            export_df = display.copy()

            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                summary_df.to_excel(w, sheet_name="Summary",      index=False)
                export_df.to_excel(w,  sheet_name="Transactions",  index=False)
            buf.seek(0)
            st.download_button(
                "⬇ Download Excel Report",
                data=buf,
                file_name=f"mf_compare_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


# ─── Empty state ─────────────────────────────────────────────────────────────
if not uploaded:
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
