import type {
  CompareRequest,
  Comparison,
  Coverage,
  Fund,
  Me,
  Portfolio,
  SavedComparison,
  Status,
  UploadResult,
} from './types';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

// Called when any request finds the session gone, so the app can show the login page.
let onSignedOut = () => {};
export const setSignedOutHandler = (fn: () => void) => {
  onSignedOut = fn;
};

async function call(method: string, path: string, body?: unknown): Promise<Response> {
  const res = await fetch(path, {
    method,
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
    if (res.status === 401 && !path.startsWith('/api/auth/')) onSignedOut();
    throw new ApiError(message, res.status);
  }
  return res;
}

const json = <T>(method: string, path: string, body?: unknown) =>
  call(method, path, body).then((r) => r.json() as Promise<T>);

// Auth
export const me = () => json<Me>('GET', '/api/auth/me');
export const login = (username: string, password: string) =>
  json<Me>('POST', '/api/auth/login', { username, password });
export const signup = (username: string, password: string) =>
  json<Me>('POST', '/api/auth/signup', { username, password });
export const logout = () => json<Me>('POST', '/api/auth/logout', {});
export const changePassword = (current: string, next: string) =>
  json<Me>('POST', '/api/auth/password', { current, new: next });

// NAV data
export const getStatus = () => json<Status>('GET', '/api/status');
export const getFund = (code: number) => json<Fund>('GET', `/api/funds/${code}`);
export const searchFunds = (q: string, signal?: AbortSignal) =>
  fetch(`/api/funds?q=${encodeURIComponent(q)}&limit=40`, { signal })
    .then((r) => (r.ok ? r.json() : { results: [] }))
    .then((r: { results: Fund[] }) => r.results);

// Statements
async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

export const getPortfolio = () => json<Portfolio>('GET', '/api/portfolio');

export async function upload(files: File[]) {
  const payload = await Promise.all(
    files.map(async (f) => ({ name: f.name, data: await toBase64(f) })),
  );
  return json<{ results: UploadResult[]; portfolio: Portfolio }>('POST', '/api/uploads', {
    files: payload,
  });
}

export const deleteUpload = (id: number) => json<Portfolio>('DELETE', `/api/uploads/${id}`);
export const uploadUrl = (id: number) => `/api/uploads/${id}/file`;

export const setMatch = (fund: string, code: number | null) =>
  json<Portfolio>('POST', '/api/matches', { fund, code });

// Comparisons
export const getCoverage = (req: CompareRequest) => json<Coverage>('POST', '/api/coverage', req);
export const compare = (req: CompareRequest) => json<Comparison>('POST', '/api/compare', req);

export const getSaved = () =>
  json<{ scenarios: SavedComparison[] }>('GET', '/api/scenarios').then((r) => r.scenarios);
export const saveComparison = (req: CompareRequest, name: string) =>
  json<{ scenarios: SavedComparison[] }>('POST', '/api/scenarios', { ...req, name }).then(
    (r) => r.scenarios,
  );
export const deleteSaved = (id: number) =>
  json<{ scenarios: SavedComparison[] }>('DELETE', `/api/scenarios/${id}`).then((r) => r.scenarios);

/** Fetches the Excel report and hands it to the browser as a download. */
export async function downloadReport(req: CompareRequest): Promise<void> {
  const res = await call('POST', '/api/report', req);
  const disposition = res.headers.get('Content-Disposition') ?? '';
  const encoded = /filename\*=UTF-8''([^;]+)/.exec(disposition)?.[1];
  const name = encoded ? decodeURIComponent(encoded) : 'mf_compare.xlsx';
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
