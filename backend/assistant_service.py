"""Evidence-bounded assistant responses for the current UNDERTOW analysis."""
import os
import re
import json
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    # Environment variables are still supported when python-dotenv is absent.
    pass

try:
    from openai import OpenAI
except ImportError:  # optional until the backend requirements are installed
    OpenAI = None


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
    """Call an OpenAI-compatible provider only with explicit backend configuration.

    The browser never sees these settings. An empty configuration intentionally
    returns ``None`` so the evidence-bounded deterministic assistant remains usable.
    """
    provider = os.getenv("AI_PROVIDER", os.getenv("UNDERTOW_AI_PROVIDER", "")).strip().lower()
    api_key = os.getenv("AI_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip()
    model = os.getenv("AI_MODEL", os.getenv("UNDERTOW_AI_MODEL", "")).strip()
    if provider != "openai" or not api_key or not model:
        return None
    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    system_prompt = "You are UNDERTOW Copilot, an assistant for financial transaction investigation. Use only supplied UNDERTOW records. Distinguish observed facts from interpretations, reference IDs and rules when available, never invent evidence, never call a risk score a fraud probability, and never declare wrongdoing. Suggest next checks without making analyst decisions."
    user_prompt = f"Question: {message}\n\nMinimal authorised context:\n{json.dumps(context, ensure_ascii=False, default=str)}"
    try:
        if OpenAI is not None:
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=12.0)
            response = client.responses.create(
                model=model,
                store=False,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            answer = str(getattr(response, "output_text", "")).strip()
            if answer:
                return answer

        # Keep the integration usable in minimal deployments where the optional
        # SDK is not installed. This remains backend-only and sends only the
        # bounded context prepared by the endpoint above.
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 700,
            }).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=12) as result:
            body = json.loads(result.read().decode("utf-8"))
        answer = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        return str(answer).strip() or None
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError):
        return None
    except Exception:
        return None


def ai_configuration():
    provider = os.getenv("AI_PROVIDER", os.getenv("UNDERTOW_AI_PROVIDER", "")).strip().lower()
    configured = provider == "openai" and bool(os.getenv("AI_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip()) and bool(os.getenv("AI_MODEL", os.getenv("UNDERTOW_AI_MODEL", "")).strip())
    return {"configured": configured, "provider": provider or None, "model": os.getenv("AI_MODEL", os.getenv("UNDERTOW_AI_MODEL", "")).strip() or None}
