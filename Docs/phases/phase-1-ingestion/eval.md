# Phase 1 — Review ingestion & normalization · Evaluation

**Objective:** Convert public App Store + Play Store review exports into normalized `Review` records within the 8–12 week window.

## What we test

| # | Test | Method | Pass condition |
|---|------|--------|----------------|
| 1 | Parse both sources | Ingest sample App Store + Play Store exports | Both parse into the common schema |
| 2 | Schema conformance | Validate records against `Review` schema | 100% valid; required fields present |
| 3 | Date window filter | Apply 8–12 week window | Only in-window reviews remain |
| 4 | Dedup | Feed duplicate rows | Duplicates collapsed to one record |
| 5 | Stable IDs | Re-run ingestion on same input | `id`s identical across runs, identity-free |
| 6 | Robustness | Feed malformed/empty rows | Skipped gracefully with a logged count |

## Test data
- Small fixed sample export per source (committed as a fixture).
- Include edge cases: missing title, empty text, out-of-window dates, duplicate entries.

## Metrics
- **Parse rate** = parsed rows / total rows (target: ≥ 99% of well-formed rows).
- **In-window retention** = records kept after date filter (sanity-checked vs fixture).

## Exit criteria
- [ ] Both export sources normalize into the shared `Review` schema.
- [ ] Date-window filtering, dedup, and stable identity-free IDs all verified.
- [ ] Malformed rows are skipped without crashing, with counts logged.
- [ ] Output dataset is reproducible across runs.

## Out of scope
- PII scrubbing (Phase 2), theming, delivery.
