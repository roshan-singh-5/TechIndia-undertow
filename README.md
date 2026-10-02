# UNDERTOW

UNDERTOW is a local MVP for financial-crime intelligence. It accepts authorised or synthetic transaction CSVs, highlights suspicious-pattern indicators, visualises account relationships, and records a durable analyst review trail in SQLite. A risk score is an investigation aid—not proof of fraud or criminal activity.

## Authentication

The API stores registered analyst accounts, opaque server-side sessions, and analyst review history in SQLite (`backend/undertow.db`). Passwords are salted and hashed with Python's memory-hard `scrypt`; plaintext passwords and browser-stored bearer tokens are never used. Login sets a short-lived HttpOnly cookie, while authenticated mutations require a server-issued CSRF token. New registrations always receive the `analyst` role and a server-generated analyst ID.

Copy `backend/.env.example` to `backend/.env` only if you need to override development defaults. The example contains placeholders and no secrets. Set `UNDERTOW_COOKIE_SECURE=true` when deploying over HTTPS. The built-in per-IP login throttle is a practical MVP protection; production should add a shared rate limiter, HTTPS, email verification, password reset, audit persistence, and database encryption/backups.

## Features

- Public landing page and responsive analyst workspace
- CSV validation, transaction analysis, account risk scoring, and alert queue
- Account, transaction, and network explorer views
- Directed interactive graph with risk-coloured nodes
- Analyst review statuses (`Pending`, `Confirmed Suspicious`, `Cleared`) and audit history
- Deterministic Investigation Copilot API: account facts, detector-rule contributions, evidence questions, and suggested checks; it is explicitly not an LLM or an automated decision
- Fund Trace and an Integration Hub with a clearly labelled synthetic-only Demo Bank Connector

## Stack and structure

- `backend/`: FastAPI, pandas, NetworkX
- `frontend/`: React, Vite, Axios, Recharts, react-force-graph-2d
- `backend/sample_data/transactions.csv`: synthetic demo data

## Run locally (Windows PowerShell)

In one terminal:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). The frontend expects the API at `http://127.0.0.1:8000`; set `VITE_API_URL` before starting Vite to override it.

## CSV format

Required columns are `transaction_id`, `timestamp`, `sender_account`, `receiver_account`, and `amount`. The detector also uses `sender_device`, `receiver_device`, `sender_ip`, and `receiver_ip` in the sample format. Amounts must be non-negative numeric values and timestamps must be parseable.

## API

- `POST /api/analyze` — upload CSV and return summary, accounts, alerts, graph, and transaction records
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` — persistent analyst authentication
- `GET /api/summary`, `/api/alerts`, `/api/graph`, `/api/transactions` — latest analysis
- `POST /api/demo/load` — load the repository's synthetic demo fixture
- `GET /api/copilot/{account_id}`, `GET /api/fund-trace`, `GET /api/priorities` — evidence brief, observed relationship trace, and transparent operational ordering
- `POST /api/reviews` — save an account review
- `GET /api/reviews/{account_id}` — review history

## Testing

```powershell
cd frontend; npm run build
cd ..\backend; py -m compileall main.py detector.py graph_engine.py
```

Then register an analyst account, sign in, open Integrations and use **Load Demo Dataset**, inspect the dashboard, Fund Trace, Network Explorer, and Investigation Center, then save a review. Review history is stored in SQLite and is attributed to the authenticated analyst by the server. The demo fixture and its limitations are documented in `backend/sample_data/README.md`.

## Limitations and next steps

This MVP has cookie authentication, SQLite persistence, and a local per-IP login throttle, but it is not production hardened. Before production use, add HTTPS-only deployment, a shared rate limiter, email verification and recovery, encrypted backups, retention policies, observability, automated test coverage, role administration, and formal model/rule governance.
