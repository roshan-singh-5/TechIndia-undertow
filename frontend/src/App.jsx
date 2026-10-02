import { useState } from "react";
import axios from "axios";
import "./index.css";

const API_URL = "http://127.0.0.1:8000";

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