"""
User accounts: sign up, log in, and checking who is logged in.

- Passwords are never stored. We store a scrypt hash with a random salt, so
  even someone who reads the database cannot get the passwords back.
- After login the browser gets a signed token (a JWT, HS256). Every request
  sends it, and the server checks the signature, so it knows who is asking
  without a database lookup. Tokens expire after 7 days.
- Forgot password: we email a 6-digit code (valid 15 minutes, 5 tries).
  Only a keyed hash of the code is saved, never the code itself.
- New accounts confirm their email with the same kind of code (when email
  sending is set up), and 5 wrong passwords in 15 minutes lock that email
  for 15 minutes, so nobody can guess passwords by trying many.
- Accounts live in Postgres when DATABASE_URL is set (the online server, a
  free Neon database), and in a local SQLite file otherwise (your laptop).

Only the Python standard library is needed, except psycopg for Postgres.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import warnings

from backend.config import PROJECT_ROOT

TOKEN_DAYS = 7
MIN_PASSWORD_LENGTH = 8
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# scrypt settings: memory-hard, so guessing passwords is slow even on GPUs
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1

DEV_SECRET = "dev-only-secret-change-me"

RESET_MINUTES = 15      # how long an emailed code works
RESET_MAX_TRIES = 5     # wrong codes allowed before it stops working
RESET_WAIT_SECONDS = 60 # no new email if one was sent less than this ago
REPORTS_PER_DAY = 10    # sale reports one user can send in 24 hours
MAX_CHECKS = 50         # past price checks kept per user
LOGIN_MAX_FAILS = 5     # wrong passwords allowed in LOGIN_LOCK_MINUTES
LOGIN_LOCK_MINUTES = 15
CODE_TABLES = {"reset": "reset_codes", "verify": "verify_codes"}


class AuthError(Exception):
    """a problem to show the user, with the HTTP status to send"""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# ----- passwords -----

def hash_password(password, salt=None):
    """'scrypt$<salt hex>$<hash hex>'"""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return "scrypt$" + salt.hex() + "$" + digest.hex()


def verify_password(password, stored):
    try:
        method, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if method != "scrypt":
        return False
    check = hash_password(password, bytes.fromhex(salt_hex)).split("$")[2]
    # compare_digest takes the same time whether it matches early or late
    return hmac.compare_digest(check, digest_hex)


# ----- tokens (JWT, HS256) -----

def _secret():
    secret = os.getenv("AUTH_SECRET")
    if not secret:
        warnings.warn("AUTH_SECRET is not set: using a development secret. Set it on the server.")
        secret = DEV_SECRET
    return secret.encode()


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(user, now=None):
    now = int(now or time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({"sub": str(user["id"]), "name": user["name"], "email": user["email"],
                               "iat": now, "exp": now + TOKEN_DAYS * 86400}).encode())
    signature = hmac.new(_secret(), (header + "." + payload).encode(), hashlib.sha256).digest()
    return header + "." + payload + "." + _b64(signature)


def read_token(token, now=None):
    """the user in a valid token, or None if it is missing, changed or expired"""
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(_secret(), (header + "." + payload).encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_unb64(signature), expected):
            return None
        data = json.loads(_unb64(payload))
    except (ValueError, AttributeError):
        return None
    if data.get("exp", 0) < (now or time.time()):
        return None
    return {"id": data["sub"], "name": data["name"], "email": data["email"]}


def user_from_header(header):
    """reads 'Authorization: Bearer <token>'"""
    if not header or not header.lower().startswith("bearer "):
        return None
    return read_token(header[7:].strip())


# ----- where accounts are saved -----

class UserStore:
    """one table, users(id, name, email, password_hash, created_at)"""

    def __init__(self, url=None):
        self.url = url if url is not None else os.getenv("DATABASE_URL", "")
        self.postgres = self.url.startswith(("postgres://", "postgresql://"))
        if self.postgres:
            import psycopg  # only needed online
            self._psycopg = psycopg
            self.mark = "%s"
        else:
            path = self.url.removeprefix("sqlite:///") if self.url else str(PROJECT_ROOT / "data" / "users.db")
            self.path = path
            self.mark = "?"
        self._create_table()

    def _connect(self):
        if self.postgres:
            return self._psycopg.connect(self.url)
        return sqlite3.connect(self.path)

    def _run(self, sql, values=(), fetch=False):
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(sql.replace("?", self.mark), values)
            row = cursor.fetchone() if fetch else None
            connection.commit()
            return row
        finally:
            connection.close()

    def _create_table(self):
        id_column = "SERIAL PRIMARY KEY" if self.postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
        self._run("CREATE TABLE IF NOT EXISTS users (id " + id_column + ", name TEXT NOT NULL, "
                  "email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at BIGINT NOT NULL)")
        # one waiting reset code per email
        self._run("CREATE TABLE IF NOT EXISTS reset_codes (email TEXT PRIMARY KEY, code_hash TEXT NOT NULL, "
                  "expires_at BIGINT NOT NULL, tries INTEGER NOT NULL, sent_at BIGINT NOT NULL)")
        # real prices users bought or sold at, collected to retrain the model
        self._run("CREATE TABLE IF NOT EXISTS sale_reports (id " + id_column + ", user_id TEXT NOT NULL, "
                  "location TEXT NOT NULL, size_sqft REAL NOT NULL, bedrooms INTEGER NOT NULL, "
                  "bathrooms REAL NOT NULL, price_lakhs REAL NOT NULL, kind TEXT NOT NULL, "
                  "our_estimate REAL NOT NULL, created_at BIGINT NOT NULL)")
        # codes that confirm a new account's email
        self._run("CREATE TABLE IF NOT EXISTS verify_codes (email TEXT PRIMARY KEY, code_hash TEXT NOT NULL, "
                  "expires_at BIGINT NOT NULL, tries INTEGER NOT NULL, sent_at BIGINT NOT NULL)")
        # wrong passwords per email, to stop password guessing
        self._run("CREATE TABLE IF NOT EXISTS login_failures (email TEXT PRIMARY KEY, fails INTEGER NOT NULL, "
                  "first_at BIGINT NOT NULL)")
        # accounts made before email confirmation existed count as confirmed
        self._add_column("users", "verified", "INTEGER NOT NULL DEFAULT 1")
        # each user's past price checks ("My checks")
        self._run("CREATE TABLE IF NOT EXISTS checks (id " + id_column + ", user_id TEXT NOT NULL, "
                  "created_at BIGINT NOT NULL, details TEXT NOT NULL)")

    def _add_column(self, table, column, definition):
        """adds a column to an existing table, once (works on SQLite and Postgres)"""
        if self.postgres:
            self._run("ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS " + column + " " + definition)
            return
        connection = self._connect()
        try:
            names = [row[1] for row in connection.execute("PRAGMA table_info(" + table + ")")]
        finally:
            connection.close()
        if column not in names:
            self._run("ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition)

    def find(self, email):
        row = self._run("SELECT id, name, email, password_hash, verified FROM users WHERE email = ?",
                        (email,), fetch=True)
        if not row:
            return None
        return {"id": row[0], "name": row[1], "email": row[2], "password_hash": row[3], "verified": bool(row[4])}

    def add(self, name, email, password_hash, verified=True):
        if self.find(email):
            raise AuthError("This email already has an account. Please log in.", 409)
        self._run("INSERT INTO users (name, email, password_hash, created_at, verified) VALUES (?, ?, ?, ?, ?)",
                  (name, email, password_hash, int(time.time()), 1 if verified else 0))
        return self.find(email)

    def set_verified(self, email):
        self._run("UPDATE users SET verified = 1 WHERE email = ?", (email,))

    # wrong-password counter

    def failures(self, email, now):
        """how many wrong passwords this email had in the last LOGIN_LOCK_MINUTES"""
        row = self._run("SELECT fails, first_at FROM login_failures WHERE email = ?", (email,), fetch=True)
        if not row or now - row[1] > LOGIN_LOCK_MINUTES * 60:
            return 0
        return row[0]

    def add_failure(self, email, now):
        if self.failures(email, now) == 0:
            self._run("DELETE FROM login_failures WHERE email = ?", (email,))
            self._run("INSERT INTO login_failures (email, fails, first_at) VALUES (?, 1, ?)", (email, now))
        else:
            self._run("UPDATE login_failures SET fails = fails + 1 WHERE email = ?", (email,))

    def clear_failures(self, email):
        self._run("DELETE FROM login_failures WHERE email = ?", (email,))

    def set_password(self, email, password_hash):
        self._run("UPDATE users SET password_hash = ? WHERE email = ?", (password_hash, email))

    # reset codes

    # emailed codes: kind "reset" (forgot password) or "verify" (confirm email)

    def save_code(self, email, code_hash, expires_at, sent_at, kind="reset"):
        self.delete_code(email, kind)
        self._run("INSERT INTO " + CODE_TABLES[kind] + " (email, code_hash, expires_at, tries, sent_at) "
                  "VALUES (?, ?, ?, 0, ?)", (email, code_hash, expires_at, sent_at))

    def get_code(self, email, kind="reset"):
        row = self._run("SELECT code_hash, expires_at, tries, sent_at FROM " + CODE_TABLES[kind]
                        + " WHERE email = ?", (email,), fetch=True)
        if not row:
            return None
        return {"code_hash": row[0], "expires_at": row[1], "tries": row[2], "sent_at": row[3]}

    def add_try(self, email, kind="reset"):
        self._run("UPDATE " + CODE_TABLES[kind] + " SET tries = tries + 1 WHERE email = ?", (email,))

    def delete_code(self, email, kind="reset"):
        self._run("DELETE FROM " + CODE_TABLES[kind] + " WHERE email = ?", (email,))

    # sale reports

    def add_report(self, user_id, location, size_sqft, bedrooms, bathrooms, price_lakhs, kind, our_estimate,
                   now=None):
        now = int(now or time.time())
        recent = self._run("SELECT COUNT(*) FROM sale_reports WHERE user_id = ? AND created_at > ?",
                           (str(user_id), now - 86400), fetch=True)[0]
        if recent >= REPORTS_PER_DAY:
            raise AuthError("Thank you, that is enough reports for today.", 429)
        self._run("INSERT INTO sale_reports (user_id, location, size_sqft, bedrooms, bathrooms, price_lakhs, "
                  "kind, our_estimate, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (str(user_id), location, float(size_sqft), int(bedrooms), float(bathrooms),
                   float(price_lakhs), kind, float(our_estimate), now))

    # my checks

    def add_check(self, user_id, details, now=None):
        """saves one price check (a dict) and keeps only the newest MAX_CHECKS per user"""
        now = int(now or time.time())
        self._run("INSERT INTO checks (user_id, created_at, details) VALUES (?, ?, ?)",
                  (str(user_id), now, json.dumps(details)))
        old = self._run("SELECT id FROM checks WHERE user_id = ? ORDER BY created_at DESC, id DESC "
                        "LIMIT 1 OFFSET " + str(MAX_CHECKS), (str(user_id),), fetch=True)
        if old:
            self._run("DELETE FROM checks WHERE user_id = ? AND id <= ?", (str(user_id), old[0]))

    def list_checks(self, user_id):
        """the user's checks, newest first"""
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(("SELECT id, created_at, details FROM checks WHERE user_id = ? "
                            "ORDER BY created_at DESC, id DESC").replace("?", self.mark), (str(user_id),))
            return [{"id": row[0], "created_at": row[1], **json.loads(row[2])} for row in cursor.fetchall()]
        finally:
            connection.close()

    def delete_check(self, user_id, check_id):
        """deletes one check, only if it belongs to this user"""
        self._run("DELETE FROM checks WHERE id = ? AND user_id = ?", (int(check_id), str(user_id)))

    def reports(self):
        """every saved sale report, as a list of dicts (for export and retraining)"""
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT location, size_sqft, bedrooms, bathrooms, price_lakhs, kind, our_estimate, "
                           "created_at FROM sale_reports ORDER BY created_at")
            names = ["location", "size_sqft", "bedrooms", "bathrooms", "price_lakhs", "kind", "our_estimate",
                     "created_at"]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
        finally:
            connection.close()


