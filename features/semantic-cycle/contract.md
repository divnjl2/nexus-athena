# Contract: Semantic repair cycle

## C-1 — Source-grounded intent and assertion support
- **C-1.1** — WHEN a semantic cycle starts THE SYSTEM SHALL derive an issue-only intent passport before generation and validate every declared source quotation against the unchanged public issue while labelling semantic validity as declared rather than proven.
  - source: design
  - see: ../../docs/adr/0030-semantic-repair-cycle.md@1b2da1e2d307ea1b
- **C-1.2** — WHEN a candidate is reviewed THE SYSTEM SHALL account for every newly introduced assertion, bind its support to the frozen intent and issue, and distinguish supported declarations, unjustified assertions, unresolved support and missing coverage before release.
  - source: design

- **C-1.3** — WHEN an issue-only passport records open questions THE SYSTEM SHALL retain those questions during public generation and require separate, source-checked reviewer declarations for resolution or nonblocking scope before release while unresolved or missing answers remain INCOMPLETE.
  - source: incident
  - see: ../../docs/adr/0031-review-issue-questions.md@f8a5c66e188ed650

## C-2 — Immutable repair lineage
- **C-2.1** — WHEN audit feedback triggers repair THE SYSTEM SHALL retain previous attempts unchanged, bind each new candidate to fresh independent review, preserve changed requirements through supersession, and publish only the exact candidate satisfying the final gates.
  - source: design
- **C-2.2** — WHEN preparing repair feedback THE SYSTEM SHALL use only public generation, semantic review and native execution evidence while excluding independent evaluator results and sealed benchmark inputs from model contexts.
  - source: design

## C-3 — Challenge quality
- **C-3.1** — WHEN semantic review proposes valid controls THE SYSTEM SHALL record their declared mechanism or representation distinction and source justification, reject structurally unchanged controls as diversity evidence, and retain native activation and typed execution rules without attesting semantic equivalence.
  - source: design

## C-4 — Shared resource accounting
- **C-4.1** — WHEN a lineage admits model or test work THE SYSTEM SHALL durably charge one shared journal before execution, protect reserved phases, retain pending and failed charges across restart, and refuse changed bindings, limits or stale concurrent writers.
  - source: incident
  - see: ../../docs/adr/0030-semantic-repair-cycle.md@1b2da1e2d307ea1b
- **C-4.2** — WHEN planning audit and repair THE SYSTEM SHALL calculate complete bound-command costs and reserve later phases within the unchanged total budget, reporting insufficiency without dropping obligations or automatically increasing limits.
  - source: incident
- **C-4.3** — WHEN reporting lineage resources THE SYSTEM SHALL preserve observed usage separately from missing usage, retain denied admissions and bounded error types without exception secrets, and distinguish charged attempts from server spending or successful execution.
  - source: incident

## C-5 — Independent assessment
- **C-5.1** — WHEN preparing the new assessment THE SYSTEM SHALL freeze disjoint evaluation and calibration IDs, model settings, budgets and executable bindings before study inference, retain all selected cases and exclude previous study IDs from new quality evidence.
  - source: design
- **C-5.2** — WHEN reporting assessment THE SYSTEM SHALL independently grade frozen intermediate and final candidates after generation ends and report native versus independent outcomes, withheld-good cases, repair changes and cumulative resources without converting uncertainty into success or excluding missing cases.
  - source: design
