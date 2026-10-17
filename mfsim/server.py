"""HTTP server: the JSON API plus the built React app, on the standard library alone.

    python -m mfsim.server

Everything under /api except health, status and the auth endpoints needs a login session
(an HttpOnly cookie). Each user's uploaded statements, fund matches and saved comparisons
live in the users database (store.py); the NAV database stays read-only.
"""

from __future__ import annotations

import base64
import gzip
import json
import logging
import mimetypes
import re
import signal
import sys
import traceback
from dataclasses import dataclass, field
from datetime import date
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

from . import compare, config, report, tradebook
from .db import Db, DataNotReady
from .store import AuthError, Store

log = logging.getLogger("mfsim.server")

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/svg+xml", ".svg")

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
COOKIE = "mfsim_session"


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass
class Request:
    query: dict
    body: dict
    params: tuple
    user: dict | None
    token: str | None
    secure: bool


@dataclass
class Reply:
    """A JSON reply that also sets or clears the session cookie."""
    payload: dict
    session: str | None = None   # a new token, or "" to clear the cookie
    headers: dict = field(default_factory=dict)


# ─── Auth ────────────────────────────────────────────────────────────────────

def _user_reply(user: dict) -> dict:
    return {"user": {"username": user["username"]}, "signup": config.ALLOW_SIGNUP}


def api_me(req: Request) -> dict:
    return {"user": {"username": req.user["username"]} if req.user else None,
            "signup": config.ALLOW_SIGNUP}


def _credentials(body: dict) -> tuple[str, str]:
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not username or not password:
        raise ApiError(400, "Enter a username and a password.")
    return username, password


def api_login(req: Request) -> Reply:
    username, password = _credentials(req.body)
    with Store() as store:
        try:
            user = store.authenticate(username, password)
        except AuthError as e:
            raise ApiError(401, str(e)) from e
        token = store.new_session(user["id"])
    log.info("login: %s", user["username"])
    return Reply(_user_reply(user), session=token)


def api_signup(req: Request) -> Reply:
    if not config.ALLOW_SIGNUP:
        raise ApiError(403, "Sign-up is turned off. Ask the admin for an account.")
    username, password = _credentials(req.body)
    with Store() as store:
        try:
            user = store.create_user(username, password)
        except AuthError as e:
            raise ApiError(400, str(e)) from e
        token = store.new_session(user["id"])
    log.info("new account: %s", user["username"])
    return Reply(_user_reply(user), session=token)


def api_logout(req: Request) -> Reply:
    if req.token:
        with Store() as store:
            store.end_session(req.token)
    return Reply({"user": None, "signup": config.ALLOW_SIGNUP}, session="")


def api_password(req: Request) -> Reply:
    current = str(req.body.get("current") or "")
    new = str(req.body.get("new") or "")
    with Store() as store:
        try:
            store.authenticate(req.user["username"], current)
        except AuthError as e:
            raise ApiError(400, "The current password is wrong.") from e
        try:
            store.set_password(req.user["id"], new)
        except AuthError as e:
            raise ApiError(400, str(e)) from e
        token = store.new_session(req.user["id"])
    return Reply(_user_reply(req.user), session=token)


# ─── NAV data ────────────────────────────────────────────────────────────────

def api_status(_req: Request) -> dict:
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


def api_search(req: Request) -> dict:
    query = (req.query.get("q") or [""])[0]
    limit = min(int((req.query.get("limit") or ["30"])[0]), 100)
    with Db() as db:
        return {"results": db.search_funds(query, limit)}


def api_fund(req: Request) -> dict:
    code = int(req.params[0])
    with Db() as db:
        fund = db.fund(code)
    if not fund:
        raise ApiError(404, f"No scheme with code {code}.")
    return fund


# ─── The user's statements ───────────────────────────────────────────────────

def _portfolio(user_id: int) -> dict:
    """Every transaction the user has uploaded, deduplicated across files, with each fund
    matched to a scheme: their own pick if they made one, else by ISIN."""
    with Store() as store:
        uploads = store.uploads(user_id)
        picks = store.matches(user_id)
    txns, dropped, method = tradebook.dedupe([t for u in uploads for t in u["txns"]])
    with Db() as db:
        funds = compare.fund_summaries(db, txns)
        for f in funds:
            f["match_source"] = "isin" if f["match"] else None
            code = picks.get(f["name"])
            picked = db.fund(code) if code else None
            if picked and picked["nav_count"]:
                f["match"], f["match_source"] = picked, "user"
    return {
        "files": [{k: v for k, v in u.items() if k != "txns"} for u in uploads],
        "transactions": txns,
        "duplicates": {"dropped": dropped, "method": method},
        "funds": funds,
    }


def api_portfolio(req: Request) -> dict:
    return _portfolio(req.user["id"])


