"""Evidence-bounded assistant responses for the current UNDERTOW analysis."""
import os
import re
from collections import deque


ACCOUNT_PATTERN = re.compile(r"\b[A-Za-z]{2,8}[-_]?\d{2,}\b")


def _money(value):
    return f"₹{float(value or 0):,.2f}"


def _account_id(message, history, accounts):
    valid = {item["account_id"] for item in accounts}
    for text in [message] + [item.get("content", "") for item in reversed(history[-4:])]:
        for candidate in ACCOUNT_PATTERN.findall(text):
            if candidate in valid:
                return candidate
    return None


def _actions(account_id, exists=True):
    if not account_id or not exists:
        return []
    return [
        {"label": "View Investigation", "route": "/investigations", "account_id": account_id},
        {"label": "Open Network Explorer", "route": "/network", "account_id": account_id},
        {"label": "View Related Transactions", "route": "/transactions", "account_id": account_id},
    ]


def deterministic_reply(message, analysis, history):
    """Answer only from the passed, authorised analysis object; never make decisions."""
    query = message.lower()
    accounts = analysis["accounts_data"]
    account_id = _account_id(message, history, accounts)
    account = next((item for item in accounts if item["account_id"] == account_id), None)

    if account:
        related = [item for item in analysis["transaction_records"] if item["sender_account"] == account_id or item["receiver_account"] == account_id]
        recent = sorted(related, key=lambda item: item["timestamp"], reverse=True)[:5]
        rules = "; ".join(account["reasons"]) or "No configured rule triggered for this account."
        lines = [
            f"Summary — **{account_id}** has a rule-based **{account['risk_level']}** risk score of **{account['risk_score']}**. This is an investigation indicator, not proof of wrongdoing.",
            f"Evidence — {account['incoming_count']} incoming transaction(s) totalling {_money(account['incoming_amount'])}; {account['outgoing_count']} outgoing transaction(s) totalling {_money(account['outgoing_amount'])}.",
            f"Triggered rules — {rules}",
        ]
        if recent:
            records = "; ".join(f"{item['transaction_id']} ({item['sender_account']} → {item['receiver_account']}, {_money(item['amount'])}, {item['timestamp']})" for item in recent[:3])
            lines.append(f"Relevant transactions — {records}.")
        lines.append("Suggested next checks — Review authorised account ownership, payment purpose, and counterparty evidence before recording any analyst decision.")
        return "\n\n".join(lines), _actions(account_id)

    requested = ACCOUNT_PATTERN.findall(message)
    if requested:
        return f"I could not find **{requested[0]}** in the current analysis. I will not invent account activity. Check the account ID or load the relevant authorised dataset.", []
    summary = analysis["summary"]
    if any(term in query for term in ("priority", "highest", "investigation")):
        flagged = sorted(analysis["alerts"], key=lambda item: item["risk_score"], reverse=True)[:5]
        if not flagged:
            return "There are no detector-flagged accounts in the current analysis, so there is no investigation queue to prioritise.", []
        items = "; ".join(f"{item['account_id']} ({item['risk_level']} {item['risk_score']})" for item in flagged)
        return f"Summary — Current detector-flagged accounts, ordered by existing risk score: {items}. Risk score and operational priority guide review; neither establishes fraud.", _actions(flagged[0]["account_id"])
    if any(term in query for term in ("fan-in", "fan in", "fan-out", "fan out", "rule", "scoring")):
        return "Risk rules — fan-in detects funds from at least three distinct accounts within ten minutes; fan-out detects sending to at least three distinct accounts within ten minutes; pass-through detects forwarding at least 80% of an incoming transfer within ten minutes. Short circular paths and shared device/IP identifiers are also scored. These are deterministic review signals, not findings of wrongdoing.", []
    if any(term in query for term in ("trace", "flow", "fund")):
        return "Use **Fund Trace** to select a source and destination account. It displays observed, chronological transfer relationships and elapsed time. It does not establish that the same funds moved through every step unless transaction-level evidence supports that conclusion.", []
    return (f"Summary — The current {analysis.get('data_source', 'loaded')} contains {summary['transactions']} transactions across {summary['accounts']} accounts, with {summary['flagged_accounts']} detector-flagged account(s). "
            "Ask about an account ID, risk rules, suspicious flow patterns, priorities, or fund tracing. This is a deterministic UNDERTOW fallback assistant, not an AI model."), []


def optional_llm_reply(message, context):
    """Optional adapter. It is only attempted with explicit server configuration."""
    if os.getenv("UNDERTOW_AI_PROVIDER", "").lower() != "openai" or not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=12.0)
        response = client.responses.create(model=os.getenv("UNDERTOW_AI_MODEL", "gpt-4.1-mini"), input=[
            {"role": "system", "content": "You are UNDERTOW AI. Use only the authorised, minimal context supplied. Never claim fraud, never make review decisions, and label suggested checks as suggestions."},
            {"role": "user", "content": f"Question: {message}\n\nAuthorised context: {context}"},
        ])
        return response.output_text.strip() or None
    except Exception:
        return None
