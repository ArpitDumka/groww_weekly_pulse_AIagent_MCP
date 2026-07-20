# Phase 5 — Weekly scheduler & end-to-end agent

Runs the whole pulse pipeline unattended, once a week, on **GitHub Actions**:

```
ingest (fresh reviews) → scrub → cluster + summarize → deliver via MCP
```

Each run **re-fetches the latest** App Store + Play Store reviews, so the pulse
always reflects new data. Delivery uses **Option A**: the Google MCP server runs
*inside the same runner* and Phase 4 calls it over `http://127.0.0.1:8000`, with
Google OAuth supplied from repo secrets (no separately hosted service).

## Files

| Path | Purpose |
|------|---------|
| `scripts/run_weekly_pulse.py` | Orchestrator — runs Phases 1→4 in order, each in its own venv |
| `ci/server.py` | FastAPI REST entrypoint overlaid onto the checked-out MCP server repo |
| `../.github/workflows/weekly-pulse.yml` | Weekly `cron` + manual `workflow_dispatch` |

## Run it locally

```bash
# one-time: create per-phase venvs and install deps
python phase-5-orchestration/scripts/run_weekly_pulse.py --setup

# full run (needs the MCP server running on MCP_SERVER_BASE_URL)
python phase-5-orchestration/scripts/run_weekly_pulse.py

# build the pulse but skip Google delivery
python phase-5-orchestration/scripts/run_weekly_pulse.py --dry-run

# reuse existing fetched reviews (skip Phase 1)
python phase-5-orchestration/scripts/run_weekly_pulse.py --skip-fetch --dry-run
```

`--week-of YYYY-MM-DD` overrides the reporting anchor (default: most recent Monday).
`--count N` / `$PULSE_FETCH_COUNT` sets reviews fetched per store.

## GitHub Actions setup

The workflow only runs once this project is a Git repo pushed to GitHub:

```bash
git init && git add . && git commit -m "Groww weekly pulse pipeline"
git remote add origin <your-github-repo>
git push -u origin main
```

Then add repo **secrets** (Settings → Secrets and variables → Actions):

| Secret | Used by | How to get it |
|--------|---------|---------------|
| `GROQ_API_KEY` | Phase 3 | https://console.groq.com/keys |
| `GOOGLE_DOC_ID` | Phase 4 | The `…/document/d/<ID>/edit` part of your Doc URL |
| `RECIPIENT` | Phase 4 | Email address for the Gmail draft |
| `GOOGLE_TOKEN_JSON` | MCP server | Contents of `token.json` (see below) |
| `GOOGLE_CREDENTIALS_JSON` | MCP server | Contents of your OAuth `credentials.json` (fallback) |

`MCP_SERVER_BASE_URL` is set to `http://127.0.0.1:8000` by the workflow — no secret needed.

### Generating `token.json` (once, locally)

The runner cannot do an interactive OAuth login, so generate the token on your
machine and paste it into the `GOOGLE_TOKEN_JSON` secret:

1. In the MCP server folder, run any tool once (e.g. start `uvicorn server:app`
   and call `/append_to_doc`). The first call opens a browser consent screen and
   writes `token.json`.
2. Copy the **entire contents** of `token.json` into the `GOOGLE_TOKEN_JSON` secret.

> **Important:** set your Google Cloud OAuth app to **Production** publishing
> status. Tokens issued while the app is in *Testing* expire after 7 days, which
> would break the weekly job. A production refresh token does not expire under
> normal use, and the deployed auth path (`IS_DEPLOYED=1`) refreshes it in place.

## Schedule

`cron: "0 6 * * 1"` → 06:00 UTC every Monday. Adjust in the workflow file, or use
**Run workflow** (manual dispatch) with an optional `dry_run` toggle to test
without writing to Google.

## Idempotency

`delivery_state.json` is ephemeral on a fresh runner, so the target Doc is written
in **append mode** — a re-run for the same week adds a timestamped section rather
than duplicating or corrupting earlier content.
