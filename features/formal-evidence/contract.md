# Contract: Optional formal evidence

## C-1 — Tool results have bounded meaning
- **C-1.1** — WHEN CrossHair finds no counterexample THE SYSTEM SHALL report NO_COUNTEREXAMPLE without promoting requirement implementation assurance.
  - source: review
  - see: ../../docs/adr/0032-formal-evidence-does-not-validate-intent.md@29f066e628201221
- **C-1.2** — WHEN Dafny returns a nonempty successful verification summary THE SYSTEM SHALL report VERIFIED_RELATIVE_TO_SPEC with its declared subject and assumptions.
  - source: review
- **C-1.3** — WHEN a formal tool times out or returns an unrecognized result THE SYSTEM SHALL report UNKNOWN.
  - source: review
- **C-1.4** — WHEN a formal input changes during execution THE SYSTEM SHALL exclude its tool result as UNKNOWN.
  - source: review
- **C-1.5** — WHEN formal receipts are displayed THE SYSTEM SHALL distinguish the verified subject from the requirement's user intent.
  - source: review
- **C-1.6** — WHEN the CrossHair self-check seeds defects THE SYSTEM SHALL preserve the live production source and retain an exact unmodified baseline snapshot.
  - source: review
- **C-1.7** — WHEN the self-check displays an exhaustive replay table THE SYSTEM SHALL identify that replay separately from CrossHair observations.
  - source: review
- **C-1.8** — WHEN tool observations are exported as GSN THE SYSTEM SHALL leave global intent fidelity and project coverage claims open.
  - source: review
  - see: ../../docs/adr/0033-gsn2x-renders-arguments-not-verdicts.md@90a63148011e26dc
