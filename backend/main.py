import io 
from io import BytesIO
from datetime import datetime, timezone

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from detector import analyze_transactions
from graph_engine import build_transaction_graph


app = FastAPI(
    title="UNTERTOW API",
    description="Financial transaction analysis and investigation API",
    version="0.1.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

REQUIRED_COLUMNS = [
    "transaction_id",
    "timestamp",
    "sender_account",
    "receiver_account",
    "amount",
]


latest_analysis = None

reviews = {}


# ---------------------------------------------------------
# Review model
# ---------------------------------------------------------

class ReviewRequest(BaseModel):
    account_id: str
    status: str
    analyst_id: str
    note: str = ""


# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------

@app.get("/")
def health_check():
    return {
        "app": "UNTERTOW",
        "status": "running",
        "version": "0.1.0",
    }


# ---------------------------------------------------------
# Analyze CSV
# ---------------------------------------------------------

@app.post("/api/analyze")
async def analyze_csv(file: UploadFile = File(...)):
    global latest_analysis

    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Uploaded CSV file is empty.",
            )

        df = pd.read_csv(io.BytesIO(contents))

        print("CSV columns:", list(df.columns))
        print("CSV rows:", len(df))

        required_columns = [
            "transaction_id",
            "timestamp",
            "sender_account",
            "receiver_account",
            "amount",
            "sender_device",
            "receiver_device",
            "sender_ip",
            "receiver_ip",
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "CSV is missing required columns.",
                    "missing_columns": missing_columns,
                    "received_columns": list(df.columns),
                },
            )

        df["amount"] = pd.to_numeric(
            df["amount"],
            errors="coerce",
        )

        if df["amount"].isna().any():
            raise HTTPException(
                status_code=400,
                detail="CSV contains invalid or empty values in the amount column.",
            )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        if df["timestamp"].isna().any():
            raise HTTPException(
                status_code=400,
                detail="CSV contains invalid timestamp values.",
            )

        summary = analyze_transactions(df)

        graph = build_transaction_graph(df)

        risk_map = {
            account["account_id"]: {
                "risk_score": account["risk_score"],
                "risk_level": account["risk_level"],
            }
            for account in summary["accounts_data"]
        }

        for node in graph["nodes"]:
            risk = risk_map.get(
                node["account_id"],
                {},
            )

            node["risk_score"] = risk.get(
                "risk_score",
                0,
            )

            node["risk_level"] = risk.get(
                "risk_level",
                "Low",
            )

        for node in graph["nodes"]:
            account_id = node["account_id"]

            review_history = reviews.get(
                account_id,
                [],
            )

            if review_history:
                review = review_history[-1]

                node["review_status"] = review["status"]

            else:
                node["review_status"] = "Pending"

        for account in summary["accounts_data"]:
            account_id = account["account_id"]

            review_history = reviews.get(
                account_id,
                [],
            )

            if review_history:
                review = review_history[-1]

                account["review_status"] = review["status"]
                account["analyst_id"] = review["analyst_id"]
                account["review_note"] = review["note"]
                account["reviewed_at"] = review["reviewed_at"]

            else:
                account["review_status"] = "Pending"
                account["analyst_id"] = ""
                account["review_note"] = ""
                account["reviewed_at"] = ""

        latest_analysis = {
            **summary,
            "graph": graph,
        }

        return latest_analysis

    except HTTPException:
        raise

    except Exception as e:
        import traceback

        print("\n========== ANALYZE ERROR ==========")
        traceback.print_exc()
        print("====================================\n")

        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {str(e)}",
        )
@app.get("/api/summary")
def get_summary():
    if latest_analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Upload a transaction CSV first.",
        )

    return latest_analysis["summary"]


# ---------------------------------------------------------
# Alerts
# ---------------------------------------------------------

@app.get("/api/alerts")
def get_alerts():
    if latest_analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Upload a transaction CSV first.",
        )

    return latest_analysis["alerts"]


# ---------------------------------------------------------
# Graph
# ---------------------------------------------------------

@app.get("/api/graph")
def get_graph():
    if latest_analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Upload a transaction CSV first.",
        )

    return latest_analysis["graph"]


# ---------------------------------------------------------
# Save analyst review
# ---------------------------------------------------------

@app.post("/api/reviews")
def save_review(review: ReviewRequest):
    global latest_analysis

    if latest_analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Upload a transaction CSV first.",
        )

    allowed_statuses = [
        "Pending",
        "Confirmed Suspicious",
        "Cleared",
    ]

    if review.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid review status.",
                "allowed_statuses": allowed_statuses,
            },
        )

    account_id = review.account_id.strip()
    analyst_id = review.analyst_id.strip()
    note = review.note.strip()

    if not account_id:
        raise HTTPException(
            status_code=400,
            detail="Account ID is required.",
        )

    if not analyst_id:
        raise HTTPException(
            status_code=400,
            detail="Analyst ID is required.",
        )

    # Check that account exists
    account_exists = any(
        account["account_id"] == account_id
        for account in latest_analysis["accounts"]
    )

    if not account_exists:
        raise HTTPException(
            status_code=404,
            detail=f"Account {account_id} was not found.",
        )

    reviewed_at = datetime.now(timezone.utc).isoformat()

    review_data = {
        "account_id": account_id,
        "status": review.status,
        "analyst_id": analyst_id,
        "note": note,
        "reviewed_at": reviewed_at,
    }

    # -----------------------------------------------------
    # Add review to audit history
    # -----------------------------------------------------

    if account_id not in reviews:
        reviews[account_id] = []

    reviews[account_id].append(review_data)

    # -----------------------------------------------------
    # Update current account status
    # -----------------------------------------------------

    for account in latest_analysis["accounts"]:
        if account["account_id"] == account_id:
            account["review_status"] = review.status
            account["analyst_id"] = analyst_id
            account["review_note"] = note
            account["reviewed_at"] = reviewed_at

    # -----------------------------------------------------
    # Update graph node
    # -----------------------------------------------------

    for node in latest_analysis["graph"]["nodes"]:
        if node["account_id"] == account_id:
            node["review_status"] = review.status

    return {
        "message": "Review saved successfully.",
        "review": review_data,
        "history": reviews[account_id],
    }

# ---------------------------------------------------------
# Get review
# ---------------------------------------------------------

@app.get("/api/reviews/{account_id}")
def get_review(account_id: str):
    account_id = account_id.strip()

    history = reviews.get(account_id, [])

    return {
        "account_id": account_id,
        "history": history,
        "count": len(history),
    }

    return review