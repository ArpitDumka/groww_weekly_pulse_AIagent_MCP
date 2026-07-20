# Phase 0 — Foundations & MCP setup · Evaluation

**Objective:** A working project skeleton with the Google Docs and Gmail MCP servers reachable and discoverable.

## What we test

| # | Test | Method | Pass condition |
|---|------|--------|----------------|
| 1 | Project boots | Run the setup/entry script | Exits 0, no import/config errors |
| 2 | Config loads | Load `.env` (date window, theme cap, recipient alias) | All required keys present and valid |
| 3 | MCP servers reachable | Connect to Google Docs + Gmail MCP servers | Both connect without auth errors |
| 4 | Tool discovery | List tools for each server | Expected Docs + Gmail tools appear |
| 5 | Schema read | Read input schema for create-doc and create-draft tools | Schemas retrieved and logged |
| 6 | Logging works | Trigger a sample log + run summary scaffold | Log + summary produced |

## Test data
- No real reviews needed. Use a "hello MCP" script that only lists tools and reads schemas.

## Exit criteria
- [ ] Repo skeleton, dependencies, and config are in place.
- [ ] Both MCP servers connect successfully (auth handled by server/connector).
- [ ] Required Docs and Gmail tools are discoverable and their schemas readable.
- [ ] A run summary scaffold prints without error.
- [ ] No direct Google API/OAuth code exists in the integration path.

## Out of scope
- Real review ingestion, summarization, or sending drafts.
