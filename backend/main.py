"""UNDERTOW API: local analysis plus cookie-authenticated analyst access."""
import hashlib
import io
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import Cookie, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from detector import analyze_transactions
from graph_engine import build_transaction_graph

APP_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("UNDERTOW_DATABASE_PATH", APP_DIR / "undertow.db"))
SESSION_HOURS = int(os.getenv("UNDERTOW_SESSION_HOURS", "8"))
COOKIE_SECURE = os.getenv("UNDERTOW_COOKIE_SECURE", "false").lower() == "true"
FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv("UNDERTOW_FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
REQUIRED_COLUMNS = ["transaction_id", "timestamp", "sender_account", "receiver_account", "amount"]
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
latest_analysis = None

app = FastAPI(title="UNDERTOW API", description="Financial Crime Intelligence API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-CSRF-Token"])


def database():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with database() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            analyst_id TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'analyst',
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            csrf_token TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            analyst_id TEXT NOT NULL,
            analyst_name TEXT NOT NULL,
            reviewed_at TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS reviews_account_id_idx ON reviews(account_id, reviewed_at);
        """)


initialize_database()


def utc_now():
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """scrypt is a memory-hard password hash available in Python's standard library."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = stored.split("$")
        if algorithm != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return secrets.compare_digest(candidate.hex(), expected)
    except (ValueError, TypeError):
        return False


def public_user(row):
    return {"id": row["id"], "full_name": row["full_name"], "email": row["email"], "analyst_id": row["analyst_id"], "role": row["role"], "created_at": row["created_at"]}


def session_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def login_rate_limit(request: Request):
    address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = [stamp for stamp in LOGIN_ATTEMPTS.get(address, []) if now - stamp < 900]
    if len(attempts) >= 8:
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
    LOGIN_ATTEMPTS[address] = attempts
    return address


def record_failed_login(address: str):
    LOGIN_ATTEMPTS.setdefault(address, []).append(time.monotonic())


def clear_login_attempts(address: str):
    LOGIN_ATTEMPTS.pop(address, None)


def get_current_user(undertow_session: Annotated[str | None, Cookie()] = None):
    if not undertow_session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    with database() as connection:
        row = connection.execute("""
            SELECT users.*, sessions.csrf_token, sessions.expires_at
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
        """, (session_hash(undertow_session),)).fetchone()
    if not row or not row["active"] or datetime.fromisoformat(row["expires_at"]) <= utc_now():
        raise HTTPException(status_code=401, detail="Authentication required.")
    return row


def require_csrf(request: Request, user=Depends(get_current_user)):
    token = request.headers.get("X-CSRF-Token", "")
    if not token or not secrets.compare_digest(token, user["csrf_token"]):
        raise HTTPException(status_code=403, detail="Invalid request security token.")
    return user


class RegistrationRequest(BaseModel):
    full_name: str
    email: str
    password: str
    confirm_password: str
    accept_terms: bool

    @field_validator("full_name")
    @classmethod
    def valid_name(cls, value):
        if len(value.strip()) < 2 or len(value.strip()) > 120:
            raise ValueError("Enter a full name between 2 and 120 characters.")
        return value.strip()

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized) or len(normalized) > 254:
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("password")
    @classmethod
    def strong_password(cls, value):
        if len(value) < 12 or not re.search(r"[a-z]", value) or not re.search(r"[A-Z]", value) or not re.search(r"\d", value):
            raise ValueError("Use at least 12 characters with upper-case, lower-case, and a number.")
        return value

    @field_validator("accept_terms")
    @classmethod
    def accepts_terms(cls, value):
        if not value:
            raise ValueError("You must accept the responsible-use terms.")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def login_email(cls, value):
        return value.strip().lower()


class ReviewRequest(BaseModel):
    account_id: str
    status: str
    note: str = ""

    @field_validator("status")
    @classmethod
    def valid_status(cls, value):
        if value not in {"Pending", "Confirmed Suspicious", "Cleared"}:
            raise ValueError("Status must be Pending, Confirmed Suspicious, or Cleared.")
        return value


@app.get("/")
def health_check():
    return {"app": "UNDERTOW", "status": "running", "version": "0.2.0"}


@app.post("/api/auth/register", status_code=201)
def register(payload: RegistrationRequest):
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=422, detail="Passwords do not match.")
    created_at = utc_now().isoformat()
    with database() as connection:
        analyst_id = f"ANL-{secrets.token_hex(4).upper()}"
        while connection.execute("SELECT 1 FROM users WHERE analyst_id = ?", (analyst_id,)).fetchone():
            analyst_id = f"ANL-{secrets.token_hex(4).upper()}"
        try:
            connection.execute("INSERT INTO users (full_name, email, password_hash, analyst_id, role, created_at) VALUES (?, ?, ?, ?, 'analyst', ?)", (payload.full_name, payload.email, hash_password(payload.password), analyst_id, created_at))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
    return {"message": "Registration complete. Sign in to continue.", "analyst_id": analyst_id}


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response, request: Request):
    address = login_rate_limit(request)
    with database() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = ?", (payload.email,)).fetchone()
        if not user or not user["active"] or not verify_password(payload.password, user["password_hash"]):
            record_failed_login(address)
            raise HTTPException(status_code=401, detail="Invalid email or password.")
        clear_login_attempts(address)
        raw_token, csrf_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (utc_now().isoformat(),))
        connection.execute("INSERT INTO sessions (token_hash, user_id, csrf_token, expires_at, created_at) VALUES (?, ?, ?, ?, ?)", (session_hash(raw_token), user["id"], csrf_token, (utc_now() + timedelta(hours=SESSION_HOURS)).isoformat(), utc_now().isoformat()))
    response.set_cookie("undertow_session", raw_token, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=SESSION_HOURS * 3600, path="/")
    result = public_user(user)
    result["csrf_token"] = csrf_token
    return {"user": result}


