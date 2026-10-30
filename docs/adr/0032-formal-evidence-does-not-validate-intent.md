# ADR-0032: Formal tool receipts preserve subject and intent boundaries

- Status: accepted
- Date: 2026-10-29

## Context
The user needs evidence of implementation and specification fidelity. A successful
formal check can still concern a weak property or an unreachable input domain.
Existing Python infrastructure should not require rewriting into a formal language.

## Decision
Introduce an optional `athena formal` collector with fixed CrossHair and Dafny
command shapes, pre/post input fingerprints and retained raw outputs. It runs
separately from the current assurance reducer and does not promote implementation
support, specification review, code correspondence or a release decision.

CrossHair no-counterexample results remain search observations. A zero exit code
without a recognized checked-condition diagnostic is UNKNOWN. Dafny nonempty,
successful verification summaries are VERIFIED_RELATIVE_TO_SPEC; failed proof
attempts are UNPROVEN, while prover/infrastructure errors remain UNKNOWN.

Every task declares its subject (model or implementation), scope, input closure
and assumptions. A proof of a separate Dafny model is not evidence of refinement
by a Python implementation. Formalization fidelity requires separate review,
including feasibility of preconditions and adequacy of postconditions.

Dafny subprocesses use invariant .NET numeric culture, recorded in each receipt.
The pilot on Russian Windows exposed a model-parser error under inherited locale;
the same defective program produced an ordinary proof failure under invariant
culture. This setting applies to the tool subprocess, not global system settings.

## Tradeoffs and alternatives
- A full Dafny rewrite would simplify proof composition but impose substantial
  migration and I/O-modeling costs; it still would not validate user intent.
- Tests/mutations preserve broad runtime compatibility but provide finite evidence.
- Optional analyzers allow gradual adoption but require typed, noninterchangeable
  evidence and explicit bridges between models and deployed code.
- Text output parsing is a deliberately bounded prototype. Unknown output fails
  closed; versioned structured result formats are preferred for production.
- Binary fingerprints cover only the selected executable, not the whole solver,
  library or OS closure. Declared inputs are not automatically complete.
- Local subprocesses are not a security sandbox. Production evaluation of hostile
  inputs needs process-tree limits and isolation before remote deployment.

## Validation
The authored seven-case pilot contains correct and defective Python/Dafny code,
missing Python contracts, a weak postcondition and an impossible precondition.
Successful verification of the latter two is an expected boundary demonstration,
not an independently measured assurance success rate.

## Consequences
Formal receipts remain opt-in and separate from requirement acceptance. Maintainers
must review formalization and model-to-implementation links before composing a
broader assurance claim. Infrastructure errors and changed inputs require a new
run; they never supply positive evidence.
`lib/formal_evidence.py` is an explicit effect seam in the architecture allowlist:
it owns the fixed tool invocations; the result-classification function stays pure.

## Sources
- https://crosshair.readthedocs.io/en/latest/contracts.html
- https://crosshair.readthedocs.io/en/latest/limitations.html
- https://dafny.org/latest/DafnyRef/DafnyRef
- https://arxiv.org/abs/2405.15800
