# Phase 4 — MCP Delivery

Deliver the Phase 3 `Pulse` to **Google Docs** + **Gmail draft** via your [Google MCP server](https://github.com/ArpitDumka/Google-mcp-server).

## Prerequisites

1. Phase 3 output: `../phase-3-theme-summarize/data/output/pulse_dashboard.json`
2. Google MCP **FastAPI** server running locally (Streamlit UI is manual-only):

```bash
# In your Google-mcp-server clone
uvicorn server:app --reload --port 8000
```

3. A Google Doc ID with edit access (`GOOGLE_DOC_ID`)
4. OAuth configured on the MCP server (`GOOGLE_CREDENTIALS_JSON`, `GOOGLE_TOKEN_JSON`)

## Setup

```powershell
cd phase-4-mcp-deliver
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env
# Edit .env: RECIPIENT, GOOGLE_DOC_ID, DRY_RUN=false when ready
```

## Run

```powershell
# Preview artifacts only (no Google calls)
.venv\Scripts\python scripts\run_phase4.py --dry-run

# Live delivery
.venv\Scripts\python scripts\run_phase4.py

# Probe MCP server
.venv\Scripts\python scripts\run_phase4.py --discover-only
```

## Outputs

| File | Description |
|------|-------------|
| `data/output/pulse_document.txt` | Rendered doc body (dry-run) |
| `data/output/pulse_email.txt` | Email preview (dry-run) |
| `data/output/delivery_result.json` | Doc URL + draft ID |
| `data/output/delivery_state.json` | Idempotency state per week |

## MCP tools called

| Tool | Payload | Returns |
|------|---------|---------|
| `POST /append_to_doc` | `doc_id`, `content` | `document_id` |
| `POST /create_email_draft` | `to`, `subject`, `body` | `draft_id` |
