"""UNDERTOW API: local analysis plus cookie-authenticated analyst access."""
import hashlib
import io
import os
import re
import secrets
import sqlite3
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import Cookie, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from detector import analyze_transactions
from graph_engine import build_transaction_graph
from assistant_service import ai_configuration, deterministic_reply, optional_llm_reply

APP_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("UNDERTOW_DATABASE_PATH", APP_DIR / "undertow.db"))
SESSION_HOURS = int(os.getenv("UNDERTOW_SESSION_HOURS", "8"))
COOKIE_SECURE = os.getenv("UNDERTOW_COOKIE_SECURE", "false").lower() == "true"
FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv("UNDERTOW_FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
REQUIRED_COLUMNS = ["transaction_id", "timestamp", "sender_account", "receiver_account", "amount"]
MAX_CSV_BYTES = 10 * 1024 * 1024
COLUMN_ALIASES = {
    "transaction_id": {"transaction_id", "transactionid", "transaction id", "txn_id", "tx_id", "reference", "reference_id"},
    "sender_account": {"sender_account", "sender", "from_account", "from", "debit_account", "origin_account"},
    "receiver_account": {"receiver_account", "receiver", "to_account", "to", "credit_account", "beneficiary_account", "destination_account"},
    "amount": {"amount", "transaction_amount", "value", "transfer_amount"},
    "timestamp": {"timestamp", "transaction_timestamp", "transaction_time", "date_time", "datetime", "date"},
}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
ASSISTANT_CONVERSATIONS: dict[int, deque] = {}
ASSISTANT_ATTEMPTS: dict[int, list[float]] = {}
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
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        for name, definition in [("timezone", "TEXT NOT NULL DEFAULT 'UTC'"), ("date_format", "TEXT NOT NULL DEFAULT 'local'")]:
            if name not in columns:
                connection.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")


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
    return {"id": row["id"], "full_name": row["full_name"], "email": row["email"], "analyst_id": row["analyst_id"], "role": row["role"], "created_at": row["created_at"], "timezone": row["timezone"] if "timezone" in row.keys() else "UTC", "date_format": row["date_format"] if "date_format" in row.keys() else "local", "active": bool(row["active"])}


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


class AssistantChatRequest(BaseModel):
    message: str
    selected_account_id: str = ""

    @field_validator("message")
    @classmethod
    def valid_message(cls, value):
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 1500:
            raise ValueError("Enter a message between 1 and 1,500 characters.")
        return cleaned

    @field_validator("selected_account_id")
    @classmethod
    def valid_selected_account(cls, value):
        return value.strip()[:120]


@app.get("/api/assistant/status")
def assistant_status(user=Depends(get_current_user)):
    config = ai_configuration()
    return {"configured": config["configured"], "provider": config["provider"], "model": config["model"], "fallback": "Rule-based assistant — AI provider not configured"}


class ProfileUpdateRequest(BaseModel):
    full_name: str
    timezone: str = "UTC"
    date_format: str = "local"

    @field_validator("full_name")
    @classmethod
    def profile_name(cls, value):
        value = value.strip()
        if not 2 <= len(value) <= 120:
            raise ValueError("Display name must be between 2 and 120 characters.")
        return value

    @field_validator("timezone")
    @classmethod
    def profile_timezone(cls, value):
        return value.strip()[:64] or "UTC"

    @field_validator("date_format")
    @classmethod
    def profile_date_format(cls, value):
        if value not in {"local", "iso"}:
            raise ValueError("Date format must be local or iso.")
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


@app.get("/api/profile")
def get_profile(user=Depends(get_current_user)):
    profile = public_user(user)
    with database() as connection:
        latest_session = connection.execute("SELECT created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user["id"],)).fetchone()
        active_sessions = connection.execute("SELECT COUNT(*) AS count FROM sessions WHERE user_id = ? AND expires_at > ?", (user["id"], utc_now().isoformat())).fetchone()["count"]
    return {"profile": profile, "last_login": latest_session["created_at"] if latest_session else None, "active_sessions": active_sessions, "authentication": "Cookie-authenticated session"}


@app.patch("/api/profile")
def update_profile(payload: ProfileUpdateRequest, user=Depends(require_csrf)):
    with database() as connection:
        connection.execute("UPDATE users SET full_name = ?, timezone = ?, date_format = ? WHERE id = ?", (payload.full_name, payload.timezone, payload.date_format, user["id"]))
        updated = connection.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return {"message": "Profile preferences saved.", "profile": public_user(updated)}


@app.get("/api/profile/analytics")
def profile_analytics(days: str = "30", user=Depends(get_current_user)):
    limit = None if days == "all" else int(days) if days in {"7", "30", "90"} else 30
    since = (utc_now() - timedelta(days=limit)).isoformat() if limit else None
    query = "SELECT account_id, status, note, reviewed_at FROM reviews WHERE user_id = ?"
    values = [user["id"]]
    if since:
        query += " AND reviewed_at >= ?"; values.append(since)
    query += " ORDER BY reviewed_at DESC"
    with database() as connection:
        records = [dict(row) for row in connection.execute(query, values).fetchall()]
    status_counts = {status: sum(item["status"] == status for item in records) for status in ("Pending", "Confirmed Suspicious", "Cleared")}
    timeline = {}
    for item in records:
        day = item["reviewed_at"][:10]
        timeline[day] = timeline.get(day, 0) + 1
    return {"period": days, "review_actions": len(records), "unique_cases": len({item["account_id"] for item in records}), "status_distribution": status_counts, "updated_last_7_days": sum(datetime.fromisoformat(item["reviewed_at"]) >= utc_now() - timedelta(days=7) for item in records), "timeline": [{"date": date, "reviews": count} for date, count in sorted(timeline.items())], "recent": records[:10], "definition": "Review actions are saved review records by the authenticated analyst. Unique cases count distinct accounts in those records; no assignment or performance score is tracked."}


@app.get("/api/profile/activity")
def profile_activity(days: str = "30", user=Depends(get_current_user)):
    analytics = profile_analytics(days, user)
    events = [{"type": "review", "account_id": item["account_id"], "status": item["status"], "note": item["note"], "timestamp": item["reviewed_at"], "description": f"Recorded {item['status']} review"} for item in analytics["recent"]]
    return {"events": events, "count": len(events), "note": "Only persisted review decisions are shown; page views and unrecorded activity are not tracked."}


@app.post("/api/auth/logout")
def logout(response: Response, user=Depends(require_csrf), undertow_session: Annotated[str | None, Cookie()] = None):
    if undertow_session:
        with database() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (session_hash(undertow_session),))
    response.delete_cookie("undertow_session", path="/")
    return {"message": "Signed out."}


def _clean_column_name(value):
    return re.sub(r"[\s_-]+", " ", str(value).strip().lower()).strip()


def validate_bank_csv(contents: bytes, filename: str | None = None):
    """Parse untrusted CSV bytes without persisting or logging transaction values."""
    if not contents:
        return None, {"valid": False, "message": "Uploaded CSV file is empty.", "valid_rows": 0, "rejected_rows": 0, "errors": []}
    if len(contents) > MAX_CSV_BYTES:
        return None, {"valid": False, "message": "CSV exceeds the 10 MB upload limit.", "valid_rows": 0, "rejected_rows": 0, "errors": []}
    if filename and not filename.lower().endswith(".csv"):
        return None, {"valid": False, "message": "Only .csv files are accepted.", "valid_rows": 0, "rejected_rows": 0, "errors": []}
    try:
        text = contents.decode("utf-8-sig")
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, on_bad_lines="error")
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError):
        return None, {"valid": False, "message": "CSV is malformed or is not UTF-8 text.", "valid_rows": 0, "rejected_rows": 0, "errors": []}
    if df.empty:
        return None, {"valid": False, "message": "CSV has headers but no transaction rows.", "valid_rows": 0, "rejected_rows": 0, "errors": []}

    lookup = {_clean_column_name(column): column for column in df.columns}
    mapping = {}
    for target, aliases in COLUMN_ALIASES.items():
        source = next((lookup.get(_clean_column_name(alias)) for alias in aliases if _clean_column_name(alias) in lookup), None)
        if source:
            mapping[target] = source
    missing = [column for column in REQUIRED_COLUMNS if column not in mapping]
    preview = df.head(10).fillna("").to_dict(orient="records")
    if missing:
        return None, {"valid": False, "message": "CSV is missing required transaction fields.", "missing_columns": missing, "received_columns": list(df.columns), "column_mapping": mapping, "preview": preview, "valid_rows": 0, "rejected_rows": len(df), "errors": []}

    normalized = pd.DataFrame({target: df[source] for target, source in mapping.items()})
    for optional in ("sender_device", "receiver_device", "sender_ip", "receiver_ip", "device_id", "ip_address", "transaction_type"):
        source = lookup.get(_clean_column_name(optional))
        if source:
            normalized[optional] = df[source]
    errors = []
    normalized["amount"] = pd.to_numeric(normalized["amount"].astype(str).str.replace(",", "", regex=False).str.replace("$", "", regex=False).str.strip(), errors="coerce")
    normalized["timestamp"] = pd.to_datetime(normalized["timestamp"].astype(str).str.strip(), errors="coerce", format="mixed", utc=True)
    for index, row in normalized.iterrows():
        row_errors = []
        for column in ("transaction_id", "sender_account", "receiver_account"):
            if not str(row[column]).strip(): row_errors.append(f"{column} is required")
        if pd.isna(row["amount"]) or row["amount"] < 0: row_errors.append("amount must be a non-negative number")
        if pd.isna(row["timestamp"]): row_errors.append("timestamp is invalid")
        if row_errors: errors.append({"row": int(index) + 2, "errors": row_errors})
    for column in ("transaction_id", "sender_account", "receiver_account"):
        normalized[column] = normalized[column].astype(str).str.strip()
    duplicate_mask = normalized["transaction_id"].duplicated(keep=False) & normalized["transaction_id"].ne("")
    for index in normalized.index[duplicate_mask]:
        entry = next((item for item in errors if item["row"] == int(index) + 2), None)
        if entry: entry["errors"].append("transaction_id is duplicated")
        else: errors.append({"row": int(index) + 2, "errors": ["transaction_id is duplicated"]})
    errors.sort(key=lambda item: item["row"])
    valid = not errors
    report = {"valid": valid, "message": "CSV is ready to import." if valid else "Correct the listed rows before importing; the active analysis was not changed.", "received_columns": list(df.columns), "column_mapping": mapping, "preview": preview, "valid_rows": len(normalized) if valid else len(normalized) - len({item["row"] for item in errors}), "rejected_rows": len({item["row"] for item in errors}), "errors": errors[:100]}
    return (normalized if valid else None), report


