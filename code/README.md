# Support Triage Agent (Python)

This folder contains a deterministic, terminal-based support triage agent for the HackerRank Orchestrate challenge.

## What it does

- Reads tickets from `support_tickets/support_tickets.csv`
- Uses only the local markdown corpus in `data/`
- Classifies `request_type`
- Decides `status` (`replied` vs `escalated`) with explicit escalation rules
- Retrieves top support docs via a lightweight BM25-style scorer
- Writes predictions to `support_tickets/output.csv`

## Environment setup (Windows PowerShell)

From repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

No external dependencies are required.

## Run

From repo root:

```powershell
python code/main.py --input support_tickets/support_tickets.csv --output support_tickets/output.csv
```

Optional:

```powershell
python code/main.py --top-k 5
```

## Notes on determinism and safety

- Deterministic rule-based routing and classification.
- Retrieval uses only local files in `data/`.
- High-risk or sensitive requests are escalated rather than guessed.
- No API keys or external network calls are used.
