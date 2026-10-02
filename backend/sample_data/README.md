# Synthetic demo dataset

`transactions.csv` is a deliberately synthetic, local demonstration dataset. It contains normal transfers alongside fan-in, fan-out, rapid pass-through, short circular-path, and shared identifier patterns. Account IDs, device IDs, IP addresses, and values are invented and must not be interpreted as real financial activity.

The checked-in data is deterministic: it is a fixed fixture, generated for the UNDERTOW demo with seed `20261002`. It is intended to exercise the detector, graph, Copilot evidence brief, and fund trace—not to validate a production detection model. The Demo Bank Connector only loads this file and does not contact a bank or payment provider.

Required columns are documented in the repository README. Imported analyst CSVs remain distinct from this source through the analysis data-source label.