# ----- sign up and log in -----

def clean_email(email):
    return (email or "").strip().lower()


def public(user):
    return {"id": str(user["id"]), "name": user["name"], "email": user["email"]}


def sign_up(store, name, email, password, send=None, now=None):
    """creates an account. with send (email set up) the user must confirm the
    email with a 6-digit code first; returns (user, token or None)"""
    name, email = (name or "").strip(), clean_email(email)
    if not name:
        raise AuthError("Please enter your name.")
    if not EMAIL_PATTERN.match(email):
        raise AuthError("Please enter a valid email.")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise AuthError("Password must be at least " + str(MIN_PASSWORD_LENGTH) + " characters.")
    if send is None:
        # email sending is not set up (e.g. on a laptop): no confirmation step
        user = store.add(name, email, hash_password(password))
        return public(user), make_token(user)
    user = store.add(name, email, hash_password(password), verified=False)
    _send_code(store, user, send, "verify", now)
    return public(user), None  # no token until the email is confirmed


def log_in(store, email, password, now=None):
    now = int(now or time.time())
    email = clean_email(email)
    if store.failures(email, now) >= LOGIN_MAX_FAILS:
        raise AuthError("Too many wrong tries. Wait " + str(LOGIN_LOCK_MINUTES)
                        + " minutes, or reset your password.", 429)
    user = store.find(email)
    # the same message for a wrong email and a wrong password, so nobody can
    # find out which emails have accounts
    if not user or not verify_password(password or "", user["password_hash"]):
        store.add_failure(email, now)
        raise AuthError("Wrong email or password.", 401)
    store.clear_failures(email)
    if not user["verified"]:
        raise AuthError("Please confirm your email first. Enter the code we sent you.", 403)
    return public(user), make_token(user)


