# Decision Log

A running record of important **technical** and **business** decisions for the Weekly Review Pulse agent. Each entry is an ADR (Architecture Decision Record): context, decision, alternatives, consequences.

> Newest decisions on top. Status: `Accepted` · `Proposed` · `Superseded` · `Deprecated`.
>
> **Index:** [ADR-010](#adr-010--explicit-stage-contracts-review--themedcorpus--pulse) · [ADR-009](#adr-009--identity-free-content-hash-ids) · [ADR-008](#adr-008--discover-themes-by-clustering-not-a-fixed-taxonomy-or-llm-freeform) · [ADR-007](#adr-007--batch-summarization-not-rag-no-vector-db) · [ADR-006](#adr-006--phase-gated-delivery-with-per-phase-eval-exit-criteria) · [ADR-005](#adr-005--email-is-created-as-a-draft-not-sent) · [ADR-004](#adr-004--verbatim-anonymized-quotes-only-no-fabrication) · [ADR-003](#adr-003--deterministic-data-layer-llm-confined-to-language-work) · [ADR-002](#adr-002--pii-scrubbing-as-a-hard-gate-before-the-llm) · [ADR-001](#adr-001--mcp-first-integrations-for-google-docs--gmail)

---

## ADR-010 — Explicit stage contracts (`Review` → `ThemedCorpus` → `Pulse`)
- **Date:** 2026-06-03
- **Status:** Accepted
- **Type:** Technical / Logical

**Context.** The pipeline has five stages built and tested in isolation (phase-gated, [ADR-006](#adr-006--phase-gated-delivery-with-per-phase-eval-exit-criteria)). They need a clean way to hand work off without coupling to each other's internals.

**Decision.** Define **explicit, validated data objects as the contract between stages**: normalized `Review[]` → clean `Review[]` → `ThemedCorpus` → `Pulse` → delivered artifacts. Every stage validates its input against the contract and fails fast on violation.

**Alternatives considered.**
- *Pass loose dicts / free-form text between stages:* quick but untestable and fragile; rejected.
- *One monolithic function:* impossible to evaluate per phase; rejected.

**Consequences.**
- (+) Each phase is independently testable against a known shape (enables the per-phase evals).
- (+) Failures surface at the exact boundary where they occur — no silent partial success.
- (−) Slightly more upfront schema design.

---

## ADR-009 — Identity-free content-hash IDs
- **Date:** 2026-06-03
- **Status:** Accepted
- **Type:** Technical / Privacy

**Context.** We need stable IDs to dedupe reviews across runs/sources, but reviewer identity must never enter the system (privacy is a hard requirement).

**Decision.** Derive each review's `id` from a **hash of its content** (source + normalized text + date), and **drop reviewer names/handles/account identifiers at parse time** — before PII scrubbing even runs.

**Alternatives considered.**
- *Use the store's reviewer/author ID:* stable but introduces identity into our data; rejected on privacy grounds.
- *Random UUID per run:* breaks cross-run dedup; rejected.

**Consequences.**
- (+) Reliable dedup and quote-to-source traceability without storing identity.
- (+) Defense in depth — identity is gone before the PII gate.
- (−) Identical text on the same date collapses to one record (acceptable; it's effectively a duplicate).

---

## ADR-008 — Discover themes by clustering, not a fixed taxonomy or LLM free-form
- **Date:** 2026-06-03
- **Status:** Accepted
- **Type:** Technical / Logical

**Context.** We must group reviews into ≤ 5 themes. Options: (a) a hard-coded category list, (b) ask the LLM to invent themes free-form over all reviews, or (c) embed reviews and cluster them.

**Decision.** **Embed reviews and cluster the embeddings** to let themes emerge from the data, cap at ≤ 5, and rank by volume × severity. The LLM only *labels* the resulting clusters (it does not decide the grouping).

**Alternatives considered.**
- *Fixed taxonomy (onboarding/KYC/payments/…):* brittle; misses emerging issues; rejected as the primary mechanism (still useful as example labels).
- *LLM free-form theming over the whole corpus:* non-deterministic, hard to evaluate, and risks missing/merging themes inconsistently; rejected.

**Consequences.**
- (+) Themes reflect what's actually in the reviews this week; reproducible grouping.
- (+) Keeps the non-deterministic LLM out of the grouping decision (pairs with [ADR-003](#adr-003--deterministic-data-layer-llm-confined-to-language-work)).
- (−) Cluster quality depends on embedding/clustering parameters; needs spot-checks.

---

## ADR-007 — Batch summarization, not RAG (no vector DB)
- **Date:** 2026-06-03
- **Status:** Accepted
- **Type:** Technical

**Context.** A natural instinct is to build a RAG stack (chunk → embed → vector DB → retrieve → LLM). But the weekly pulse is a **once-a-week summarization over a bounded corpus** (8–12 weeks of public reviews), where we process *all* in-window reviews each run. There is no interactive Q&A in the spec — there is no "question" to retrieve against.

**Decision.** Use a **batch summarization pipeline**. Embeddings are used **in-memory to cluster reviews into themes** only; they are discarded after the run. **No persistent vector database and no retrieval/Q&A layer.**

**Alternatives considered.**
- *Full RAG (vector DB + retrieval):* heavier ops, earns its keep only for large/unbounded corpora or interactive Q&A. Rejected as overkill for a bounded weekly batch.
- *Hybrid (batch now, persist embeddings for a future chatbot):* sensible if Q&A is on the roadmap; deferred — can revisit without reworking the batch core.

**Consequences.**
- (+) Simpler: no vector store to provision, index, or keep fresh.
- (+) Reproducible and easy to evaluate (Phase 3 eval).
- (+) Embedding-based clustering still gives quality theme grouping.
- (−) No out-of-the-box interactive querying; adding Q&A later means introducing a store/retrieval layer (revisit this ADR if so).

---

## ADR-001 — MCP-first integrations for Google Docs & Gmail
- **Date:** 2026-06-03
- **Status:** Accepted
- **Type:** Technical / Business (course requirement)

**Context.** We must write the weekly pulse to Google Docs and create a Gmail draft. Options were direct Google REST APIs (custom OAuth + HTTP clients) or MCP servers/connectors.

**Decision.** Use **MCP servers** for both Google Docs and Gmail. The agent discovers tools, reads their schemas, and invokes them. No bespoke OAuth/REST code as the primary integration path.

**Alternatives considered.**
- *Direct Google APIs:* full control, but duplicates auth + HTTP plumbing and diverges from course tooling.
- *Hybrid:* MCP for Docs, REST for Gmail — inconsistent; rejected.

**Consequences.**
- (+) Less auth/HTTP code; consistent, auditable tool calls.
- (+) Aligns with the project requirement (MCP-first).
- (−) Dependent on available MCP server capabilities/limits.
- (−) Need MCP connectivity verified early (Phase 0).

---

## ADR-002 — PII scrubbing as a hard gate before the LLM
- **Date:** 2026-06-03
- **Status:** Accepted
- **Type:** Technical / Privacy

**Context.** Artifacts must contain no PII. LLMs and stored docs/drafts could leak reviewer identity if raw text flows through.

**Decision.** Make PII scrubbing a **mandatory stage before any LLM call or artifact write**. Ambiguous tokens fail safe to redaction. Recall (catching PII) is prioritized over false positives.

**Alternatives considered.**
- *Scrub only final output:* risks PII reaching the LLM/logs; rejected.
- *Rely on LLM to avoid PII:* not guaranteed; rejected as the sole control.

**Consequences.**
- (+) Strong privacy guarantee at a single boundary.
- (−) Some clean text may be over-redacted (acceptable trade-off).

---

## ADR-003 — Deterministic data layer; LLM confined to language work
- **Date:** 2026-06-03
- **Status:** Accepted (refined by [ADR-008](#adr-008--discover-themes-by-clustering-not-a-fixed-taxonomy-or-llm-freeform))
- **Type:** Technical

**Context.** We need reproducible runs but also high-quality thematic summaries. The question is which stages should be deterministic and which should use the (non-deterministic) LLM.

**Decision.** Keep **ingestion, normalization, dedup, date-filtering, PII scrubbing, and theme clustering deterministic**. Confine the **LLM to language work only**: labeling themes, selecting verbatim quotes, and drafting action ideas. (Clustering itself is embedding-based and deterministic — see [ADR-008](#adr-008--discover-themes-by-clustering-not-a-fixed-taxonomy-or-llm-freeform).)

**Consequences.**
- (+) Reproducible, testable data layer; LLM scope is small and auditable.
- (+) Easier evaluation (deterministic stages have exact pass/fail).
- (−) Theme labels and quotes still need spot-checks for quality.

---

## ADR-004 — Verbatim, anonymized quotes only (no fabrication)
- **Date:** 2026-06-03
- **Status:** Accepted
- **Type:** Business / Trust

**Context.** Stakeholders rely on quotes as real user voice.

**Decision.** Quotes must be **verbatim** snippets from actual reviews, **anonymized**, with **no invented wording**. Exactly 3 in the note.

**Consequences.**
- (+) Trustworthy, auditable artifact.
- (−) Constrains the LLM; requires fidelity checks (Phase 3 eval).

---

## ADR-005 — Email is created as a draft, not sent
- **Date:** 2026-06-03
- **Status:** Accepted
- **Type:** Business / Safety

**Context.** The flow ends with an email to self/alias. Auto-sending risks accidental or repeated sends.

**Decision.** Create a **Gmail draft** (to self/alias) rather than sending automatically. A human reviews and sends.

**Consequences.**
- (+) Safe against accidental sends and retry duplication.
- (−) Requires a manual send step (acceptable for a weekly pulse).

---

## ADR-006 — Phase-gated delivery with per-phase eval exit criteria
- **Date:** 2026-06-03
- **Status:** Accepted
- **Type:** Process

**Context.** The build spans ingestion → privacy → summarization → delivery → orchestration.

**Decision.** Ship in **phases**, each with an `eval.md` defining tests and **exit criteria**. A phase must pass its eval before the next begins.

**Consequences.**
- (+) Clear progress tracking and quality gates.
- (−) Slightly more upfront documentation overhead.

---

## Template for new decisions

```
## ADR-NNN — <short title>
- **Date:** YYYY-MM-DD
- **Status:** Proposed | Accepted | Superseded | Deprecated
- **Type:** Technical | Business | Privacy | Process

**Context.** <what problem / forces are at play>

**Decision.** <what we decided>

**Alternatives considered.** <options + why rejected>

**Consequences.** <trade-offs, + and ->
```
