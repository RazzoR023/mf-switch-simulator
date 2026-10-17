// Shapes returned by the Python API (mfsim/server.py). Dates are ISO strings.

export interface Status {
  ready: boolean;
  funds_with_nav?: number;
  nav_rows?: number;
  latest_nav_date?: string | null;
  nav_max_date?: string | null;
  refreshed_at?: string | null;
  days_stale?: number | null;
  fresh?: boolean;
}

export interface Fund {
  code: number;
  name: string;
  nav_name: string | null;
  amc: string | null;
  category: string | null;
  launch_date: string | null;
  latest_nav_date: string | null;
  nav_start: string | null;
  nav_end: string | null;
  nav_count: number;
  last_nav: number | null;
}

export interface Transaction {
  date: string;
  scheme_name: string;
  direction: string;
  amount: number;
  units?: number;
  nav?: number;
  isin?: string;
  trade_type?: string;
  txn_type?: string;
  trade_id?: string;
}

export interface User {
  username: string;
}

export interface Me {
  user: User | null;
  signup: boolean;
}

/** One stored statement file (its parsed rows are merged into Portfolio.transactions). */
export interface UploadFile {
  id: number;
  name: string;
  size: number;
  uploaded_at: string;
  count: number;
  warnings: string[];
}

/** What happened to each file in an upload. ok=false: not stored (error says why). */
export interface UploadResult {
  name: string;
  ok: boolean;
  count: number;
  error: string | null;
  warnings: string[];
}

export type MatchProblem = 'no_isin' | 'isin_not_found' | 'no_nav';

export interface StatementFund {
  name: string;
  isin: string | null;
  n_txns: number;
  n_buys: number;
  n_sells: number;
  bought: number;
  sold: number;
  first_date: string;
  last_date: string;
  /** The user's own pick if they made one, else the ISIN match. */
  match: Fund | null;
  match_source: 'isin' | 'user' | null;
  match_problem: MatchProblem | null;
}

/** Everything the user has uploaded, deduplicated across files. */
export interface Portfolio {
  files: UploadFile[];
  transactions: Transaction[];
  duplicates: { dropped: number; method: string };
  funds: StatementFund[];
}

export interface Coverage {
  fund: Fund;
  n_before: number;
  first_before: string | null;
  last_before: string | null;
}

export type MetricKind = 'money' | 'count' | 'nav' | 'units' | 'pct' | 'xirr';
export type Verdict = 'better' | 'worse' | 'neutral';

export interface Metric {
  key: string;
  label: string;
  kind: MetricKind;
  actual: number | null;
  alternate: number | null;
  actual_cls: Verdict;
  alternate_cls: Verdict;
}

export interface NegativeEvent {
  date: string;
  running: number;
  amount: number;
  fund?: string;
}

export interface Scenario {
  label: string;
  current_nav: number | null;
  total_bought: number;
  total_sold: number;
  net_invested: number;
  total_units: number;
  current_value: number;
  total_proceeds: number;
  absolute_ret: number;
  return_pct: number;
  xirr: number | null;
  matched: number;
  skipped: number;
  n_buys: number;
  n_sells: number;
  negative_events: NegativeEvent[];
}

export interface DetailRow {
  date: string;
  fund: string;
  direction: string;
  amount: number;
  actual_nav: number | null;
  actual_units: number | null;
  actual_status: 'ok' | 'no_nav';
  alt_nav: number | null;
  alt_units: number | null;
  alt_status: 'ok' | 'no_nav';
}

export interface Comparison {
  as_of: string;
  actual: Scenario;
  alternate: Scenario & { fund: Fund };
  funds: string[];
  exclude_sells: boolean;
  n_txns: number;
  sells_present: boolean;
  verdict: { value_diff: number; xirr_diff: number };
  metrics: Metric[];
  detail: DetailRow[];
  missing: { actual: number; alternate: number };
}

/** The server replays the user's stored transactions; funds are matched server-side. */
export interface CompareRequest {
  funds: string[];
  alt_code: number;
  exclude_sells: boolean;
}

export interface SavedComparison {
  id: number;
  name: string;
  created_at: string;
  params: CompareRequest;
  snapshot: {
    as_of: string;
    actual_label: string;
    alt_label: string;
    actual_value: number;
    alt_value: number;
    actual_xirr: number | null;
    alt_xirr: number | null;
    value_diff: number;
    xirr_diff: number;
    n_txns: number;
  };
}
