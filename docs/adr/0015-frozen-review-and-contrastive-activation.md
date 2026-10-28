# ADR-0015: Freeze before review and require contrastive activation

- Status: accepted
- Date: 2026-10-25
- Deciders: implementation within the operator-approved benchmark work
- Cited by: features/tdd-benchmark C-8.1/C-8.3 and features/spec-trust C-2.11

## Context
A candidate baseline alone cannot show that its oracle accepts valid alternatives and detects an independently activated violation.

## Decision
The trust arm freezes a passing native candidate before independent review, publishes no
evaluator prediction yet, and reserves one model call within its original total budget.
Review uses a fresh public-only context. Bind review to candidate and snapshot hashes;
retain all submitted specs for every live clause. Do not feed reviewer tests back into
the generator or repair the candidate after seeing hidden challenges.

Run the real spec-trust audit through the same bounded offline pytest bridge. Activation
tests and candidate tests receive separate containers and submitted files. Each execution
consumes the original arm's test budget. Missing/stale evidence or exhausted budgets
remain INCOMPLETE; only a passing audit releases the original frozen test patch.

An activation probe must distinguish the proposed clean baseline from its violation.
Require typed ASSERTION_FAIL on the baseline, then PASS on the violation. A baseline-PASS
probe is non-discriminating and fails the audit. Runtime/import/skip/timeout errors do not
prove inactivity and remain inconclusive. Generic nonzero command exits are insufficient;
use a pytest assertion probe or an injected typed execution boundary. This closes a real
gap where an always-true activation could be credited by the core audit.

## Consequences
Separate model contexts provide process separation, not independent semantic truth.
Reviewer validity remains a declaration. Track requested/served model, charged calls,
runtime identity and framework source hashes. The native evidence's environment describes
the host orchestrator; actual test execution uses the separately pinned container runtime.
Passing curated controls is not completeness or an inference benchmark score. Real model
comparisons still need frozen common budgets, all selected tasks and independent old/gold
evaluation. Human review costs must not be hidden inside an allegedly model-only result.
