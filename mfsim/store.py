"""Per-user state: accounts, login sessions, uploaded statements, fund matches and saved
comparisons, in one small SQLite file (config.USERS_DB_PATH).

Passwords are PBKDF2-SHA256 hashes (standard library, no memory spike like scrypt).
Session cookies carry a random token; only its SHA-256 is stored.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone

from . import config

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pw_hash     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at  INTEGER NOT NULL
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS sessions_by_user ON sessions(user_id);
-- The original file is kept so it can be downloaded again and re-parsed if the parser
-- improves; the parsed rows are kept so a page load doesn't re-parse every file.
CREATE TABLE IF NOT EXISTS uploads (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    size         INTEGER NOT NULL,
    sha256       TEXT NOT NULL,
    uploaded_at  TEXT NOT NULL,
    data         BLOB NOT NULL,
    txns         TEXT NOT NULL,
    warnings     TEXT NOT NULL,
    UNIQUE (user_id, sha256)
);
-- The user's own choice of scheme for a fund in their statements, overriding the ISIN match.
CREATE TABLE IF NOT EXISTS matches (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fund_name  TEXT NOT NULL,
    code       INTEGER NOT NULL,
    PRIMARY KEY (user_id, fund_name)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS scenarios (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    params      TEXT NOT NULL,
    snapshot    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS scenarios_by_user ON scenarios(user_id, id);
"""

PBKDF2_ITERATIONS = 600_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8


class AuthError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    got = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(got.hex(), digest)


# A hash to check against when the username doesn't exist, so a login for an unknown user
# takes as long as one with a wrong password.
_DUMMY_HASH = hash_password(secrets.token_hex(8))


def validate_new(username: str, password: str) -> None:
    if not USERNAME_RE.match(username):
        raise AuthError("Usernames are 3–32 letters, digits, dots, dashes or underscores.")
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Passwords need at least {MIN_PASSWORD} characters.")


class _Throttle:
    """At most MAX failed logins per username per WINDOW seconds, in memory."""

    MAX, WINDOW = 10, 15 * 60

    def __init__(self):
        self.lock = threading.Lock()
        self.failures: dict[str, list[float]] = {}

    def blocked(self, key: str) -> bool:
        with self.lock:
            recent = [t for t in self.failures.get(key, []) if t > time.time() - self.WINDOW]
            self.failures[key] = recent
            return len(recent) >= self.MAX

    def fail(self, key: str) -> None:
        with self.lock:
            self.failures.setdefault(key, []).append(time.time())

    def clear(self, key: str) -> None:
        with self.lock:
            self.failures.pop(key, None)


throttle = _Throttle()