# ----- forgot password -----

def _code_hash(email, code):
    """keyed with AUTH_SECRET, so a leaked table does not reveal codes"""
    return hmac.new(_secret(), (email + ":" + code).encode(), hashlib.sha256).hexdigest()


def _new_code():
    return str(secrets.randbelow(10 ** 6)).zfill(6)


def _send_code(store, user, send, kind, now=None):
    """makes a 6-digit code, saves only its hash, and emails it. no new email
    if one was sent less than RESET_WAIT_SECONDS ago"""
    now = int(now or time.time())
    waiting = store.get_code(user["email"], kind)
    if waiting and now - waiting["sent_at"] < RESET_WAIT_SECONDS:
        return
    code = _new_code()
    store.save_code(user["email"], _code_hash(user["email"], code), now + RESET_MINUTES * 60, now, kind)
    send(user["email"], user["name"], code)


def _check_code(store, email, code, kind, now):
    """raises AuthError unless the code is right, not expired and not over the tries"""
    waiting = store.get_code(email, kind)
    if not waiting or waiting["expires_at"] < now:
        raise AuthError("This code has expired. Please ask for a new code.")
    if waiting["tries"] >= RESET_MAX_TRIES:
        store.delete_code(email, kind)
        raise AuthError("Too many wrong tries. Please ask for a new code.", 429)
    if not hmac.compare_digest(_code_hash(email, code), waiting["code_hash"]):
        store.add_try(email, kind)
        raise AuthError("Wrong code. Please check your email.")
    store.delete_code(email, kind)


