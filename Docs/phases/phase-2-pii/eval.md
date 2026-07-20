# Phase 2 — PII scrubbing · Evaluation

**Objective:** Guarantee no PII reaches the LLM or any artifact. This is the privacy boundary.

## What we test

| # | Test | Method | Pass condition |
|---|------|--------|----------------|
| 1 | Email removal | Reviews with emails | All emails masked/removed |
| 2 | Phone removal | Reviews with phone numbers (intl + local) | All masked/removed |
| 3 | Handle/username removal | `@handle`, "my username is …" | Removed/masked |
| 4 | ID removal | Account/order/device IDs | Removed/masked |
| 5 | Ambiguous cases | Borderline tokens | Redacted (fail-safe), logged |
| 6 | Hard gate | Attempt LLM call with unscrubbed text | Blocked; scrubbing enforced first |
| 7 | Content integrity | Clean reviews | Non-PII content preserved, readable |

## Test data
- Curated PII fixture set with known planted PII and a labeled ground truth.
- Negative cases: text that looks like IDs but isn't (e.g., "v8.2.1").

## Metrics
- **PII recall** = caught PII / total planted PII. **Target: 100%** (no leaks).
- **False-positive rate** = clean tokens wrongly redacted. Track and keep low, but recall wins ties.

## Exit criteria
- [ ] 100% of planted PII removed/masked in the fixture set (zero leaks).
- [ ] Ambiguous tokens fail safe to redaction.
- [ ] Scrubbing is enforced as a hard gate before any LLM call or artifact write.
- [ ] Redaction counts are logged per run.
- [ ] Non-PII review content remains intact and usable for theming.

## Out of scope
- Theming/summarization quality (Phase 3).
