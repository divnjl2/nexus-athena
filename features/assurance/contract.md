# Contract: Requirement assurance

> Assessment describes evidence for a requirement; it does not authorize release or prove universal correctness.

## C-1 — Evidence boundaries
- **C-1.1** — WHEN an assessment is generated THE SYSTEM SHALL include every live contract clause in its denominator.
- **C-1.2** — WHEN evidence input bytes differ from their declared fingerprints THE SYSTEM SHALL exclude that evidence from current support.
- **C-1.3** — WHEN a passing execution lacks valid-alternative and activated-violation controls THE SYSTEM SHALL leave implementation assurance unknown.
- **C-1.4** — WHEN current observations both support and contradict a dimension THE SYSTEM SHALL report conflict for that dimension.
- **C-1.5** — WHEN no current code correspondence review exists THE SYSTEM SHALL report code correspondence as unknown.
- **C-1.6** — WHEN an assessment is rendered THE SYSTEM SHALL describe its counts as evidence coverage rather than probability of correctness.

