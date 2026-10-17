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

export interface FileResult {
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
  first_date: string;
  last_date: string;
  match: Fund | null;
  match_problem: MatchProblem | null;
}

export interface TradebookResult {
  files: FileResult[];
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

export interface CompareRequest {
  transactions: Transaction[];
  funds: string[];
  actual_codes: Record<string, number>;
  alt_code: number;
  exclude_sells: boolean;
}