@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    result = public_user(user)
    result["csrf_token"] = user["csrf_token"]
    return {"user": result}


@app.post("/api/auth/logout")
def logout(response: Response, user=Depends(require_csrf), undertow_session: Annotated[str | None, Cookie()] = None):
    if undertow_session:
        with database() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (session_hash(undertow_session),))
    response.delete_cookie("undertow_session", path="/")
    return {"message": "Signed out."}


@app.post("/api/analyze")
async def analyze_csv(file: UploadFile = File(...), user=Depends(require_csrf)):
    global latest_analysis
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")
        df = pd.read_csv(io.BytesIO(contents))
        missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail={"message": "CSV is missing required columns.", "missing_columns": missing, "received_columns": list(df.columns)})
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        if df["amount"].isna().any() or (df["amount"] < 0).any():
            raise HTTPException(status_code=400, detail="CSV contains invalid or negative values in amount.")
        if df["timestamp"].isna().any():
            raise HTTPException(status_code=400, detail="CSV contains invalid timestamp values.")
        for column in ["transaction_id", "sender_account", "receiver_account"]:
            if df[column].isna().any() or df[column].astype(str).str.strip().eq("").any():
                raise HTTPException(status_code=400, detail=f"CSV contains empty values in {column}.")
        summary, graph = analyze_transactions(df), build_transaction_graph(df)
        risk_map = {a["account_id"]: a for a in summary["accounts_data"]}
        with database() as connection:
            for node in graph["nodes"]:
                account = risk_map.get(node["account_id"], {})
                latest_review = connection.execute("SELECT status FROM reviews WHERE account_id = ? ORDER BY id DESC LIMIT 1", (node["account_id"],)).fetchone()
                node.update(risk_score=account.get("risk_score", 0), risk_level=account.get("risk_level", "Low"), review_status=(latest_review["status"] if latest_review else "Pending"))
            for account in summary["accounts_data"]:
                prior = connection.execute("SELECT status, analyst_id, note, reviewed_at FROM reviews WHERE account_id = ? ORDER BY id DESC LIMIT 1", (account["account_id"],)).fetchone()
                account.update({"review_status": prior["status"] if prior else "Pending", "analyst_id": prior["analyst_id"] if prior else "", "review_note": prior["note"] if prior else "", "reviewed_at": prior["reviewed_at"] if prior else ""})
        records = [{key: (value.isoformat() if isinstance(value, pd.Timestamp) else value) for key, value in row.items()} for row in df.to_dict(orient="records")]
        summary_data = {key: summary[key] for key in ("transactions", "accounts", "total_amount", "flagged_accounts")}
        latest_analysis = {**summary, "summary": summary_data, "graph": graph, "transaction_records": records}
        return latest_analysis
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to analyze this CSV. Check its format and try again.")


def analysis_or_404():
    if latest_analysis is None:
        raise HTTPException(status_code=404, detail="Upload a transaction CSV first.")
    return latest_analysis


@app.get("/api/summary")
def get_summary(user=Depends(get_current_user)): return analysis_or_404()["summary"]
@app.get("/api/alerts")
def get_alerts(user=Depends(get_current_user)): return analysis_or_404()["alerts"]
@app.get("/api/graph")
def get_graph(user=Depends(get_current_user)): return analysis_or_404()["graph"]
@app.get("/api/transactions")
def get_transactions(user=Depends(get_current_user)):
    records = analysis_or_404()["transaction_records"]
    return {"transactions": records, "count": len(records)}


@app.post("/api/reviews")
def save_review(review: ReviewRequest, user=Depends(require_csrf)):
    analysis = analysis_or_404()
    account_id, note = review.account_id.strip(), review.note.strip()
    if not account_id:
        raise HTTPException(status_code=400, detail="Account ID is required.")
    if not any(account["account_id"] == account_id for account in analysis["accounts_data"]):
        raise HTTPException(status_code=404, detail=f"Account {account_id} was not found.")
    review_data = {"account_id": account_id, "status": review.status, "analyst_id": user["analyst_id"], "analyst_name": user["full_name"], "note": note, "reviewed_at": utc_now().isoformat()}
    with database() as connection:
        connection.execute("INSERT INTO reviews (account_id, status, note, analyst_id, analyst_name, reviewed_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (account_id, review.status, note, user["analyst_id"], user["full_name"], review_data["reviewed_at"], user["id"]))
        history = [dict(row) for row in connection.execute("SELECT account_id, status, note, analyst_id, analyst_name, reviewed_at FROM reviews WHERE account_id = ? ORDER BY id", (account_id,)).fetchall()]
    for account in analysis["accounts_data"]:
        if account["account_id"] == account_id:
            account.update(review_status=review.status, analyst_id=user["analyst_id"], review_note=note, reviewed_at=review_data["reviewed_at"])
    for node in analysis["graph"]["nodes"]:
        if node["account_id"] == account_id: node["review_status"] = review.status
    return {"message": "Review saved successfully.", "review": review_data, "history": history}


@app.get("/api/reviews/{account_id}")
def get_review(account_id: str, user=Depends(get_current_user)):
    normalized_account_id = account_id.strip()
    with database() as connection:
        history = [dict(row) for row in connection.execute("SELECT account_id, status, note, analyst_id, analyst_name, reviewed_at FROM reviews WHERE account_id = ? ORDER BY id", (normalized_account_id,)).fetchall()]
    return {"account_id": normalized_account_id, "history": history, "count": len(history)}
