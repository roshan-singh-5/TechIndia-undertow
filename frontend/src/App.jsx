import { useState } from "react";
import axios from "axios";
import ForceGraph2D from "react-force-graph-2d";
import "./index.css";

const API_URL = "http://127.0.0.1:8000";
function TransactionNetwork({ graph }) {
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

  return (
    <div className="network-container">
      <div className="network-graph">
        <ForceGraph2D
          graphData={graphData}
          nodeLabel={(node) =>
            `${node.account_id}\nIncoming: ${node.incoming_count}\nOutgoing: ${node.outgoing_count}`
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
          onNodeClick={(node) => setSelectedNode(node)}
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
              <span>Incoming transactions</span>
              <strong>{selectedNode.incoming_count}</strong>
            </div>

            <div className="network-stat">
              <span>Outgoing transactions</span>
              <strong>{selectedNode.outgoing_count}</strong>
            </div>

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
function App() {
  const [file, setFile] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("All");

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

      setData(response.data);
    } catch (err) {
      console.error(err);

      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;

        if (typeof detail === "string") {
          setError(detail);
        } else {
          setError(detail.message || "Analysis failed.");
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

  const filteredAccounts =
    data?.accounts?.filter((account) => {
      const matchesSearch = account.account_id
        .toLowerCase()
        .includes(search.toLowerCase());

      const matchesRisk =
        riskFilter === "All" || account.risk_level === riskFilter;

      return matchesSearch && matchesRisk;
    }) || [];

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-mark">U</div>
          <div>
            <h1>UNTERTOW</h1>
            <span>Financial Intelligence</span>
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
            <p className="eyebrow">FINANCIAL CRIME INTELLIGENCE</p>
            <h2>Investigation Dashboard</h2>
          </div>

          <div className="upload-section">
            <label className="file-input">
              <input
                type="file"
                accept=".csv"
                onChange={handleFileChange}
              />
              <span>
                {file ? file.name : "Choose transaction CSV"}
              </span>
            </label>

            <button
              className="analyze-button"
              onClick={analyzeFile}
              disabled={loading}
            >
              {loading ? "Analyzing..." : "Analyze CSV"}
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
            <div className="welcome-icon">⬆</div>

            <h3>Upload Transaction Data</h3>

            <p>
              Upload a CSV transaction file to start detecting
              suspicious financial activity.
            </p>

            <div className="supported">
              Required columns:
              <br />
              <code>
                transaction_id, timestamp, sender_account,
                receiver_account, amount
              </code>
            </div>
          </section>
        )}

        {loading && (
          <section className="loading-card">
            <div className="spinner"></div>
            <h3>Analyzing transaction network...</h3>
            <p>
              Checking transaction patterns and account behavior.
            </p>
          </section>
        )}

        {data && !loading && (
          <>
            {/* Metrics */}
            <section className="metrics">
              <div className="metric-card">
                <span>Total Transactions</span>
                <strong>{data.summary.transactions}</strong>
                <small>Transactions analyzed</small>
              </div>

              <div className="metric-card">
                <span>Total Accounts</span>
                <strong>{data.summary.accounts}</strong>
                <small>Unique accounts</small>
              </div>

              <div className="metric-card">
                <span>Total Amount</span>
                <strong>
                  ₹{Number(data.summary.total_amount).toLocaleString()}
                </strong>
                <small>Total transaction value</small>
              </div>

              <div className="metric-card danger">
                <span>Flagged Accounts</span>
                <strong>{data.summary.flagged_accounts}</strong>
                <small>Requires investigation</small>
              </div>
            </section>

            {/* Alert Section */}
            <section className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">DETECTION ENGINE</p>
                  <h3>Suspicious Activity Alerts</h3>
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
                  {data.alerts.map((account) => (
                    <div
                      className="alert-card"
                      key={account.account_id}
                    >
                      <div className="alert-main">
                        <div className="account-avatar">
                          {account.account_id.slice(-2)}
                        </div>

                        <div>
                          <strong>{account.account_id}</strong>
                          <span>
                            {account.reasons.length} detection signal
                            {account.reasons.length !== 1 ? "s" : ""}
                          </span>
                        </div>
                      </div>

                      <div className="risk">
                        <span
                          className={`risk-badge ${account.risk_level.toLowerCase()}`}
                        >
                          {account.risk_level}
                        </span>

                        <strong>{account.risk_score}</strong>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
{/* Transaction Network */}
<section className="panel network-panel">
  <div className="panel-header">
    <div>
      <p className="eyebrow">TRANSACTION GRAPH</p>
      <h3>Money Flow Network</h3>
    </div>

    <span className="analysis-status">
      {data.graph.nodes.length} Accounts ·{" "}
      {data.graph.edges.length} Connections
    </span>
  </div>

  <TransactionNetwork graph={data.graph} />
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
                  <p className="eyebrow">ACCOUNT ANALYSIS</p>
                  <h3>Account Risk Overview</h3>
                </div>

                <div className="filters">
                  <input
                    type="text"
                    placeholder="Search account..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />

                  <select
                    value={riskFilter}
                    onChange={(e) => setRiskFilter(e.target.value)}
                  >
                    <option value="All">All Risk</option>
                    <option value="High">High</option>
                    <option value="Medium">Medium</option>
                    <option value="Low">Low</option>
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
                    </tr>
                  </thead>

                  <tbody>
                    {filteredAccounts.map((account) => (
                      <tr key={account.account_id}>
                        <td>
                          <strong>{account.account_id}</strong>
                        </td>

                        <td>{account.incoming_count}</td>

                        <td>{account.outgoing_count}</td>

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
                            {account.risk_level} ·{" "}
                            {account.risk_score}
                          </span>
                        </td>

                        <td>
                          <span className="pending">
                            {account.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Detection explanation */}
            <section className="panel explanation">
              <p className="eyebrow">IMPORTANT</p>

              <h3>How to interpret these alerts</h3>

              <p>
                UNTERTOW identifies transaction patterns that may
                require investigation. A flagged account is a
                suspicious activity indicator and is not, by itself,
                proof of criminal activity.
              </p>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default App;