async def read_and_validate_upload(file: UploadFile):
    contents = await file.read()
    if file.content_type and file.content_type not in {"text/csv", "application/csv", "application/vnd.ms-excel", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Only CSV uploads are accepted.")
    return validate_bank_csv(contents, file.filename)


def process_analysis(df, filename):
    global latest_analysis
    try:
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
        latest_analysis = {
            **summary,
            "summary": summary_data,
            "graph": graph,
            "transaction_records": records,
            "dataset_name": filename or "Uploaded transaction CSV",
            "data_source": "Synthetic demo dataset" if (filename or "").startswith("undertow-synthetic-demo") else "Authorised analyst-uploaded CSV",
            "analyzed_at": utc_now().isoformat(),
        }
        return latest_analysis
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to analyze this CSV. Check its format and try again.")


@app.post("/api/import/validate")
async def validate_csv_import(file: UploadFile = File(...), user=Depends(require_csrf)):
    _, report = await read_and_validate_upload(file)
    return report


@app.post("/api/import")
async def import_csv(file: UploadFile = File(...), user=Depends(require_csrf)):
    df, report = await read_and_validate_upload(file)
    if not report["valid"]:
        raise HTTPException(status_code=422, detail=report)
    return process_analysis(df, file.filename)


@app.post("/api/analyze")
async def analyze_csv(file: UploadFile = File(...), user=Depends(require_csrf)):
    """Backward-compatible alias for the validated import endpoint."""
    return await import_csv(file, user)


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


@app.post("/api/copilot/chat")
@app.post("/api/assistant/chat")
def assistant_chat(payload: AssistantChatRequest, user=Depends(get_current_user)):
    """Authenticated, bounded assistant. Conversation state is isolated per analyst session user."""
    now = time.monotonic()
    attempts = [stamp for stamp in ASSISTANT_ATTEMPTS.get(user["id"], []) if now - stamp < 60]
    if len(attempts) >= 20:
        raise HTTPException(status_code=429, detail="Too many assistant requests. Please wait a minute.")
    attempts.append(now)
    ASSISTANT_ATTEMPTS[user["id"]] = attempts
    analysis = analysis_or_404()
    history = ASSISTANT_CONVERSATIONS.setdefault(user["id"], deque(maxlen=12))
    message = payload.message
    if payload.selected_account_id and payload.selected_account_id in {item["account_id"] for item in analysis["accounts_data"]}:
        message = f"{message}\nSelected account context: {payload.selected_account_id}"
    fallback, actions = deterministic_reply(message, analysis, list(history))
    selected_id = payload.selected_account_id.strip() if payload.selected_account_id else None
    account_context = next((item for item in analysis["accounts_data"] if item["account_id"] == selected_id), None) if selected_id else None
    related = [item for item in analysis["transaction_records"] if item["sender_account"] == selected_id or item["receiver_account"] == selected_id][:12] if selected_id else []
    minimal_context = {"dataset_source": analysis.get("data_source"), "summary": analysis["summary"], "account": account_context, "related_transactions": related, "fallback_evidence": fallback[:3500]}
    llm_response = optional_llm_reply(payload.message, minimal_context)
    response = llm_response or fallback
    mode = "llm" if llm_response else "deterministic_fallback"
    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": response})
    return {"response": response, "mode": mode, "label": "Model-assisted suggestion; verify against case evidence." if llm_response else "Deterministic UNDERTOW fallback — derived from the current authorised analysis, not an AI model.", "actions": actions}


@app.post("/api/demo/load")
async def load_demo_dataset(user=Depends(require_csrf)):
    """Load only the repository's clearly labelled synthetic demo dataset."""
    sample = APP_DIR / "sample_data" / "transactions.csv"
    if not sample.exists():
        raise HTTPException(status_code=404, detail="Synthetic demo dataset is unavailable.")
    demo_file = UploadFile(filename="undertow-synthetic-demo.csv", file=io.BytesIO(sample.read_bytes()))
    return await import_csv(demo_file, user)


def rule_contributions(account):
    contributions = []
    for reason in account.get("reasons", []):
        score = 25 if "circular" in reason else 15 if "device or IP" in reason else 20
        contributions.append({"rule": reason, "score_contribution": score})
    return contributions


def priority_for(account, graph):
    """Operational ordering only; it deliberately remains separate from risk."""
    connected = sum(1 for edge in graph["edges"] if edge["source"] == account["account_id"] or edge["target"] == account["account_id"])
    score = min(100, int(account.get("risk_score", 0)) + len(account.get("reasons", [])) * 5 + min(15, connected * 2))
    label = "Urgent" if score >= 80 else "High" if score >= 60 else "Standard"
    explanation = f"Risk {account.get('risk_score', 0)}, {len(account.get('reasons', []))} signal(s), and {connected} direct relationship(s)."
    return {"priority_score": score, "priority_label": label, "priority_explanation": explanation}


@app.get("/api/priorities")
def get_priorities(user=Depends(get_current_user)):
    analysis = analysis_or_404()
    cases = [{**account, **priority_for(account, analysis["graph"])} for account in analysis["alerts"]]
    return {"cases": sorted(cases, key=lambda case: case["priority_score"], reverse=True), "definition": "Operational priority combines existing risk, configured signals, and direct graph relationships. It is not a fraud finding."}


@app.get("/api/copilot/{account_id}")
def investigation_copilot(account_id: str, user=Depends(get_current_user)):
    """Deterministic, evidence-grounded explanation; it never calls an LLM."""
    analysis = analysis_or_404()
    normalized = account_id.strip()
    account = next((item for item in analysis["accounts_data"] if item["account_id"] == normalized), None)
    if not account:
        raise HTTPException(status_code=404, detail="Account was not found in the current analysis.")
    transactions = [record for record in analysis["transaction_records"] if record["sender_account"] == normalized or record["receiver_account"] == normalized]
    connections = [edge for edge in analysis["graph"]["edges"] if str(edge["source"]) == normalized or str(edge["target"]) == normalized]
    contributions = rule_contributions(account)
    factual_summary = f"{normalized} has a {account['risk_level'].lower()} risk score of {account['risk_score']} based on {len(contributions)} configured detection signal{'s' if len(contributions) != 1 else ''}."
    questions = ["Confirm the purpose and counterparties for the recorded transfers."]
    if account["incoming_count"] and account["outgoing_count"]:
        questions.append("Review whether inbound and outbound transfers represent a rapid pass-through pattern.")
    if any("device or IP" in item["rule"] for item in contributions):
        questions.append("Validate whether shared device or IP identifiers are expected for these accounts.")
    return {
        "mode": "deterministic_template",
        "label": "Simulated investigation copilot — deterministic explanation, not an AI model.",
        "account_id": normalized,
        "case_summary": factual_summary,
        "verified_facts": {"incoming_transactions": account["incoming_count"], "outgoing_transactions": account["outgoing_count"], "incoming_value": account["incoming_amount"], "outgoing_value": account["outgoing_amount"], "connected_accounts": len(connections)},
        "rule_contributions": contributions,
        "transactions": transactions,
        "connections": connections,
        "unresolved_questions": questions,
        "suggested_checks": ["Review transaction references and account ownership evidence.", "Compare activity with the institution's authorised customer and payment context."],
        "disclaimer": "Risk indicators guide investigation and do not establish wrongdoing.",
    }


@app.get("/api/fund-trace")
def fund_trace(source: str, destination: str, user=Depends(get_current_user)):
    analysis = analysis_or_404()
    source, destination = source.strip(), destination.strip()
    if not source or not destination:
        raise HTTPException(status_code=400, detail="Source and destination accounts are required.")
    adjacency = {}
    for record in analysis["transaction_records"]:
        adjacency.setdefault(record["sender_account"], set()).add(record["receiver_account"])
    queue, parents = deque([source]), {source: None}
    while queue and destination not in parents:
        current = queue.popleft()
        for neighbor in adjacency.get(current, set()):
            if neighbor not in parents:
                parents[neighbor] = current
                queue.append(neighbor)
    if destination not in parents:
        return {"source": source, "destination": destination, "path": [], "message": "No directed relationship path was found in the current dataset."}
    accounts = []
    cursor = destination
    while cursor is not None:
        accounts.append(cursor); cursor = parents[cursor]
    accounts.reverse()
    steps, previous_time = [], None
    for sender, receiver in zip(accounts, accounts[1:]):
        candidates = [record for record in analysis["transaction_records"] if record["sender_account"] == sender and record["receiver_account"] == receiver]
        record = sorted(candidates, key=lambda item: item["timestamp"])[0]
        timestamp = datetime.fromisoformat(record["timestamp"])
        steps.append({**record, "elapsed_seconds_from_previous": int((timestamp - previous_time).total_seconds()) if previous_time else None})
        previous_time = timestamp
    return {"source": source, "destination": destination, "accounts": accounts, "path": steps, "message": "This shows observed directed relationships, not proof that the same funds moved through every step."}


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


@app.get("/api/reviews")
def get_recent_reviews(user=Depends(get_current_user)):
    """Return recent persisted analyst decisions for the authenticated workspace."""
    with database() as connection:
        history = [dict(row) for row in connection.execute(
            "SELECT account_id, status, note, analyst_id, analyst_name, reviewed_at "
            "FROM reviews ORDER BY id DESC LIMIT 20"
        ).fetchall()]
    return {"history": history, "count": len(history)}
