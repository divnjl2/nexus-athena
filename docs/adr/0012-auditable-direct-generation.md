# ADR-0012: Keep direct generation distinct from Athena evaluation

- Status: accepted
- Date: 2026-10-25
- Deciders: implementation within the operator-approved benchmark work
- Cited by: features/tdd-benchmark C-5.1 and C-5.3

## Context
Direct generation must remain distinguishable from native Athena and trust evaluation. A transport smoke test cannot establish model quality.

## Decision
The initial direct-agent generator exposes only public-source list/read tools and a
finish action, through explicit chat-completions configuration. No model-generated code
executes on the host. It rechecks the public snapshot at every turn, enforces fixed call
and context limits, records returned usage and every tool result, and has no hidden retries.

Generation produces a candidate and a receipt, never a semantic PASS. Invalid, truncated,
interrupted or failed generation remains INCOMPLETE. Provider exception text is not logged
because it can contain credentials. Provider-supplied usage is retained as reported;
missing usage remains unknown. Secrets are sourced from a named environment variable.

The generator's current list/read/finish interface is not yet a complete coding agent:
it cannot run tests locally. Its offline code-tool sandbox remains a separate boundary.
Before comparing modes, all arms need the same code tools and total budget. Athena arms
must execute real framework/trust logic; prompt labels do not implement an ablation.

## Consequences
Scripted HTTP controls prove transport and evaluation plumbing, not inference quality.
They carry an explicit scripted-control source kind. A successful negative control means
the evaluator rejects an always-green test. It does not establish the advantage of Athena
or complete the thirty-task paired evaluation.
