
import pandas as pd


def analyze_transactions(df):
    """Return basic transaction metrics and account activity."""
    incoming = df.groupby("receiver_account").agg(
        incoming_count=("transaction_id", "count"),
        incoming_amount=("amount", "sum"),
    )

    outgoing = df.groupby("sender_account").agg(
        outgoing_count=("transaction_id", "count"),
        outgoing_amount=("amount", "sum"),
    )

    incoming.index = incoming.index.astype(str)
    outgoing.index = outgoing.index.astype(str)

    account_ids = sorted(
        set(incoming.index) | set(outgoing.index)
    )

    accounts = []

    for account_id in account_ids:
        received = incoming.loc[account_id] if account_id in incoming.index else None
        sent = outgoing.loc[account_id] if account_id in outgoing.index else None

        received_count = int(received["incoming_count"]) if received is not None else 0
        sent_count = int(sent["outgoing_count"]) if sent is not None else 0
        received_amount = float(received["incoming_amount"]) if received is not None else 0.0
        sent_amount = float(sent["outgoing_amount"]) if sent is not None else 0.0

        accounts.append({
            "account_id": account_id,
            "incoming_count": received_count,
            "outgoing_count": sent_count,
            "incoming_amount": round(received_amount, 2),
            "outgoing_amount": round(sent_amount, 2),
            "risk_score": 0,
            "risk_level": "Not assessed",
            "reasons": [],
            "status": "Pending",
        })

    return {
        "transactions": int(len(df)),
        "accounts": len(account_ids),
        "total_amount": round(float(df["amount"].sum()), 2),
        "accounts_data": accounts,
    }