def api_upload(req: Request) -> dict:
    files = req.body.get("files") or []
    if not files:
        raise ApiError(400, "No files uploaded.")
    results = []
    with Store() as store:
        for f in files:
            name = str(f.get("name") or "upload")[:200]
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
            if not rows:
                results.append({"name": name, "ok": False, "count": 0, "warnings": warnings,
                                "error": "No transactions found in this file."})
                continue
            added = store.add_upload(req.user["id"], name, data, rows, warnings)
            results.append({
                "name": name, "ok": added, "count": len(rows), "warnings": warnings,
                "error": None if added else "You already uploaded this file.",
            })
    return {"results": results, "portfolio": _portfolio(req.user["id"])}


def api_delete_upload(req: Request) -> dict:
    with Store() as store:
        if not store.delete_upload(req.user["id"], int(req.params[0])):
            raise ApiError(404, "No such upload.")
    return _portfolio(req.user["id"])


def api_upload_file(req: Request) -> tuple[bytes, str, str]:
    with Store() as store:
        found = store.upload_file(req.user["id"], int(req.params[0]))
    if not found:
        raise ApiError(404, "No such upload.")
    name, data = found
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return data, ctype, name


def api_match(req: Request) -> dict:
    fund = str(req.body.get("fund") or "")
    code = req.body.get("code")
    if not fund:
        raise ApiError(400, "fund is required")
    if code is not None:
        with Db() as db:
            picked = db.fund(int(code))
        if not picked or not picked["nav_count"]:
            raise ApiError(400, f"Scheme code {code} has no NAV history.")
    with Store() as store:
        store.set_match(req.user["id"], fund, None if code is None else int(code))
    return _portfolio(req.user["id"])


# ─── Comparisons ─────────────────────────────────────────────────────────────

def _compare_args(req: Request) -> dict:
    """The user's stored transactions plus the funds, alternate and options in the body."""
    try:
        funds = [str(f) for f in req.body.get("funds") or []]
        alt_code = int(req.body["alt_code"])
        exclude_sells = bool(req.body.get("exclude_sells"))
    except (KeyError, TypeError, ValueError) as e:
        raise ApiError(400, f"Bad comparison request: {e}") from e
    pf = _portfolio(req.user["id"])
    actual_codes = {f["name"]: f["match"]["code"] for f in pf["funds"] if f["match"]}
    return {"txns": pf["transactions"], "funds": funds, "actual_codes": actual_codes,
            "alt_code": alt_code, "exclude_sells": exclude_sells}


def api_coverage(req: Request) -> dict:
    args = _compare_args(req)
    with Db() as db:
        return compare.coverage(db, args["txns"], args["funds"], args["alt_code"])


def api_compare(req: Request) -> dict:
    with Db() as db:
        return compare.run(db, **_compare_args(req))


def api_report(req: Request) -> tuple[bytes, str, str]:
    with Db() as db:
        result = compare.run(db, **_compare_args(req))
    filename = f"mf_compare_{result['as_of']}.xlsx"
    return report.build(result), XLSX_TYPE, filename


def api_scenarios(req: Request) -> dict:
    with Store() as store:
        return {"scenarios": store.scenarios(req.user["id"])}


def api_save_scenario(req: Request) -> dict:
    args = _compare_args(req)
    name = str(req.body.get("name") or "").strip()[:120]
    with Db() as db:
        result = compare.run(db, **args)
    if not name:
        name = f"{result['actual']['label']} → {result['alternate']['label']}"
    params = {"funds": args["funds"], "alt_code": args["alt_code"],
              "exclude_sells": args["exclude_sells"]}
    # What the comparison said when it was saved, for the list; opening it re-runs it.
    snapshot = {
        "as_of": result["as_of"],
        "actual_label": result["actual"]["label"],
        "alt_label": result["alternate"]["label"],
        "actual_value": result["actual"]["current_value"],
        "alt_value": result["alternate"]["current_value"],
        "actual_xirr": result["actual"]["xirr"],
        "alt_xirr": result["alternate"]["xirr"],
        "value_diff": result["verdict"]["value_diff"],
        "xirr_diff": result["verdict"]["xirr_diff"],
        "n_txns": result["n_txns"],
    }
    with Store() as store:
        store.add_scenario(req.user["id"], name, params, snapshot)
        return {"scenarios": store.scenarios(req.user["id"])}


def api_delete_scenario(req: Request) -> dict:
    with Store() as store:
        if not store.delete_scenario(req.user["id"], int(req.params[0])):
            raise ApiError(404, "No such comparison.")
        return {"scenarios": store.scenarios(req.user["id"])}


