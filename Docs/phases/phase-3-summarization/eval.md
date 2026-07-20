# Phase 3 — Theme clustering & summarization · Evaluation

**Objective:** Produce a valid `Pulse` — ≤5 themes (top 3 shown), 3 anonymized verbatim quotes, 3 action ideas — within ≤250 words, using **in-memory** embedding clustering (no vector DB).

## What we test

| # | Test | Method | Pass condition |
|---|------|--------|----------------|
| 0 | In-memory clustering | Inspect pipeline | Embeddings clustered in memory; nothing persisted to a vector store |
| 1 | Theme cap | Run on sample dataset | ≤ 5 themes total |
| 2 | Top-3 selection | Inspect note | Exactly 3 themes highlighted |
| 3 | Quote count + fidelity | Compare quotes to source reviews | Exactly 3; verbatim; no invented wording |
| 4 | Quote anonymity | Scan quotes | No PII / reviewer identity |
| 5 | Action ideas | Inspect note | Exactly 3; concrete; grounded in themes |
| 6 | Length | Word count | ≤ 250 words |
| 7 | Structure | Validate `Pulse` object | Schema-valid; scannable |
| 8 | Determinism | Re-run with fixed input/seed | Stable themes/structure (allowing minor wording drift) |

## Test data
- The scrubbed sample dataset from Phase 2.
- A small labeled set where expected dominant themes are known.

## Metrics
- **Quote fidelity** = quotes matching source text exactly / 3. Target: 3/3.
- **Theme relevance** = human spot-check that top-3 themes match the data (qualitative rubric: 1–5, target ≥ 4).
- **Grounding** = each action idea traceable to a theme. Target: 3/3.

## Exit criteria
- [ ] Clustering runs in-memory; no vector DB / persistence introduced (per ADR-007).
- [ ] ≤ 5 themes; exactly top 3 surfaced in the note.
- [ ] Exactly 3 verbatim, anonymized quotes (no fabrication).
- [ ] Exactly 3 concrete action ideas grounded in themes.
- [ ] Note is ≤ 250 words and scannable.
- [ ] `Pulse` object is schema-valid and reproducible.

## Out of scope
- Writing to Google Docs / Gmail (Phase 4).
