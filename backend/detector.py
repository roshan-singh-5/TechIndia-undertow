
import pandas as pd
import networkx as nx


WINDOW_MINUTES = 10
HIGH_RISK = 60
MEDIUM_RISK = 30


def analyze_transactions(df):
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["amount"] = pd.to_numeric(df["amount"])

    # Store account-level activity.
    incoming = {}
    outgoing = {}
    account_devices = {}
    account_ips = {}

    for _, row in df.iterrows():
        sender = str(row["sender_account"]).strip()
        receiver = str(row["receiver_account"]).strip()

        incoming.setdefault(receiver, []).append(row)
        outgoing.setdefault(sender, []).append(row)

        for account, device_col, ip_col in [
            (sender, "sender_device", "sender_ip"),
            (receiver, "receiver_device", "receiver_ip"),
        ]:
            account_devices.setdefault(account, set())
            account_ips.setdefault(account, set())

            if device_col in df.columns and pd.notna(row.get(device_col)):
                value = str(row[device_col]).strip()
                if value:
                    account_devices[account].add(value)

            if ip_col in df.columns and pd.notna(row.get(ip_col)):
                value = str(row[ip_col]).strip()
                if value:
                    account_ips[account].add(value)

    accounts = sorted(
        set(df["sender_account"].astype(str))
        | set(df["receiver_account"].astype(str))
    )

    # Build a directed transaction graph.
    graph = nx.DiGraph()
    for _, row in df.iterrows():
        graph.add_edge(
            str(row["sender_account"]),
            str(row["receiver_account"]),
            timestamp=row["timestamp"],
            amount=float(row["amount"]),
        )

    # Find short circular paths. Limit cycle length for MVP performance.
    cycles = []
    try:
        for cycle in nx.simple_cycles(graph):
            if 2 <= len(cycle) <= 4:
                cycles.append(cycle)
    except Exception:
        cycles = []

    cycle_accounts = {
        account for cycle in cycles for account in cycle
    }

    # Find device/IP identifiers shared by multiple accounts.
    device_owners = {}
    ip_owners = {}

    for account in accounts:
        for device in account_devices.get(account, set()):
            device_owners.setdefault(device, set()).add(account)

        for ip in account_ips.get(account, set()):
            ip_owners.setdefault(ip, set()).add(account)

    shared_accounts = set()

    for owners in device_owners.values():
        if len(owners) >= 2:
            shared_accounts.update(owners)

    for owners in ip_owners.values():
        if len(owners) >= 2:
            shared_accounts.update(owners)

    accounts_data = []

    for account in accounts:
        reasons = []
        score = 0
        received = incoming.get(account, [])
        sent = outgoing.get(account, [])

        # Fan-in: many distinct senders within a short time window.
        fan_in_detected = False
        if len(received) >= 3:
            received_sorted = sorted(
                received, key=lambda row: row["timestamp"]
            )
            for start in range(len(received_sorted)):
                window = received_sorted[start]["timestamp"]
                nearby = [
                    row for row in received_sorted[start:]
                    if (row["timestamp"] - window).total_seconds()
                    <= WINDOW_MINUTES * 60
                ]
                counterparties = {
                    str(row["sender_account"]) for row in nearby
                }
                if len(counterparties) >= 3:
                    fan_in_detected = True
                    break

        if fan_in_detected:
            score += 20
            reasons.append(
                "Received funds from at least 3 distinct accounts "
                f"within {WINDOW_MINUTES} minutes."
            )

        # Fan-out: many distinct recipients within a short time window.
        fan_out_detected = False
        if len(sent) >= 3:
            sent_sorted = sorted(
                sent, key=lambda row: row["timestamp"]
            )
            for start in range(len(sent_sorted)):
                window = sent_sorted[start]["timestamp"]
                nearby = [
                    row for row in sent_sorted[start:]
                    if (row["timestamp"] - window).total_seconds()
                    <= WINDOW_MINUTES * 60
                ]
                counterparties = {
                    str(row["receiver_account"]) for row in nearby
                }
                if len(counterparties) >= 3:
                    fan_out_detected = True
                    break

        if fan_out_detected:
            score += 20
            reasons.append(
                "Sent funds to at least 3 distinct accounts "
                f"within {WINDOW_MINUTES} minutes."
            )

        # Pass-through: received and sent funds close in time.
        pass_through_detected = False
        for incoming_tx in received:
            for outgoing_tx in sent:
                elapsed = (
                    outgoing_tx["timestamp"] - incoming_tx["timestamp"]
                ).total_seconds()

                if (
                    0 <= elapsed <= WINDOW_MINUTES * 60
                    and float(outgoing_tx["amount"])
                    >= 0.8 * float(incoming_tx["amount"])
                ):
                    pass_through_detected = True
                    break

            if pass_through_detected:
                break

        if pass_through_detected:
            score += 20
            reasons.append(
                "Forwarded at least 80% of an incoming transaction "
                "within 10 minutes."
            )

        if account in cycle_accounts:
            score += 25
            reasons.append(
                "Account participates in a short circular transfer path."
            )

        if account in shared_accounts:
            score += 15
            reasons.append(
                "Shares a device or IP identifier with other accounts."
            )

        score = min(score, 100)

        if score >= HIGH_RISK:
            risk_level = "High"
        elif score >= MEDIUM_RISK:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        accounts_data.append({
            "account_id": account,
            "incoming_count": len(received),
            "outgoing_count": len(sent),
            "incoming_amount": round(
                sum(float(row["amount"]) for row in received), 2
            ),
            "outgoing_amount": round(
                sum(float(row["amount"]) for row in sent), 2
            ),
            "risk_score": score,
            "risk_level": risk_level,
            "reasons": reasons,
            "status": "Pending",
        })

    alerts = [
        account for account in accounts_data
        if account["risk_score"] >= MEDIUM_RISK
    ]

    return {
        "transactions": int(len(df)),
        "accounts": len(accounts),
        "total_amount": round(float(df["amount"].sum()), 2),
        "flagged_accounts": len(alerts),
        "accounts_data": accounts_data,
        "alerts": alerts,
    }