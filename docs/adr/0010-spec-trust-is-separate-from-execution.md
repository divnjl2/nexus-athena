# ADR-0010: Spec trust is separate from execution

- Status: accepted
- Date: 2026-10-24
- Deciders: operator (agreed research plan); implementation details by Codex
- Cited by: features/spec-trust C-1.3, C-2.2

## Context
The operator approved the research-based trust plan. Existing green execution ledgers and
AST mutation cannot alone establish oracle validity or semantic adequacy. The empty mutation
denominator returned a perfect score, and integer process results conflated errors with kills.

## Decision
Keep the existing fast execution lane. Add an explicit `trust` audit for curated clauses.
It runs declared valid alternatives and semantic violations in fresh trusted filesystem
copies. Violation activation is independent of the spec command and is never a kill itself.
No observations means INCOMPLETE. Scores retain denominators and inconclusive outcomes.

The manifest records the origin of the oracle, input domain, assumptions, review decision,
and known gaps. These are declarations to review, not facts certified by an LLM. A successful
audit is scoped evidence about its challenge set, not a probability of correctness.

The trusted inputs, manifest and challenge fixtures are fingerprinted. Implementation overlays
cannot replace tests, configuration or the manifest. File-integrity checks detect writes to
protected files. This is filesystem separation, NOT an OS security sandbox: arbitrary hostile
Python can interfere with its process. Use a separately administered sandbox for hostile code.
The implementation never launches models or performs Git operations.
`lib/verification.py` is an explicit effect seam allowed to spawn local verification commands;
the architecture linter lists it alongside spec_runner. The audit policy stays separate.

## Evidence motivating the decision
- https://arxiv.org/html/2608.17177v2 (contracts improve bug detection in a bounded study)
- https://arxiv.org/html/2610.13065v1 (valid generated tests can remain weak)
- https://arxiv.org/html/2607.22880v1 (mutation metrics depend on generation context)
- https://arxiv.org/abs/2608.19626 (single-reference oracle artifacts)
- https://rdi.berkeley.edu/blog/vero/ (fresh trusted scaffold for verification)

## Compatibility
Retain integer runners as a legacy test-injection seam. Production mutation paths use typed
outcomes with pytest JUnit evidence. Only assertion failures are credited automatically;
generic command failures require an explicit adapter and otherwise remain inconclusive.
An explicitly unchanged deep sweep is NOT_REQUIRED; an attempted empty sweep is INCOMPLETE.
Existing feature contracts are not rewritten. New obligations live in features/spec-trust.

## Consequences
Verification becomes costlier only when explicitly requested. Existing baselines remain
visible, and inconclusive runs cannot establish trust. A reviewer must maintain the input
domain and labels; an independent evaluation on unseen real faults remains future work.
