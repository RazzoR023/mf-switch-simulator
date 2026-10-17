"""HTTP server: the JSON API plus the built React app, on the standard library alone.

    python -m mfsim.server

The server keeps no per-user state: the browser holds the parsed transactions and sends
them back with each request, so memory stays flat however many tabs are open.
"""

from __future__ import annotations

import base64
import gzip
import json
import logging
import mimetypes
import sys
import traceback
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import compare, config, report, tradebook
from .db import Db, DataNotReady

log = logging.getLogger("mfsim.server")

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/svg+xml", ".svg")

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# ─── Handlers ────────────────────────────────────────────────────────────────

def api_status(_q, _body) -> dict:
    try:
        with Db() as db:
            meta = db.meta()
    except DataNotReady:
        return {"ready": False}
    latest = meta.get("latest_nav_date") or meta.get("nav_max_date") or None
    days_stale = (date.today() - date.fromisoformat(latest)).days if latest else None
    return {
        "ready": True,
        "funds_with_nav": int(meta.get("funds_with_nav", 0)),
        "nav_rows": int(meta.get("nav_rows", 0)),
        "latest_nav_date": latest,
        "nav_max_date": meta.get("nav_max_date") or None,
        "refreshed_at": meta.get("refreshed_at") or None,
        "days_stale": days_stale,
        # NAVs aren't published on weekends and holidays, so a few days behind is normal.
        "fresh": days_stale is not None and days_stale <= 3,
    }


def api_search(q, _body) -> dict:
    query = (q.get("q") or [""])[0]
    limit = min(int((q.get("limit") or ["30"])[0]), 100)
    with Db() as db:
        return {"results": db.search_funds(query, limit)}


def api_fund(code: int) -> dict:
    with Db() as db:
        fund = db.fund(code)
    if not fund:
        raise ApiError(404, f"No scheme with code {code}.")
    return fund


def api_tradebook(_q, body) -> dict:
    files = body.get("files") or []
    if not files:
        raise ApiError(400, "No files uploaded.")
    results, txns = [], []
    for f in files:
        name = str(f.get("name") or "upload")
        try:
            data = base64.b64decode(f.get("data") or "", validate=True)
            rows, warnings = tradebook.parse_file(name, data)
        except tradebook.TradebookError as e:
            results.append({"name": name, "ok": False, "count": 0, "error": str(e), "warnings": []})
            continue
        except Exception as e:  # anything else about the file itself
            log.warning("could not parse %s: %s", name, e)
            results.append({"name": name, "ok": False, "count": 0,
                            "error": f"Could not read the file: {e}", "warnings": []})
            continue
        ok = bool(rows)
        results.append({
            "name": name, "ok": ok, "count": len(rows), "warnings": warnings,
            "error": None if ok else "No transactions found in this file.",
        })
        txns.extend(rows)
    txns, dropped, method = tradebook.dedupe(txns)
    with Db() as db:
        funds = compare.fund_summaries(db, txns)
    return {
        "files": results,
        "transactions": txns,
        "duplicates": {"dropped": dropped, "method": method},
        "funds": funds,
    }


def _compare_args(body) -> dict:
    try:
        return {
            "txns": body.get("transactions") or [],
            "funds": [str(f) for f in body.get("funds") or []],
            "actual_codes": {str(k): int(v) for k, v in (body.get("actual_codes") or {}).items()},
            "alt_code": int(body["alt_code"]),
            "exclude_sells": bool(body.get("exclude_sells")),
        }
    except (KeyError, TypeError, ValueError) as e:
        raise ApiError(400, f"Bad comparison request: {e}") from e


def api_coverage(_q, body) -> dict:
    try:
        alt_code = int(body["alt_code"])
    except (KeyError, TypeError, ValueError) as e:
        raise ApiError(400, "alt_code is required") from e
    with Db() as db:
        return compare.coverage(db, body.get("transactions") or [], body.get("funds") or [], alt_code)


