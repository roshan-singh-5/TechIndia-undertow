
import networkx as nx


def build_transaction_graph(df):
    """Build a directed graph from transaction records."""
    graph = nx.DiGraph()

    for _, row in df.iterrows():
        sender = str(row["sender_account"]).strip()
        receiver = str(row["receiver_account"]).strip()

        if not sender or not receiver:
            continue

        amount = float(row["amount"])

        # Add account nodes
        graph.add_node(sender, account_id=sender)
        graph.add_node(receiver, account_id=receiver)

        # Multiple transactions between the same accounts
        # are aggregated for this MVP graph.
        if graph.has_edge(sender, receiver):
            graph[sender][receiver]["amount"] += amount
            graph[sender][receiver]["transaction_count"] += 1
        else:
            graph.add_edge(
                sender,
                receiver,
                amount=amount,
                transaction_count=1,
            )

    nodes = [
        {
            "id": account,
            "account_id": account,
            "incoming_count": graph.in_degree(account),
            "outgoing_count": graph.out_degree(account),
        }
        for account in graph.nodes()
    ]

    edges = [
        {
            "source": sender,
            "target": receiver,
            "amount": round(data["amount"], 2),
            "transaction_count": data["transaction_count"],
        }
        for sender, receiver, data in graph.edges(data=True)
    ]

    return {"nodes": nodes, "edges": edges}