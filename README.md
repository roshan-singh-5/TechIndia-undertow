# UNDERTOW

**Financial Transaction Fraud Detection & Money Mule Network Investigation Platform**

UNDERTOW is a financial intelligence platform designed to help analysts identify suspicious transaction patterns, investigate potentially risky accounts, and visualize relationships between accounts using transaction network analysis.

> **Disclaimer:** UNDERTOW is an investigative decision-support tool. A risk score or alert is not proof of fraud or criminal activity. This project uses synthetic demo data unless otherwise stated.

## 1. Project Overview

Financial transaction networks can contain patterns such as multiple accounts sending funds to one account, one account distributing funds to many recipients, rapid pass-through transactions, and circular transfers. Identifying these patterns manually can be difficult.

UNDERTOW analyses transaction data, builds a directed account network, detects configurable suspicious patterns, assigns explainable risk scores, and provides an interface for analysts to review and document cases.

### Objectives
- Detect potentially suspicious transaction patterns.
- Visualize connections and flows between accounts.
- Provide transparent risk scores and reasons for alerts.
- Support analyst investigation and review workflows.
- Present transaction analytics in a unified dashboard.

## 2. Key Features

- **Transaction CSV Import:** Load transaction records for analysis.
- **Risk Detection:** Identify fan-in, fan-out, rapid pass-through, short cycles, and shared device/IP patterns where the required data is available.
- **Risk Scoring:** Calculate account-level risk scores and categorize risk levels using configurable rules.
- **Interactive Network Explorer:** Explore connected accounts and transaction relationships.
- **Investigation Center:** Review flagged accounts, record analyst notes, and manage review statuses.
- **Audit History:** View recorded investigation review actions where supported by the configured backend storage.
- **Analytics Dashboard:** Summarize account risk and transaction activity using available data.
- **Light and Dark Themes:** Switch between application themes.
- **UNDERTOW AI Assistant:** If configured and implemented, help explain analysis results using available authorized data. Availability depends on AI provider configuration; otherwise, document the implemented fallback behavior.
- **Data Integration Hub:** If implemented, demonstrate the clearly labelled simulated connector or configure supported authorized provider integrations.

Only list features as complete if they are present and working in the submitted repository.

## 3. Technology Stack

### Frontend
- React
- Vite
- Axios
- Recharts
- react-force-graph-2d
- CSS and responsive UI components

### Backend
- Python
- FastAPI
- pandas
- NetworkX

### Data and Analysis
- CSV transaction datasets
- Directed account transaction graph
- Rule-based suspicious-pattern detection
- Account-level risk scoring

### Development Tools
- Git and GitHub
- Node.js and npm
- Python virtual environment and pip

## 4. Architecture / Workflow

1. **Data Input:** The analyst uploads a transaction CSV or loads the supported demo dataset.
2. **Validation:** The backend checks the input structure and processes the transaction records.
3. **Graph Construction:** NetworkX builds a directed graph representing transfers between accounts.
4. **Pattern Detection:** The detection engine evaluates transactions and account relationships against configured rules.
5. **Risk Scoring:** The system calculates account-level scores and risk categories based on triggered rules.
6. **API Response:** FastAPI provides the processed analysis to the frontend.
7. **Visualization:** React displays dashboard metrics, alerts, account details, and the interactive network.
8. **Investigation:** Analysts review available evidence, record notes, and update supported review statuses.
9. **Audit and Reporting:** Recorded review history can be inspected and available results can be exported where implemented.

### High-Level Architecture

```text
Analyst
   |
   v
React + Vite Frontend
   |
   | HTTP / REST API
   v
FastAPI Backend
   |
   +--> CSV Validation and Processing (pandas)
   |
   +--> Transaction Graph (NetworkX)
   |
   +--> Suspicious Pattern Detection
   |
   +--> Risk Scoring
   |
   +--> Investigation / Review Services
   |
   v
Analysis Results and Review Records
   |
   v
Dashboard + Network Explorer + Investigation Center
```

## 5. Setup & Installation

### Prerequisites

Install the following:
- Python 3.10 or a compatible version supported by the project dependencies.
- Node.js and npm.
- Git.

### Clone the Repository

```bash
git clone https://github.com/roshan-singh-5/TechIndia-UNDERTOW.git
cd TechIndia-UNDERTOW
```

If the repository is private, ensure you have the required GitHub access.

### Backend Setup

Open a terminal in the project root and run:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

On macOS/Linux, activate the virtual environment with:

```bash
source venv/bin/activate
```

The backend will typically run at:

`http://127.0.0.1:8000`

FastAPI interactive API documentation is typically available at:

`http://127.0.0.1:8000/docs`

These addresses assume the default local configuration.

