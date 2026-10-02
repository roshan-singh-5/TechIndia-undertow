
from io import BytesIO

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from detector import analyze_transactions
from graph_engine import build_transaction_graph


app = FastAPI(
    title="UNTERTOW API",
    description="Financial transaction analysis and investigation API",
    version="0.1.0",
)

# Allow the local React development server to call this API.
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

REQUIRED_COLUMNS = [
    "transaction_id",
    "timestamp",
    "sender_account",
    "receiver_account",
    "amount",
]

latest_analysis = None


@app.get("/")
def health_check():
    return {
        "app": "UNTERTOW",
        "status": "running",
        "version": "0.1.0",
    }


@app.post("/api/analyze")
async def upload_transactions(file: UploadFile = File(...)):
    global latest_analysis

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file.",
        )

    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="The uploaded CSV file is empty.",
            )

        df = pd.read_csv(BytesIO(contents))
        df.columns = df.columns.str.strip()

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in df.columns
        ]

        if missing:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Required columns are missing.",
                    "missing_columns": missing,
                    "required_columns": REQUIRED_COLUMNS,
                },
            )

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="The CSV contains no transactions.",
            )

        for column in [
            "transaction_id",
            "sender_account",
            "receiver_account",
        ]:
            df[column] = df[column].astype("string").str.strip()

        if df[[
            "transaction_id",
            "sender_account",
            "receiver_account",
        ]].isna().any().any():
            raise HTTPException(
                status_code=400,
                detail="Transaction IDs and account IDs cannot be empty.",
            )

        if (
            df[[
                "transaction_id",
                "sender_account",
                "receiver_account",
            ]] == ""
        ).any().any():
            raise HTTPException(
                status_code=400,
                detail="Transaction IDs and account IDs cannot be blank.",
            )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        if df["timestamp"].isna().any():
            raise HTTPException(
                status_code=400,
                detail="One or more timestamps are invalid.",
            )

        df["amount"] = pd.to_numeric(
            df["amount"],
            errors="coerce",
        )

        if df["amount"].isna().any() or (df["amount"] < 0).any():
            raise HTTPException(
                status_code=400,
                detail="Amounts must be valid non-negative numbers.",
            )

        if df["transaction_id"].duplicated().any():
            raise HTTPException(
                status_code=400,
                detail="Transaction IDs must be unique.",
            )

        summary = analyze_transactions(df)
        graph = build_transaction_graph(df)

        latest_analysis = {
            "summary": {
                "transactions": summary["transactions"],
                "accounts": summary["accounts"],
                "total_amount": summary["total_amount"],
                "flagged_accounts": 0,
            },
            "accounts": summary["accounts_data"],
            "alerts": [],
            "graph": graph,
            "detection_status": "Basic analysis only",
        }

        return latest_analysis

    except HTTPException:
        raise
    except (ValueError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read the CSV: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing the CSV.",
        ) from exc
    finally:
        await file.close()


@app.get("/api/summary")
def get_summary():
    if latest_analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Upload a transaction CSV first.",
        )

    return latest_analysis["summary"]


@app.get("/api/alerts")
def get_alerts():
    if latest_analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Upload a transaction CSV first.",
        )

    return latest_analysis["alerts"]


@app.get("/api/graph")
def get_graph():
    if latest_analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Upload a transaction CSV first.",
        )

    return latest_analysis["graph"]