class Store:
    """A short-lived connection: open one per request, like Db."""

    def __init__(self):
        config.STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(config.USERS_DB_PATH, timeout=10)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type, *_) -> None:
        if exc_type is None:
            self.con.commit()
        self.con.close()

    @staticmethod
    def init() -> None:
        config.STATE_DIR.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(config.USERS_DB_PATH)
        con.executescript(SCHEMA)
        con.close()

    # ─── Accounts ─────────────────────────────────────────────────────────────

    def create_user(self, username: str, password: str) -> dict:
        validate_new(username, password)
        try:
            cur = self.con.execute(
                "INSERT INTO users (username, pw_hash, created_at) VALUES (?,?,?)",
                (username, hash_password(password), _now()),
            )
        except sqlite3.IntegrityError as e:
            raise AuthError("That username is taken.") from e
        return {"id": cur.lastrowid, "username": username}

    def authenticate(self, username: str, password: str) -> dict:
        key = username.lower()
        if throttle.blocked(key):
            raise AuthError("Too many failed attempts. Try again in a few minutes.")
        row = self.con.execute(
            "SELECT id, username, pw_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not check_password(password, row["pw_hash"] if row else _DUMMY_HASH) or not row:
            throttle.fail(key)
            raise AuthError("Wrong username or password.")
        throttle.clear(key)
        return {"id": row["id"], "username": row["username"]}

    def set_password(self, user_id: int, password: str) -> None:
        if len(password) < MIN_PASSWORD:
            raise AuthError(f"Passwords need at least {MIN_PASSWORD} characters.")
        self.con.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (hash_password(password), user_id))
        # Signs out every other browser.
        self.con.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def user_by_name(self, username: str) -> dict | None:
        row = self.con.execute("SELECT id, username FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict]:
        return [dict(r) for r in self.con.execute(
            "SELECT u.id, u.username, u.created_at, "
            "(SELECT COUNT(*) FROM uploads WHERE user_id = u.id) AS uploads "
            "FROM users u ORDER BY u.username"
        )]

    def delete_user(self, user_id: int) -> None:
        self.con.execute("DELETE FROM users WHERE id = ?", (user_id,))

    # ─── Sessions ─────────────────────────────────────────────────────────────

    def new_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        self.con.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        self.con.execute(
            "INSERT INTO sessions VALUES (?,?,?)",
            (hashlib.sha256(token.encode()).hexdigest(), user_id, now + config.SESSION_DAYS * 86400),
        )
        return token

    def session_user(self, token: str) -> dict | None:
        row = self.con.execute(
            "SELECT u.id, u.username FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ?",
            (hashlib.sha256(token.encode()).hexdigest(), int(time.time())),
        ).fetchone()
        return dict(row) if row else None

    def end_session(self, token: str) -> None:
        self.con.execute(
            "DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),)
        )

    # ─── Uploads ──────────────────────────────────────────────────────────────

    def add_upload(self, user_id: int, name: str, data: bytes, txns: list[dict],
                   warnings: list[str]) -> bool:
        """Stores a parsed statement. False if this user already uploaded the same file."""
        cur = self.con.execute(
            "INSERT OR IGNORE INTO uploads (user_id, name, size, sha256, uploaded_at, data, txns, warnings) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, name, len(data), hashlib.sha256(data).hexdigest(), _now(), data,
             json.dumps(txns, separators=(",", ":")), json.dumps(warnings)),
        )
        return cur.rowcount > 0

    def uploads(self, user_id: int) -> list[dict]:
        """Every upload's metadata and parsed transactions, oldest first."""
        out = []
        for r in self.con.execute(
            "SELECT id, name, size, uploaded_at, txns, warnings FROM uploads WHERE user_id = ? ORDER BY id",
            (user_id,),
        ):
            txns = json.loads(r["txns"])
            out.append({
                "id": r["id"], "name": r["name"], "size": r["size"], "uploaded_at": r["uploaded_at"],
                "count": len(txns), "warnings": json.loads(r["warnings"]), "txns": txns,
            })
        return out

    def upload_file(self, user_id: int, upload_id: int) -> tuple[str, bytes] | None:
        row = self.con.execute(
            "SELECT name, data FROM uploads WHERE id = ? AND user_id = ?", (upload_id, user_id)
        ).fetchone()
        return (row["name"], row["data"]) if row else None

    def delete_upload(self, user_id: int, upload_id: int) -> bool:
        cur = self.con.execute("DELETE FROM uploads WHERE id = ? AND user_id = ?", (upload_id, user_id))
        return cur.rowcount > 0

    # ─── Fund matches ─────────────────────────────────────────────────────────

    def matches(self, user_id: int) -> dict[str, int]:
        return dict(self.con.execute(
            "SELECT fund_name, code FROM matches WHERE user_id = ?", (user_id,)
        ).fetchall())

    def set_match(self, user_id: int, fund_name: str, code: int | None) -> None:
        if code is None:
            self.con.execute(
                "DELETE FROM matches WHERE user_id = ? AND fund_name = ?", (user_id, fund_name)
            )
        else:
            self.con.execute(
                "INSERT OR REPLACE INTO matches VALUES (?,?,?)", (user_id, fund_name, code)
            )

    # ─── Saved comparisons ────────────────────────────────────────────────────

    def scenarios(self, user_id: int) -> list[dict]:
        return [
            {"id": r["id"], "name": r["name"], "created_at": r["created_at"],
             "params": json.loads(r["params"]), "snapshot": json.loads(r["snapshot"])}
            for r in self.con.execute(
                "SELECT * FROM scenarios WHERE user_id = ? ORDER BY id DESC", (user_id,)
            )
        ]

    def add_scenario(self, user_id: int, name: str, params: dict, snapshot: dict) -> int:
        cur = self.con.execute(
            "INSERT INTO scenarios (user_id, name, params, snapshot, created_at) VALUES (?,?,?,?,?)",
            (user_id, name, json.dumps(params), json.dumps(snapshot), _now()),
        )
        return cur.lastrowid

    def delete_scenario(self, user_id: int, scenario_id: int) -> bool:
        cur = self.con.execute("DELETE FROM scenarios WHERE id = ? AND user_id = ?", (scenario_id, user_id))
        return cur.rowcount > 0
