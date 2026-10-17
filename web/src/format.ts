import type { Fund, MetricKind, StatementFund } from './types';

const inr0 = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });
const num4 = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});
const int = new Intl.NumberFormat('en-IN');
const dateFmt = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
});
const dateTimeFmt = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

export const money = (n: number) => `${n < 0 ? '−' : ''}₹${inr0.format(Math.abs(n))}`;
export const nav = (n: number | null | undefined) => (n == null ? '—' : `₹${num4.format(n)}`);
export const units = (n: number | null | undefined) => (n == null ? '—' : num4.format(n));
export const count = (n: number) => int.format(n);
export const signedPct = (n: number) => `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(2)}%`;
export const xirr = (x: number | null) => (x == null ? 'N/A' : `${(x * 100).toFixed(2)}%`);

/** "05 Jan 2021" from an ISO date. */
export const day = (iso: string | null | undefined) =>
  iso ? dateFmt.format(new Date(`${iso.slice(0, 10)}T00:00:00Z`)) : '—';

export const dateTime = (iso: string | null | undefined) =>
  iso ? dateTimeFmt.format(new Date(iso)) : '—';

export function metricValue(kind: MetricKind, v: number | null): string {
  if (v == null) return kind === 'xirr' ? 'N/A' : '—';
  switch (kind) {
    case 'money':
      return money(v);
    case 'count':
      return count(v);
    case 'nav':
      return nav(v);
    case 'units':
      return units(v);
    case 'pct':
      return signedPct(v);
    case 'xirr':
      return xirr(v);
  }
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

/** "12 buys, 3 sells" when there are sells, else "12 purchases". */
export function txnBlurb(f: Pick<StatementFund, 'n_txns' | 'n_buys' | 'n_sells'>): string {
  return f.n_sells > 0
    ? `${plural(f.n_buys, 'buy')}, ${plural(f.n_sells, 'sell')}`
    : plural(f.n_txns, 'purchase');
}

export const fundTitle = (f: Fund) => f.nav_name ?? f.name;

export const truncate = (s: string, max = 55) => (s.length > max ? `${s.slice(0, max - 1)}…` : s);

export const signedMoney = (n: number) => `${n >= 0 ? '+' : '−'}₹${inr0.format(Math.abs(n))}`;

/** "₹12.3L" / "₹1.2Cr" for stat cards. */
export function compactMoney(n: number): string {
  const a = Math.abs(n);
  const sign = n < 0 ? '−' : '';
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2)}Cr`;
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(2)}L`;
  return money(n);
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export { plural };
