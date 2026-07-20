# Groww Weekly Review Pulse — AI Agent (MCP)

Unattended weekly pipeline that fetches Groww app reviews from the **Play Store** and **App Store**, scrubs PII, clusters themes, summarizes with **Groq**, and delivers a short pulse via **MCP** (Google Docs + Gmail draft).

**Repo:** [ArpitDumka/groww_weekly_pulse_AIagent_MCP](https://github.com/ArpitDumka/groww_weekly_pulse_AIagent_MCP)

```
ingest → PII scrub → embed + cluster → Groq summarize → MCP deliver
```

---

## Phases (short)

| Phase | Folder | What it does |
|-------|--------|--------------|
| **0 · Foundations** | `phase-0-mcp-setup/` | Shared project skeleton, config, logging, and MCP connectivity check. |
| **1 · Ingest** | `phase-1-review-ingest/` | Fetches public reviews via `google-play-scraper` (Play) + Apple RSS (App Store). Filters (≥6 words, English, no emoji), dedupes, normalizes to `Review[]`. |
| **2 · PII scrub** | `phase-2-pii-scrub/` | Deterministic regex/denylist redaction (phones, account IDs, handles, etc.). Hard gate before any LLM call. |
| **3 · Themes & summarize** | `phase-3-theme-summarize/` | Embeds with `all-MiniLM-L6-v2`, KMeans clustering, ranks top 3 themes, **one** Groq call → validated ≤250-word `Pulse` (themes, verbatim quotes, action ideas). Local dashboard on port **8765**. |
| **4 · MCP deliver** | `phase-4-mcp-deliver/` | Renders the pulse and calls FastAPI MCP tools: `append_to_doc` + `create_email_draft` (draft only, not sent). |
| **5 · Weekly agent** | `phase-5-orchestration/` | Orchestrator + GitHub Actions (`cron` Monday 06:00 UTC). Merges each weekly fetch into a **cumulative** `corpus.json`, then re-runs scrub → summarize → deliver over the full corpus. |

Design docs: [`Docs/architecture.md`](Docs/architecture.md) · [`Docs/ImplementationPlan.md`](Docs/ImplementationPlan.md)

---

## Run on localhost (from clone)

### Prerequisites

- **Python 3.11+** (3.12 recommended)
- A **Groq API key** — [console.groq.com/keys](https://console.groq.com/keys)
- For live Google delivery: the [Google MCP server](https://github.com/ArpitDumka/Google-mcp-server) (or your fork) with OAuth `credentials.json` / `token.json`, plus a Google Doc ID and recipient email

### 1. Clone

```bash
git clone https://github.com/ArpitDumka/groww_weekly_pulse_AIagent_MCP.git
cd groww_weekly_pulse_AIagent_MCP
```

### 2. Configure env files

Copy each phase’s example env and fill in values:

```bash
# Windows (PowerShell)
Copy-Item phase-1-review-ingest\.env.example phase-1-review-ingest\.env
Copy-Item phase-2-pii-scrub\.env.example phase-2-pii-scrub\.env
Copy-Item phase-3-theme-summarize\.env.example phase-3-theme-summarize\.env
Copy-Item phase-4-mcp-deliver\.env.example phase-4-mcp-deliver\.env
```

```bash
# macOS / Linux
cp phase-1-review-ingest/.env.example phase-1-review-ingest/.env
cp phase-2-pii-scrub/.env.example phase-2-pii-scrub/.env
cp phase-3-theme-summarize/.env.example phase-3-theme-summarize/.env
cp phase-4-mcp-deliver/.env.example phase-4-mcp-deliver/.env
```

Minimum edits:

| File | Set |
|------|-----|
| `phase-3-theme-summarize/.env` | `GROQ_API_KEY=...` |
| `phase-4-mcp-deliver/.env` | `RECIPIENT=...`, `GOOGLE_DOC_ID=...`, `MCP_SERVER_BASE_URL=http://127.0.0.1:8000`, `DRY_RUN=false` for live delivery |

`.env` files are gitignored — never commit them.

### 3. One-time setup (per-phase virtualenvs)

Phases share the package name `groww_pulse`, so each phase uses its **own** `.venv`:

```bash
python phase-5-orchestration/scripts/run_weekly_pulse.py --setup
```

This creates `.venv` under each phase folder and installs dependencies (including `sentence-transformers` for Phase 3). First run may download the embedding model from Hugging Face.

### 4. Start the Google MCP server (needed for Phase 4 delivery)

In a **separate terminal**, from your MCP server checkout:

```bash
cd /path/to/Google-mcp-server   # or your local mcp-server folder
# Ensure credentials.json / token.json exist (first run opens browser OAuth)
pip install -r requirements.txt
# Use the FastAPI entrypoint (REST). This repo ships a copy at phase-5-orchestration/ci/server.py
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Health check: open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) → `{"status":"ok"}`.

> Streamlit UIs are not REST APIs. Phase 4 needs FastAPI routes `/append_to_doc` and `/create_email_draft`.

### 5. Run the full weekly pipeline locally

```bash
# Full run: fetch → scrub → summarize → deliver
python phase-5-orchestration/scripts/run_weekly_pulse.py

# Build pulse only (skip Google Doc / Gmail)
python phase-5-orchestration/scripts/run_weekly_pulse.py --dry-run

# Reuse already-fetched reviews
python phase-5-orchestration/scripts/run_weekly_pulse.py --skip-fetch --dry-run

# Smaller fetch for a quick test
python phase-5-orchestration/scripts/run_weekly_pulse.py --count 500 --dry-run
```

Useful flags:

| Flag | Meaning |
|------|---------|
| `--setup` | Create venvs + install deps |
| `--dry-run` | Skip MCP delivery |
| `--skip-fetch` | Skip Phase 1 fetch/ingest |
| `--no-accumulate` | Use only this week’s batch (don’t merge into `corpus.json`) |
| `--reset-corpus` | Delete accumulated corpus before merging |
| `--count N` | Reviews to fetch per store |
| `--week-of YYYY-MM-DD` | Reporting week anchor (default: most recent Monday) |

Each weekly run **merges** new reviews into `phase-1-review-ingest/data/output/corpus.json` (deduped by review id), then re-scrubs and re-summarizes the **full** corpus.

### 6. View the dashboard (localhost:8765)

After Phase 3 has produced `pulse.json`:

```bash
cd phase-3-theme-summarize
python scripts/serve_pulse.py --pulse data/output/pulse.json --port 8765
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The dashboard **live-reloads** when `pulse.json` changes and shows corpus total + “new this run” counts when accumulation metadata is present.

### 6b. Public dashboard on Vercel (static)

The same dashboard can be exported as static HTML (no Python on Vercel):

```bash
cd phase-3-theme-summarize
python scripts/serve_pulse.py --pulse data/output/pulse.json --export ../public/index.html
```

Then deploy the repo on [vercel.com](https://vercel.com) with **Root Directory** = repo root and **Output Directory** = `public` (see `vercel.json`). Connect the GitHub repo — each push to `main` that updates `public/index.html` refreshes the public URL.

### 7. Run phases individually (optional)

```bash
# Phase 1 — fetch + normalize
cd phase-1-review-ingest
.venv\Scripts\python scripts/fetch_reviews.py --count 2000 --output-dir data/raw   # Windows
# .venv/bin/python scripts/fetch_reviews.py --count 2000 --output-dir data/raw   # macOS/Linux
.venv\Scripts\python -m groww_pulse.phases.phase_1_ingestion.run_ingest --app-store data/raw/app_store_reviews.csv --play-store data/raw/play_store_reviews.csv --output data/output/normalized_reviews.json

# Phase 2 — scrub
cd ../phase-2-pii-scrub
.venv\Scripts\python -m groww_pulse.phases.phase_2_pii.run_scrub --input ../phase-1-review-ingest/data/output/corpus.json --output data/output/scrubbed_reviews.json

# Phase 3 — cluster + summarize
cd ../phase-3-theme-summarize
.venv\Scripts\python -m groww_pulse.phases.phase_3_summarization.run_summarize --input ../phase-2-pii-scrub/data/output/scrubbed_reviews.json --output data/output/pulse.json

# Phase 4 — deliver (MCP server must be up)
cd ../phase-4-mcp-deliver
.venv\Scripts\python -m groww_pulse.phases.phase_4_delivery.run_deliver
```

---

## GitHub Actions (weekly schedule)

Workflow: [`.github/workflows/weekly-pulse.yml`](.github/workflows/weekly-pulse.yml)

- **Schedule:** Monday 06:00 UTC (`cron: "0 6 * * 1"`)
- **Manual:** Actions → **Weekly Review Pulse** → Run workflow

### Required repository secrets

**Settings → Secrets and variables → Actions**

| Secret | Purpose |
|--------|---------|
| `GROQ_API_KEY` | Phase 3 summarization |
| `GOOGLE_DOC_ID` | Target Google Doc |
| `RECIPIENT` | Gmail draft recipient |
| `GOOGLE_TOKEN_JSON` | Full contents of MCP `token.json` |
| `GOOGLE_CREDENTIALS_JSON` | Full contents of OAuth `credentials.json` |

Set the Google Cloud OAuth app to **Production** (Testing tokens expire in ~7 days).

More detail: [`phase-5-orchestration/README.md`](phase-5-orchestration/README.md)

---

## What is not in the repo

By design, these stay local / regenerable:

- `.env`, `.venv/`
- Large outputs: `corpus.json`, `scrubbed_reviews.json`, `pulse.json`, raw CSV fetches
- Google `token.json` / `credentials.json`

---

## License / notes

Public reviews are scraped for analysis only. Gmail integration creates a **draft** — it does not send email automatically.