def verify_email(store, email, code, now=None):
    """confirms a new account's email with its code and logs the user in"""
    now = int(now or time.time())
    email, code = clean_email(email), (code or "").strip().replace(" ", "")
    _check_code(store, email, code, "verify", now)
    store.set_verified(email)
    user = store.find(email)
    return public(user), make_token(user)


def resend_verification(store, email, send, now=None):
    """sends a new confirmation code to an account that is not confirmed yet"""
    user = store.find(clean_email(email))
    if user and not user["verified"]:
        _send_code(store, user, send, "verify", now)


def start_reset(store, email, send, now=None):
    """emails a 6-digit code if the email has an account.

    It answers the same way either way, so nobody can find out which emails
    have accounts. send(email, name, code) does the actual sending.
    """
    now = int(now or time.time())
    email = clean_email(email)
    if not EMAIL_PATTERN.match(email):
        raise AuthError("Please enter a valid email.")
    user = store.find(email)
    if not user:
        return
    _send_code(store, user, send, "reset", now)


def finish_reset(store, email, code, password, now=None):
    """checks the code, saves the new password and logs the user in"""
    now = int(now or time.time())
    email, code = clean_email(email), (code or "").strip().replace(" ", "")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise AuthError("Password must be at least " + str(MIN_PASSWORD_LENGTH) + " characters.")
    _check_code(store, email, code, "reset", now)
    store.set_password(email, hash_password(password))
    store.set_verified(email)      # the code proves the email is theirs
    store.clear_failures(email)
    user = store.find(email)
    return public(user), make_token(user)