### Frontend Setup

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite in the terminal.

### Production Build

```bash
cd frontend
npm run build
```

Configure the frontend API base URL according to the environment variables or configuration actually used in the repository.

### Environment Variables

If the project requires environment variables, create the appropriate local environment file using the variable names documented in the project configuration or example environment file.

Do not commit API keys, passwords, tokens, or other secrets. Do not invent environment variable names; document the exact names used by the implementation.

## 6. Dataset / API Information

### Dataset

The project includes a transaction CSV at:

`backend/sample_data/transactions.csv`

Verify that this file is present in the submitted repository.

The dataset is intended for demonstration and testing. Document its source, schema, and whether it is synthetic. Do not present synthetic transactions as genuine banking records.

Document the actual CSV columns from the dataset. Typical transaction-analysis fields may include:
- Transaction identifier
- Sender account
- Receiver account
- Transaction amount
- Transaction timestamp
- Device or IP identifier, if provided

The actual column names required by the application must be taken from its CSV parser and sample dataset.

### API

The backend uses FastAPI to expose the application's analysis and investigation functionality.

Document the actual endpoints from the submitted `backend/main.py` and related routers. Use `/docs` to inspect the registered API routes.

Do not list an endpoint as available unless it exists and works in the submitted code.

## 7. Screenshots / Demo Information

Add screenshots of the actual running application to a `docs/screenshots/` directory.

Suggested screenshots:
1. `dashboard.png` — Main analytics dashboard.
2. `network-explorer.png` — Account relationship graph.
3. `investigations.png` — Investigation table and review workflow.
4. `account-details.png` — Risk reasons and account details.
5. `dark-mode.png` — Application in dark theme.
6. `ai-assistant.png` — Assistant interface, if implemented.

Embed available screenshots using relative paths, for example:

```markdown
![UNDERTOW Dashboard](docs/screenshots/dashboard.png)
```

Replace these examples with screenshots captured from the actual running project. Do not add placeholder screenshots and describe them as real product output.

### Demo Workflow

1. Start the backend and frontend.
2. Load the provided demo dataset using the supported workflow.
3. Run the transaction analysis.
4. Inspect risk categories and triggered detection rules.
5. Open the Network Explorer and investigate connected accounts.
6. Open an investigation and record a review decision if supported.

Add a demo video or hosted deployment URL here when available.

## 8. Limitations

- Rule-based detection identifies patterns that warrant investigation; it does not prove criminal activity.
- Detection quality depends on the completeness and accuracy of transaction data.
- Missing device/IP attributes limit detection of shared-identifier patterns.
- Synthetic demo data cannot represent every real-world banking scenario.
- The application is not a substitute for bank compliance procedures or human investigation.
- Review persistence, multi-user behavior, and audit durability depend on the configured storage implementation.
- Real bank integration requires an authorized provider, supported APIs, credentials, and appropriate security controls.
- AI-assisted features depend on the actual implementation and provider configuration.
- Production deployment requires additional security, privacy, monitoring, scalability, and compliance work.

Update this section to reflect the final implementation accurately.

## 9. Future Scope

- Integrate authorized bank and payment-provider APIs.
- Add streaming transaction ingestion and near-real-time monitoring.
- Improve detection with configurable rules and graph-based analytics.
- Add explainable AI assistance grounded in transaction evidence.
- Add case assignment, collaboration, and notifications.
- Add stronger audit retention and role-based access controls.
- Improve automated testing, monitoring, and deployment.
- Add controlled report generation and investigation exports.

## 10. Team Members

Update the following section with the actual team details before submission.

| Name | Role |
|---|---|
| Roshan Singh | [Actual contribution / role] |
| [Team Member 2] | [Role / contribution] |
| [Team Member 3] | [Role / contribution] |
| [Team Member 4] | [Role / contribution] |

Remove unused rows and ensure names and contributions are accurate.

## 11. Repository Structure

```text
UNDERTOW/
├── backend/
│   ├── main.py
│   ├── graph_engine.py
│   ├── detector.py
│   ├── sample_data/
│   │   └── transactions.csv
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   └── index.html
├── .gitignore
└── README.md
```

This is an illustrative structure. Update it to match the actual submitted repository, including any routers, services, tests, and configuration files.

## 12. Contributing

1. Fork the repository or create a feature branch.
2. Make focused changes.
3. Test the frontend and backend.
4. Submit a pull request with a clear description of the changes.

Do not commit secrets, virtual environments, `node_modules`, build artifacts, or private customer data.

## 13. License

Add a `LICENSE` file and specify the project's actual license before allowing reuse or redistribution.

---

**UNDERTOW — Turning transaction relationships into actionable investigative insights.**