def api_compare(_q, body) -> dict:
    with Db() as db:
        return compare.run(db, **_compare_args(body))


def api_report(_q, body) -> tuple[bytes, str, str]:
    with Db() as db:
        result = compare.run(db, **_compare_args(body))
    filename = f"mf_compare_{result['as_of']}.xlsx"
    return report.build(result), XLSX_TYPE, filename


GET_ROUTES = {"/api/status": api_status, "/api/funds": api_search}
POST_ROUTES = {
    "/api/tradebook": api_tradebook,
    "/api/coverage": api_coverage,
    "/api/compare": api_compare,
    "/api/report": api_report,
}


# ─── HTTP plumbing ───────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "mfsim"
    sys_version = ""

    def log_message(self, fmt, *args):
        if self.path.startswith("/api/") and not self.path.startswith("/api/health"):
            log.info("%s %s", self.address_string(), fmt % args)

    def _send(self, status: int, body: bytes, content_type: str, headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
        headers = {"Cache-Control": "no-store"}
        if len(body) > 2048 and "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(body, compresslevel=5)
            headers["Content-Encoding"] = "gzip"
        self._send(status, body, "application/json", headers)

    def _dispatch(self, fn, *args) -> None:
        try:
            result = fn(*args)
        except ApiError as e:
            return self._json(e.status, {"error": str(e)})
        except (tradebook.TradebookError, compare.CompareError) as e:
            return self._json(400, {"error": str(e)})
        except DataNotReady:
            return self._json(503, {"error": "The NAV database is still being built. Try again in a few minutes."})
        except Exception:
            log.error("error handling %s %s\n%s", self.command, self.path, traceback.format_exc())
            return self._json(500, {"error": "Something went wrong on the server. Check its log."})
        if isinstance(result, tuple):  # a file download
            body, ctype, filename = result
            return self._send(200, body, ctype, {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            })
        self._json(200, result)

    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        if path == "/api/health":
            return self._send(200, b"ok", "text/plain")
        if path in GET_ROUTES:
            return self._dispatch(GET_ROUTES[path], parse_qs(url.query), None)
        if path.startswith("/api/funds/"):
            code = path.removeprefix("/api/funds/")
            if not code.isdigit():
                return self._json(404, {"error": "Not found"})
            return self._dispatch(api_fund, int(code))
        if path.startswith("/api/"):
            return self._json(404, {"error": "Not found"})
        self._static(path)

    do_HEAD = do_GET

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in POST_ROUTES:
            return self._json(404, {"error": "Not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > config.MAX_BODY_BYTES:
            self.close_connection = True
            return self._json(413, {"error": "That upload is too large."})
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "The request body isn't valid JSON."})
        if not isinstance(body, dict):
            return self._json(400, {"error": "The request body must be a JSON object."})
        self._dispatch(POST_ROUTES[path], None, body)

    def _static(self, path: str) -> None:
        root = config.WEB_DIR.resolve()
        target = (root / path.lstrip("/")).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            # Client-side routes all render the app.
            target = root / "index.html"
            if not target.is_file():
                return self._send(404, b"UI not built: run npm run build in web/", "text/plain")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        # Vite puts content hashes in asset names, so those never change.
        cache = ("public, max-age=31536000, immutable" if "/assets/" in path else "no-cache")
        headers = {"Cache-Control": cache}
        gz = target.with_name(target.name + ".gz")
        if gz.is_file() and "gzip" in self.headers.get("Accept-Encoding", ""):
            target = gz
            headers["Content-Encoding"] = "gzip"
            headers["Vary"] = "Accept-Encoding"
        self._send(200, target.read_bytes(), ctype, headers)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
    )
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    server.daemon_threads = True
    log.info("serving on http://%s:%d (data %s, UI %s)", config.HOST, config.PORT,
             config.DB_PATH, config.WEB_DIR)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
