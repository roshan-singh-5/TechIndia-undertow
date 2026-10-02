import { useState } from "react";
import axios from "axios";
import ForceGraph2D from "react-force-graph-2d";
import "./index.css";

const API_URL = "http://127.0.0.1:8000";

function TransactionNetwork({ graph, onSelectAccount }) {
  const [selectedNode, setSelectedNode] = useState(null);

  if (!graph || !graph.nodes || graph.nodes.length === 0) {
    return (
      <div className="empty-state">
        No transaction network available.
      </div>
    );
  }

  const graphData = {
    nodes: graph.nodes.map((node) => ({
      ...node,
      id: node.id,
    })),

    links: graph.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      amount: edge.amount,
      transaction_count: edge.transaction_count,
    })),
  };

  const handleNodeClick = (node) => {
    setSelectedNode(node);
    onSelectAccount(node.account_id);
  };

  return (
    <div className="network-container">
      <div className="network-graph">
        <ForceGraph2D
          graphData={graphData}
          nodeLabel={(node) =>
            `${node.account_id}
Incoming: ${node.incoming_count}
Outgoing: ${node.outgoing_count}
Risk: ${node.risk_level} (${node.risk_score})`
          }
          nodeRelSize={7}
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          linkWidth={(link) =>
            Math.min(1 + link.transaction_count, 5)
          }
          linkLabel={(link) =>
            `₹${Number(link.amount).toLocaleString()}`
          }
          onNodeClick={handleNodeClick}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const label = node.account_id;
            const fontSize = Math.max(9 / globalScale, 3);

            ctx.beginPath();

            ctx.arc(
              node.x,
              node.y,
              6,
              0,
              2 * Math.PI,
              false
            );

            if (node.account_id === selectedNode?.account_id) {
              ctx.fillStyle = "#111827";
            } else if (node.risk_level === "High") {
              ctx.fillStyle = "#ef4444";
            } else if (node.risk_level === "Medium") {
              ctx.fillStyle = "#f59e0b";
            } else {
              ctx.fillStyle = "#2563eb";
            }

            ctx.fill();

            if (globalScale > 0.7) {
              ctx.font = `${fontSize}px Arial`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillStyle = "#172033";

              ctx.fillText(
                label,
                node.x,
                node.y + 12
              );
            }
          }}
        />
      </div>

      <div className="network-side-panel">
        <p className="eyebrow">NETWORK INSPECTION</p>

        {selectedNode ? (
          <>
            <h3>{selectedNode.account_id}</h3>

            <div className="network-stat">
              <span>Risk level</span>
              <strong>{selectedNode.risk_level}</strong>
            </div>

            <div className="network-stat">
              <span>Risk score</span>
              <strong>{selectedNode.risk_score}</strong>
            </div>

            <div className="network-stat">
              <span>Incoming transactions</span>
              <strong>{selectedNode.incoming_count}</strong>
            </div>

            <div className="network-stat">
              <span>Outgoing transactions</span>
              <strong>{selectedNode.outgoing_count}</strong>
            </div>

            <button
              className="investigate-button"
              onClick={() =>
                onSelectAccount(selectedNode.account_id)
              }
            >
              Open Investigation
            </button>

            <p className="network-help">
              Click another account in the network to inspect it.
            </p>
          </>
        ) : (
          <div className="network-empty">
            <div className="network-icon">◎</div>

            <h3>Select an account</h3>

            <p>
              Click any node in the transaction network to
              inspect its activity.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}


function InvestigationPanel({
  account,
  analystId,
  setAnalystId,
  note,
  setNote,
  onSave,
  saving,
  onClose,
  reviewHistory,
}) {
  if (!account) {
    return null;
  }

  return (
    <section className="panel investigation-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">ANALYST INVESTIGATION</p>

          <h3>
            Investigate {account.account_id}
          </h3>
        </div>
        <div className="investigation-status-bar">
  <div>
    <span className="status-label">
      Current Review Status
    </span>

    <strong>
      {account.review_status || "Pending"}
    </strong>
  </div>

  <span
    className={
      account.review_status === "Confirmed Suspicious"
        ? "review-status danger"
        : account.review_status === "Cleared"
        ? "review-status success"
        : "review-status pending"
    }
  >
    {account.review_status || "Pending"}
  </span>
</div>

        <button
          className="close-button"
          onClick={onClose}
        >
          ×
        </button>
      </div>
<div className="investigation-steps">

  <div className="investigation-step completed">
    <span>1</span>
    <strong>Detected</strong>
  </div>

  <div className="step-line"></div>

  <div
    className={
      account.review_status !== "Pending"
        ? "investigation-step completed"
        : "investigation-step active"
    }
  >
    <span>2</span>
    <strong>Reviewed</strong>
  </div>

  <div className="step-line"></div>

  <div
    className={
      account.review_status !== "Pending"
        ? "investigation-step completed"
        : "investigation-step"
    }
  >
    <span>3</span>
    <strong>Decision</strong>
  </div>

</div>
      <div className="investigation-grid">

        {/* Account summary */}

        <div className="investigation-summary">

          <div className="investigation-risk-card">
            <span>Risk Score</span>

            <strong>
              {account.risk_score}
            </strong>

            <small>
              {account.risk_level} Risk
            </small>
          </div>

          <div className="investigation-stat">
            <span>Incoming</span>
            <strong>
              {account.incoming_count}
            </strong>
          </div>

          <div className="investigation-stat">
            <span>Outgoing</span>
            <strong>
              {account.outgoing_count}
            </strong>
          </div>

          <div className="investigation-stat">
            <span>Review Status</span>
            <strong>
              {account.review_status || "Pending"}
            </strong>
          </div>

        </div>


        {/* Detection reasons */}

        <div className="detection-reasons">

          <p className="eyebrow">
            DETECTION SIGNALS
          </p>

          <h4>
            Why was this account flagged?
          </h4>

          {account.reasons &&
          account.reasons.length > 0 ? (
            <div className="reason-list">
              {account.reasons.map((reason, index) => (
                <div
                  className="reason-item"
                  key={index}
                >
                  <span className="reason-number">
                    {index + 1}
                  </span>

                  <span>
                    {reason}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">
              No detection reasons available.
            </p>
          )}

        </div>


        {/* Analyst review */}

        <div className="review-form">

          <p className="eyebrow">
            ANALYST REVIEW
          </p>

          <label>
            Analyst ID
          </label>

          <input
            type="text"
            placeholder="Enter analyst ID"
            value={analystId}
            onChange={(e) =>
              setAnalystId(e.target.value)
            }
          />

          <label>
            Investigation Note
          </label>

          <textarea
            placeholder="Add investigation notes..."
            rows="5"
            value={note}
            onChange={(e) =>
              setNote(e.target.value)
            }
          />

          <div className="review-actions">

  <button
    className="confirm-button"
    onClick={() =>
      onSave("Confirmed Suspicious")
    }
    disabled={saving}
  >
    <span>⚠</span>

    {saving
      ? "Saving..."
      : "Confirm Suspicious"}
  </button>

  <button
    className="clear-button"
    onClick={() =>
      onSave("Cleared")
    }
    disabled={saving}
  >
    <span>✓</span>

    {saving
      ? "Saving..."
      : "Clear Account"}
  </button>

</div>

        </div>

      </div>

{reviewHistory.length > 0 && (
  <div className="audit-trail">

    <div className="audit-header">
      <div>
        <p className="eyebrow">
          AUDIT TRAIL
        </p>

        <h4>
          Review History
        </h4>
      </div>

      <span className="audit-count">
        {reviewHistory.length} Review
        {reviewHistory.length !== 1
          ? "s"
          : ""}
      </span>
    </div>


    <div className="audit-list">

      {[...reviewHistory]
        .reverse()
        .map((review, index) => (

          <div
            className="audit-item"
            key={`${review.reviewed_at}-${index}`}
          >

            <div className="audit-marker">
              {review.status ===
              "Confirmed Suspicious"
                ? "!"
                : review.status ===
                  "Cleared"
                ? "✓"
                : "•"}
            </div>


            <div className="audit-content">

              <div className="audit-top">

                <strong>
                  {review.status}
                </strong>

                <span>
                  {new Date(
                    review.reviewed_at
                  ).toLocaleString()}
                </span>

              </div>


              <div className="audit-analyst">

                Analyst:
                {" "}
                <strong>
                  {review.analyst_id}
                </strong>

              </div>


              {review.note && (
                <p className="audit-note">
                  {review.note}
                </p>
              )}

            </div>

          </div>

        ))}

    </div>

  </div>
)}

    </section>
  );
}


function App() {

  const loadReviewHistory = async (accountId) => {
  try {
    const response = await axios.get(
      `${API_URL}/api/reviews/${accountId}`
    );

    setReviewHistory(
      response.data.history || []
    );
  } catch (err) {
    console.error(
      "Could not load review history:",
      err
    );

    setReviewHistory([]);
  }
};
  const [file, setFile] = useState(null);

  const [data, setData] = useState(null);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const [search, setSearch] = useState("");

  const [riskFilter, setRiskFilter] = useState("All");

  const [selectedAccountId, setSelectedAccountId] =
    useState(null);

  const [analystId, setAnalystId] = useState("");

  const [note, setNote] = useState("");

  const [savingReview, setSavingReview] =
    useState(false);

  const [reviewHistory, setReviewHistory] =
  useState([]);


  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
    setError("");
  };


  const analyzeFile = async () => {
    if (!file) {
      setError("Please select a CSV file first.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();

      formData.append("file", file);

      const response = await axios.post(
        `${API_URL}/api/analyze`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );

      const payload = response.data || {};
      const normalizedAccounts = Array.isArray(payload.accounts)
        ? payload.accounts
        : Array.isArray(payload.accounts_data)
        ? payload.accounts_data
        : [];

      setData({
        ...payload,
        accounts: normalizedAccounts,
        accounts_data: normalizedAccounts,
        alerts: Array.isArray(payload.alerts) ? payload.alerts : [],
        graph: payload.graph && Array.isArray(payload.graph.nodes) && Array.isArray(payload.graph.edges)
          ? payload.graph
          : { nodes: [], edges: [] },
        summary: payload.summary && typeof payload.summary === "object"
          ? payload.summary
          : {
              transactions: payload.transactions ?? 0,
              accounts: normalizedAccounts.length,
              total_amount: payload.total_amount ?? 0,
              flagged_accounts: Array.isArray(payload.alerts) ? payload.alerts.length : 0,
            },
      });

      setReviewHistory([]);
      setSelectedAccountId(null);

      setAnalystId("");

      setNote("");

    } catch (err) {
      console.error(err);

      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;

        if (typeof detail === "string") {
          setError(detail);
        } else {
          setError(
            detail.message || "Analysis failed."
          );
        }
      } else {
        setError(
          "Could not connect to the backend. Make sure FastAPI is running."
        );
      }

    } finally {
      setLoading(false);
    }
  };


  const accounts = Array.isArray(data?.accounts)
    ? data.accounts
    : Array.isArray(data?.accounts_data)
    ? data.accounts_data
    : [];

  const selectedAccount = accounts.find(
    (item) => item.account_id === selectedAccountId
  ) || null;

  const openInvestigation = (accountId) => {
    const account = accounts.find(
      (item) => item.account_id === accountId
    );

    if (!account) {
      return;
    }

    setSelectedAccountId(accountId);
    loadReviewHistory(accountId);

    setAnalystId(
      account.analyst_id || ""
    );

    setNote(
      account.review_note || ""
    );

    setError("");

    setTimeout(() => {
      document
        .getElementById("investigation-panel")
        ?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
    }, 100);
  };


  const saveReview = async (status) => {
    if (!selectedAccountId) {
      setError("Please select an account first.");
      return;
    }

    if (!analystId.trim()) {
      setError("Please enter an Analyst ID.");
      return;
    }

    setSavingReview(true);
    setError("");

    try {
      await axios.post(
        `${API_URL}/api/reviews`,
        {
          account_id: selectedAccountId,
          status: status,
          analyst_id: analystId.trim(),
          note: note.trim(),
        }
      );

      await loadReviewHistory(
  selectedAccountId
);

      /*
       * Update the account inside the existing
       * dashboard data immediately.
       */

      setData((currentData) => {
        if (!currentData) {
          return currentData;
        }

        const reviewedAt =
          new Date().toISOString();

        const currentAccounts = Array.isArray(currentData.accounts)
          ? currentData.accounts
          : Array.isArray(currentData.accounts_data)
          ? currentData.accounts_data
          : [];

        const updatedAccounts =
          currentAccounts.map((account) => {
            if (
              account.account_id !==
              selectedAccountId
            ) {
              return account;
            }

            return {
              ...account,
              review_status: status,
              analyst_id: analystId.trim(),
              review_note: note.trim(),
              reviewed_at: reviewedAt,
            };
          });

        const updatedAlerts =
          (Array.isArray(currentData.alerts) ? currentData.alerts : []).map((account) => {
            if (
              account.account_id !==
              selectedAccountId
            ) {
              return account;
            }

            return {
              ...account,
              review_status: status,
              analyst_id: analystId.trim(),
              review_note: note.trim(),
              reviewed_at: reviewedAt,
            };
          });

        const updatedNodes =
          currentData.graph.nodes.map((node) => {
            if (
              node.account_id !==
              selectedAccountId
            ) {
              return node;
            }

            return {
              ...node,
              review_status: status,
            };
          });

        return {
          ...currentData,

          accounts: updatedAccounts,
          accounts_data: updatedAccounts,
          alerts: updatedAlerts,

          graph: {
            ...currentData.graph,
            nodes: updatedNodes,
          },
        };
      });

      setError("");

    } catch (err) {
      console.error(err);

      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;

        if (typeof detail === "string") {
          setError(detail);
        } else {
          setError(
            detail.message || "Could not save review."
          );
        }
      } else {
        setError(
          "Could not save review. Make sure FastAPI is running."
        );
      }

    } finally {
      setSavingReview(false);
    }
  };


  const filteredAccounts =
    accounts.filter((account) => {

      const matchesSearch =
        account.account_id
          .toLowerCase()
          .includes(
            search.toLowerCase()
          );

      const matchesRisk =
        riskFilter === "All" ||
        account.risk_level ===
          riskFilter;

      return (
        matchesSearch &&
        matchesRisk
      );

    }) || [];


  return (
    <div className="app">

      {/* Sidebar */}

      <aside className="sidebar">

        <div className="logo">

          <div className="logo-mark">
            U
          </div>

          <div>
            <h1>UNTERTOW</h1>
            <span>
              Financial Intelligence
            </span>
          </div>

        </div>


        <nav>

          <div className="nav-item active">
            <span>▣</span>
            Dashboard
          </div>

          <div className="nav-item">
            <span>⚠</span>
            Alerts
          </div>

          <div className="nav-item">
            <span>◎</span>
            Network
          </div>

          <div className="nav-item">
            <span>▤</span>
            Transactions
          </div>

        </nav>


        <div className="sidebar-bottom">

          <div className="system-status">

            <span className="status-dot"></span>

            API Connected

          </div>

        </div>

      </aside>


      {/* Main Content */}

      <main className="main">

        <header className="topbar">

          <div>

            <p className="eyebrow">
              FINANCIAL CRIME INTELLIGENCE
            </p>

            <h2>
              Investigation Dashboard
            </h2>

          </div>


          <div className="upload-section">

            <label className="file-input">

              <input
                type="file"
                accept=".csv"
                onChange={
                  handleFileChange
                }
              />

              <span>
                {file
                  ? file.name
                  : "Choose transaction CSV"}
              </span>

            </label>


            <button
              className="analyze-button"
              onClick={analyzeFile}
              disabled={loading}
            >
              {loading
                ? "Analyzing..."
                : "Analyze CSV"}
            </button>

          </div>

        </header>


        {error && (
          <div className="error-box">
            ⚠ {error}
          </div>
        )}


        {!data && !loading && (
          <section className="welcome">

            <div className="welcome-icon">
              ⬆
            </div>

            <h3>
              Upload Transaction Data
            </h3>

            <p>
              Upload a CSV transaction file
              to start detecting suspicious
              financial activity.
            </p>

            <div className="supported">

              Required columns:

              <br />

              <code>
                transaction_id, timestamp,
                sender_account,
                receiver_account, amount
              </code>

            </div>

          </section>
        )}


        {loading && (
          <section className="loading-card">

            <div className="spinner"></div>

            <h3>
              Analyzing transaction network...
            </h3>

            <p>
              Checking transaction patterns
              and account behavior.
            </p>

          </section>
        )}


        {data && !loading && (
          <>

            {/* Metrics */}

            <section className="metrics">

              <div className="metric-card">

                <span>
                  Total Transactions
                </span>

                <strong>
                  {data.summary.transactions}
                </strong>

                <small>
                  Transactions analyzed
                </small>

              </div>


              <div className="metric-card">

                <span>
                  Total Accounts
                </span>

                <strong>
                  {data.summary.accounts}
                </strong>

                <small>
                  Unique accounts
                </small>

              </div>


              <div className="metric-card">

                <span>
                  Total Amount
                </span>

                <strong>
                  ₹
                  {Number(
                    data.summary.total_amount
                  ).toLocaleString()}
                </strong>

                <small>
                  Total transaction value
                </small>

              </div>


              <div className="metric-card danger">

                <span>
                  Flagged Accounts
                </span>

                <strong>
                  {data.summary.flagged_accounts}
                </strong>

                <small>
                  Requires investigation
                </small>

              </div>

            </section>


            {/* Alert Section */}

            <section className="panel">

              <div className="panel-header">

                <div>

                  <p className="eyebrow">
                    DETECTION ENGINE
                  </p>

                  <h3>
                    Suspicious Activity Alerts
                  </h3>

                </div>

                <span className="analysis-status">
                  {data.detection_status}
                </span>

              </div>


              {data.alerts.length === 0 ? (

                <div className="empty-state">
                  No suspicious accounts detected.
                </div>

              ) : (

                <div className="alerts">

                  {data.alerts.map(
                    (account) => (

                      <div
                        className={`alert-card ${
                          selectedAccountId ===
                          account.account_id
                            ? "selected-alert"
                            : ""
                        }`}
                        key={
                          account.account_id
                        }
                        onClick={() =>
                          openInvestigation(
                            account.account_id
                          )
                        }
                      >

                        <div className="alert-main">

                          <div className="account-avatar">
                            {account.account_id.slice(
                              -2
                            )}
                          </div>

                          <div>

                            <strong>
                              {account.account_id}
                            </strong>

                            <span>
                              {
                                account
                                  .reasons
                                  .length
                              }{" "}
                              detection signal
                              {account.reasons
                                .length !== 1
                                ? "s"
                                : ""}
                            </span>

                          </div>

                        </div>


                        <div className="alert-actions">

  <div className="risk">

    <span
      className={`risk-badge ${account.risk_level.toLowerCase()}`}
    >
      {account.risk_level}
    </span>

    <strong>
      {account.risk_score}
    </strong>

  </div>

  <button
    className="alert-investigate"
    onClick={(event) => {
      event.stopPropagation();
      openInvestigation(account.account_id);
    }}
  >
    Investigate →
  </button>

</div>

                      </div>

                    )
                  )}

                </div>

              )}

            </section>


            {/* Investigation Panel */}

            {selectedAccount && (
              <div id="investigation-panel">

                <InvestigationPanel
  account={selectedAccount}
  analystId={analystId}
  setAnalystId={setAnalystId}
  note={note}
  setNote={setNote}
  onSave={saveReview}
  saving={savingReview}
  onClose={() =>
    setSelectedAccountId(null)
  }
  reviewHistory={reviewHistory}
/>

              </div>
            )}


            {/* Transaction Network */}

            <section className="panel network-panel">

              <div className="panel-header">

                <div>

                  <p className="eyebrow">
                    TRANSACTION GRAPH
                  </p>

                  <h3>
                    Money Flow Network
                  </h3>

                </div>

                <span className="analysis-status">

                  {data.graph.nodes.length}
                  {" "}Accounts ·{" "}
                  {data.graph.edges.length}
                  {" "}Connections

                </span>

              </div>


              <TransactionNetwork
                graph={data.graph}
                onSelectAccount={
                  openInvestigation
                }
              />


              <div className="network-legend">

                <span>
                  <i className="legend-dot high"></i>
                  High Risk
                </span>

                <span>
                  <i className="legend-dot medium"></i>
                  Medium Risk
                </span>

                <span>
                  <i className="legend-dot low"></i>
                  Low Risk
                </span>

              </div>

            </section>


            {/* Accounts */}

            <section className="panel">

              <div className="panel-header">

                <div>

                  <p className="eyebrow">
                    ACCOUNT ANALYSIS
                  </p>

                  <h3>
                    Account Risk Overview
                  </h3>

                </div>


                <div className="filters">

                  <input
                    type="text"
                    placeholder="Search account..."
                    value={search}
                    onChange={(e) =>
                      setSearch(
                        e.target.value
                      )
                    }
                  />


                  <select
                    value={riskFilter}
                    onChange={(e) =>
                      setRiskFilter(
                        e.target.value
                      )
                    }
                  >

                    <option value="All">
                      All Risk
                    </option>

                    <option value="High">
                      High
                    </option>

                    <option value="Medium">
                      Medium
                    </option>

                    <option value="Low">
                      Low
                    </option>

                  </select>

                </div>

              </div>


              <div className="table-wrapper">

                <table>

                  <thead>

                    <tr>

                      <th>Account</th>
                      <th>Incoming</th>
                      <th>Outgoing</th>
                      <th>Received</th>
                      <th>Sent</th>
                      <th>Risk</th>
                      <th>Status</th>
                      <th>Action</th>

                    </tr>

                  </thead>


                  <tbody>

                    {filteredAccounts.map(
                      (account) => (

                        <tr
                          key={
                            account.account_id
                          }
                        >

                          <td>
                            <strong>
                              {account.account_id}
                            </strong>
                          </td>

                          <td>
                            {account.incoming_count}
                          </td>

                          <td>
                            {account.outgoing_count}
                          </td>

                          <td>
                            ₹
                            {Number(
                              account.incoming_amount
                            ).toLocaleString()}
                          </td>

                          <td>
                            ₹
                            {Number(
                              account.outgoing_amount
                            ).toLocaleString()}
                          </td>

                          <td>

                            <span
                              className={`risk-badge ${account.risk_level.toLowerCase()}`}
                            >
                              {account.risk_level}
                              {" · "}
                              {account.risk_score}
                            </span>

                          </td>

                          <td>

                            <span
                              className={
                                account.review_status ===
                                "Confirmed Suspicious"
                                  ? "confirmed"
                                  : account.review_status ===
                                    "Cleared"
                                  ? "cleared"
                                  : "pending"
                              }
                            >
                              {account.review_status ||
                                "Pending"}
                            </span>

                          </td>

                          <td>

                            <button
                              className="table-action"
                              onClick={() =>
                                openInvestigation(
                                  account.account_id
                                )
                              }
                            >
                              Investigate
                            </button>

                          </td>

                        </tr>

                      )
                    )}

                  </tbody>

                </table>

              </div>

            </section>


            {/* Detection explanation */}

            <section className="panel explanation">

              <p className="eyebrow">
                IMPORTANT
              </p>

              <h3>
                How to interpret these alerts
              </h3>

              <p>
                UNTERTOW identifies transaction
                patterns that may require
                investigation. A flagged account
                is a suspicious activity indicator
                and is not, by itself, proof of
                criminal activity.
              </p>

            </section>

          </>
        )}

      </main>

    </div>
  );
}

export default App;