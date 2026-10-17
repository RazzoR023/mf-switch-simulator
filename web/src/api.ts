import type {
  CompareRequest,
  Comparison,
  Coverage,
  Fund,
  Status,
  TradebookResult,
  Transaction,
} from './types';

export class ApiError extends Error {}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let message = `The server answered ${res.status}.`;
    try {
      message = (await res.json()).error ?? message;
    } catch {
      // not JSON: keep the status message
    }
    throw new ApiError(message);
  }
  return res.json() as Promise<T>;
}

export const getStatus = () => request<Status>('/api/status');

export const searchFunds = (q: string, signal?: AbortSignal) =>
  fetch(`/api/funds?q=${encodeURIComponent(q)}&limit=40`, { signal })
    .then((r) => (r.ok ? r.json() : { results: [] }))
    .then((r: { results: Fund[] }) => r.results);

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

export async function parseTradebooks(files: File[]): Promise<TradebookResult> {
  const payload = await Promise.all(
    files.map(async (f) => ({ name: f.name, data: await toBase64(f) })),
  );
  return request<TradebookResult>('/api/tradebook', { files: payload });
}

export const getCoverage = (transactions: Transaction[], funds: string[], altCode: number) =>
  request<Coverage>('/api/coverage', { transactions, funds, alt_code: altCode });

export const compare = (req: CompareRequest) => request<Comparison>('/api/compare', req);

/** Fetches the Excel report and hands it to the browser as a download. */
export async function downloadReport(req: CompareRequest): Promise<void> {
  const res = await fetch('/api/report', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new ApiError((await res.json().catch(() => null))?.error ?? 'Could not build the report.');
  }
  const name =
    /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ??
    'mf_compare.xlsx';
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
