# Phase 4 — Delivery via MCP · Evaluation

**Objective:** Write the pulse to **Google Docs** and create a **Gmail draft**, both exclusively via MCP servers.

## What we test

| # | Test | Method | Pass condition |
|---|------|--------|----------------|
| 1 | Doc creation | Call Google Docs MCP tool with a `Pulse` | Doc created; URL returned |
| 2 | Doc formatting | Inspect created doc | Headings + bullets render; ≤250-word note intact |
| 3 | Draft creation | Call Gmail MCP tool | Draft created to self/alias; draft id returned |
| 4 | Draft content | Inspect draft | Contains or correctly links the pulse |
| 5 | MCP-only path | Code/integration review | No direct Google API/OAuth/REST calls |
| 6 | Response validation | Inspect tool responses | Validated before marking success |
| 7 | Idempotent retry | Force a transient failure | Retry succeeds without duplicate spam |
| 8 | No PII in artifacts | Scan doc + draft | Zero PII present |

## Test data
- A validated `Pulse` object from Phase 3.

## Metrics
- **Delivery success** = (doc created AND draft created) per run. Target: 100% on valid input.
- **Duplicate rate** on retry. Target: 0 unintended duplicates.

## Exit criteria
- [ ] Google Doc created/updated via MCP with correct formatting and content.
- [ ] Gmail **draft** (not sent) created to self/alias containing/linking the pulse.
- [ ] Integration path is MCP-only; no bespoke Google API code.
- [ ] Tool responses validated; retries are idempotent.
- [ ] No PII in either artifact.

## Out of scope
- Full end-to-end chaining and scheduling (Phase 5).
