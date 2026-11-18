"""
User accounts: sign up, log in, and checking who is logged in.

- Passwords are never stored. We store a scrypt hash with a random salt, so
  even someone who reads the database cannot get the passwords back.
- After login the browser gets a signed token (a JWT, HS256). Every request
  sends it, and the server checks the signature, so it knows who is asking
  without a database lookup. Tokens expire after 7 days.
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

    def find(self, email):
        row = self._run("SELECT id, name, email, password_hash FROM users WHERE email = ?", (email,), fetch=True)
        if not row:
            return None
        return {"id": row[0], "name": row[1], "email": row[2], "password_hash": row[3]}

    def add(self, name, email, password_hash):
        if self.find(email):
            raise AuthError("This email already has an account. Please log in.", 409)
        self._run("INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                  (name, email, password_hash, int(time.time())))
        return self.find(email)


# ----- sign up and log in -----

def clean_email(email):
    return (email or "").strip().lower()


def public(user):
    return {"id": str(user["id"]), "name": user["name"], "email": user["email"]}


def sign_up(store, name, email, password):
    name, email = (name or "").strip(), clean_email(email)
    if not name:
        raise AuthError("Please enter your name.")
    if not EMAIL_PATTERN.match(email):
        raise AuthError("Please enter a valid email.")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise AuthError("Password must be at least " + str(MIN_PASSWORD_LENGTH) + " characters.")
    user = store.add(name, email, hash_password(password))
    return public(user), make_token(user)


def log_in(store, email, password):
    user = store.find(clean_email(email))
    # the same message for a wrong email and a wrong password, so nobody can
    # find out which emails have accounts
    if not user or not verify_password(password or "", user["password_hash"]):
        raise AuthError("Wrong email or password.", 401)
    return public(user), make_token(user)
