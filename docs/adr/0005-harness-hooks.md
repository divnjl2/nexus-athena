# ADR-0005: The harness hands the agent its context and enforces the core's constraints

- Status: accepted
- Date: 2026-09-23
- Deciders: operator
- Cited by: features/team-layer C-5.*

## Context

`athena contract owners <file:line>` answered "which clauses may I break by editing this",
but nothing told the agent at the moment it mattered. Two constraints of CORE.md ("a
derived artifact is never edited by hand", "pure modules spawn nothing") were held by
convention and by docstrings.

## Decision

A PreToolUse hook on Edit, Write and MultiEdit execs `athena hook pre-edit`, which reads the
tool payload and answers with additional context: the clauses of every contract whose map
owns lines in the target file. The same hook refuses an edit of a derived artifact
(`spec_ledger.json`, `clause_map.json`, `clauses.needs.json`) and names the command that
rebuilds it; `CONTRACT_CRITERION_BYPASS=1` allows it and says so. `athena lint arch` reports
any module outside an explicit effect allowlist that imports a process or network module,
and the repository must pass its own lint.

## Consequences

- The agent sees the blast radius before the edit, not in the review.
- A derived file cannot be hand-patched into agreement with a claim.
- The allowlist is a list in code, reviewed like code; adding a module to it is a decision.
