# Contract: Spec trust

> A passing command is execution evidence. Adequacy and oracle validity need their own
> challenges; none of these observations establishes completeness of the requirement.

## C-1 — Honest mutation evidence
- **C-1.1** — WHEN no mutant has a decided outcome THE SYSTEM SHALL report a null mutation score.
  - source: incident
- **C-1.2** — WHEN a mutation check has no execution evidence THE SYSTEM SHALL report INCOMPLETE unless the sweep was explicitly not required.
  - source: review
- **C-1.3** — WHEN a mutation command fails to execute its assertions THE SYSTEM SHALL retain the failure as inconclusive evidence.
  - see: ../../docs/adr/0010-spec-trust-is-separate-from-execution.md@308f155838372d20
  - source: review
- **C-1.4** — WHEN a mutation is tested against a failing baseline THE SYSTEM SHALL refuse to credit its failure as a kill.
  - source: review
- **C-1.5** — WHEN per-clause mutation results contain inconclusive outcomes THE SYSTEM SHALL exclude those outcomes from the score denominator.
  - source: review
- **C-1.6** — WHEN a shared-line mutant is killed THE SYSTEM SHALL credit per-clause detection only to the clauses bound to the killing spec.
  - source: review
- **C-1.7** — WHEN the mutant budget truncates an attempted sweep THE SYSTEM SHALL report its overall evidence as incomplete.
  - source: review

## C-2 — Challenge the oracle
- **C-2.1** — WHEN a trust manifest is loaded THE SYSTEM SHALL validate its clause fingerprints against the current contract.
  - source: design
- **C-2.2** — WHEN a trust audit runs THE SYSTEM SHALL evaluate both declared valid alternatives and activated requirement violations.
  - see: ../../docs/adr/0010-spec-trust-is-separate-from-execution.md@308f155838372d20
  - source: design
- **C-2.3** — WHEN a declared valid alternative is rejected or an activated violation is accepted THE SYSTEM SHALL fail the trust audit.
  - source: design
- **C-2.4** — WHEN a challenge cannot be activated or evaluated THE SYSTEM SHALL report that challenge as inconclusive.
  - source: design
- **C-2.5** — WHEN a trust audit prepares a challenge THE SYSTEM SHALL apply only manifest-authorized implementation files to a fresh copy of the trusted inputs.
  - source: design
- **C-2.6** — WHEN a challenge changes a protected verifier input THE SYSTEM SHALL reject its evidence.
  - source: design
- **C-2.7** — WHEN a trust audit emits evidence THE SYSTEM SHALL fingerprint its manifest, trusted inputs, challenge data and execution environment.
  - source: design
- **C-2.8** — WHEN a trust audit has missing controls or declared knowledge gaps THE SYSTEM SHALL report INCOMPLETE.
  - source: design
- **C-2.9** — WHEN trust evidence is integrated into check THE SYSTEM SHALL refuse missing, stale or unsuccessful evidence explicitly requested by the operator.
  - source: design
- **C-2.10** — WHEN a spec command names generic Python THE SYSTEM SHALL execute it with the verifier's current interpreter.
  - source: incident
- **C-2.11** — WHEN a violation activation probe is evaluated THE SYSTEM SHALL require an assertion failure on the clean baseline before crediting its successful activation on the violation, rejecting non-discriminating probes and retaining execution errors as inconclusive.
  - see: ../../docs/adr/0015-frozen-review-and-contrastive-activation.md@f0bfe50bc66f6f6e
  - source: audit
- **C-2.12** — WHEN verification environment evidence is prepared THE SYSTEM SHALL remove volatile tool-call trace metadata from both execution and fingerprinting while retaining changes to actual runtime settings.
  - source: incident
