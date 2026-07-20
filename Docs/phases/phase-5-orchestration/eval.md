# Phase 5 — Orchestration & end-to-end agent · Evaluation

**Objective:** A single weekly run chains ingest → scrub → summarize → deliver with validation and a run summary.

## What we test

| # | Test | Method | Pass condition |
|---|------|--------|----------------|
| 1 | End-to-end run | One command on sample export | Produces Doc URL + Gmail draft id |
| 2 | Stage validation | Inspect inter-stage checks | Each stage validated before the next |
| 3 | PII gate honored | Trace pipeline | Scrubbing runs before summarization every time |
| 4 | Run summary | Inspect output | Reports review counts, themes, doc link, draft id |
| 5 | Idempotent retries | Inject transient failure | Recovers without duplicate artifacts |
| 6 | Failure handling | Break one MCP call | Fails clearly; no partial silent success |
| 7 | Reproducibility | Re-run same input | Comparable pulse + clean summary |
| 8 | Weekly runnability | Follow run docs | A new user can run it from instructions |

## Test data
- Full sample export covering the 8–12 week window.

## Metrics
- **End-to-end success rate** on valid input. Target: 100%.
- **Mean stages passed** before failure (for failure-mode runs). Higher is better; failures are explicit.

## Exit criteria
- [ ] One command runs the full pipeline and yields a Doc URL + draft id.
- [ ] All constraints hold end-to-end (≤5 themes/top 3, 3 quotes, 3 actions, ≤250 words, no PII).
- [ ] Inter-stage validation and idempotent retries verified.
- [ ] Failures are explicit (no silent partial success).
- [ ] Run summary is emitted and the weekly run is documented.

## Out of scope
- Future enhancements (multi-product, dashboards, auto-send) tracked separately.