# (method, path pattern, handler, needs a login)
ROUTES = [
    ("GET", r"/api/status", api_status, False),
    ("GET", r"/api/auth/me", api_me, False),
    ("POST", r"/api/auth/login", api_login, False),
    ("POST", r"/api/auth/signup", api_signup, False),
    ("POST", r"/api/auth/logout", api_logout, False),
    ("POST", r"/api/auth/password", api_password, True),
    ("GET", r"/api/funds", api_search, True),
    ("GET", r"/api/funds/(\d+)", api_fund, True),
    ("GET", r"/api/portfolio", api_portfolio, True),
    ("POST", r"/api/uploads", api_upload, True),
    ("DELETE", r"/api/uploads/(\d+)", api_delete_upload, True),
    ("GET", r"/api/uploads/(\d+)/file", api_upload_file, True),
    ("POST", r"/api/matches", api_match, True),
    ("POST", r"/api/coverage", api_coverage, True),
    ("POST", r"/api/compare", api_compare, True),
    ("POST", r"/api/report", api_report, True),
    ("GET", r"/api/scenarios", api_scenarios, True),
    ("POST", r"/api/scenarios", api_save_scenario, True),
    ("DELETE", r"/api/scenarios/(\d+)", api_delete_scenario, True),
]
ROUTES = [(m, re.compile(p + "$"), fn, auth) for m, p, fn, auth in ROUTES]


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
            if isinstance(v, list):
                for item in v:
                    self.send_header(k, item)
            else:
                self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload, headers: dict | None = None) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
        headers = {"Cache-Control": "no-store", **(headers or {})}
        if len(body) > 2048 and "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(body, compresslevel=5)
            headers["Content-Encoding"] = "gzip"
        self._send(status, body, "application/json", headers)

    def _session_token(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie") or "")
        except Exception:
            return None
        morsel = cookie.get(COOKIE)
        return morsel.value if morsel and morsel.value else None

    def _secure(self) -> bool:
        # Caddy terminates TLS and says so; plain http on the LAN port can't use Secure.
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def _cookie_header(self, token: str, secure: bool) -> str:
        attrs = ["Path=/", "HttpOnly", "SameSite=Lax"]
        if secure:
            attrs.append("Secure")
        if token:
            attrs.append(f"Max-Age={config.SESSION_DAYS * 86400}")
        else:
            attrs.append("Max-Age=0")
        return f"{COOKIE}={token}; " + "; ".join(attrs)

    def _same_origin(self) -> bool:
        """Rejects cross-site writes: a browser sends Origin on every POST and DELETE."""
        origin = self.headers.get("Origin")
        return not origin or urlsplit(origin).netloc == self.headers.get("Host")

    def _drain(self) -> None:
        """Reads and drops a request body that won't be used. Left unread, it would be
        parsed as the next request on this keep-alive connection."""
        remaining = int(self.headers.get("Content-Length") or 0)
        if remaining > config.MAX_BODY_BYTES:
            self.close_connection = True
            return
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)

    def _read_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > config.MAX_BODY_BYTES:
            self.close_connection = True
            self._json(413, {"error": "That upload is too large."})
            return None
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "The request body isn't valid JSON."})
            return None
        if not isinstance(body, dict):
            self._json(400, {"error": "The request body must be a JSON object."})
            return None
        return body

    def _api(self, method: str, url) -> None:
        route = params = None
        allowed = False
        for m, pattern, fn, auth in ROUTES:
            match = pattern.match(url.path)
            if match:
                allowed = True
                if m == method:
                    route, params = (fn, auth), match.groups()
                    break
        if route is None:
            self._drain()
            return self._json(405 if allowed else 404, {"error": "Not found"})
        fn, needs_auth = route

        body: dict = {}
        if method in ("POST", "DELETE"):
            if not self._same_origin():
                self._drain()
                return self._json(403, {"error": "Cross-site request refused."})
            if method == "POST":
                body = self._read_body()
                if body is None:
                    return

        token = self._session_token()
        try:
            user = None
            if token:
                with Store() as store:
                    user = store.session_user(token)
            if needs_auth and not user:
                return self._json(401, {"error": "Sign in first."})
            req = Request(parse_qs(url.query), body, params, user, token, self._secure())
            result = fn(req)
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
            data, ctype, filename = result
            return self._send(200, data, ctype, {
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                "Cache-Control": "no-store",
            })
        if isinstance(result, Reply):
            headers = dict(result.headers)
            if result.session is not None:
                headers["Set-Cookie"] = self._cookie_header(result.session, self._secure())
            return self._json(200, result.payload, headers)
        self._json(200, result)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/api/health":
            return self._send(200, b"ok", "text/plain")
        if url.path.startswith("/api/"):
            return self._api("GET", url)
        self._static(url.path)

    def do_HEAD(self):
        url = urlsplit(self.path)
        if url.path.startswith("/api/"):
            return self._send(405, b"", "text/plain")
        self._static(url.path)

    def do_POST(self):
        self._api("POST", urlsplit(self.path))

    def do_DELETE(self):
        self._api("DELETE", urlsplit(self.path))

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
    Store.init()
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    server.daemon_threads = True
    log.info("serving on http://%s:%d (data %s, users %s, UI %s, sign-up %s)", config.HOST,
             config.PORT, config.DB_PATH, config.USERS_DB_PATH, config.WEB_DIR,
             "on" if config.ALLOW_SIGNUP else "off")

    # As PID 1 in a container, SIGTERM is ignored unless handled, and `docker stop` would
    # wait out its 10 s timeout.
    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
