# ADR-0001: Specs as data, run in-process

- Status: accepted
- Date: 2026-09-23
- Deciders: operator
- Cited by: features/team-layer C-1.*

## Context

Every executable spec was a pytest node bound to a clause by its docstring. The
Given/When/Then lines in scenarios.md were prose that nothing executed. That proves an
implementation rather than a behaviour: a refactor breaks specs whose behaviour did not
change, and a second language means rewriting every spec. The speed of the reference
approach (thousands of specs per second) comes from specs being data over a pure core,
not from a faster runner.

## Decision

A scenario may name a `case:` file instead of a `run_cmd`. A case is JSON with three parts:
`given` (named values), `when` (a call on a `module:callable` with `$name` references) and
`then` (a list of checks: equals, contains, truthy, startswith, length, raises, pending).
`athena spec run` executes cases in the current process. A case scenario still gets a
derived run command (`python -m athena case run <file>`) so the clause map, the mutation
sweep and the binding guard need no second mechanism. Command scenarios stay for anything a
case cannot express or for code in another language.

## Consequences

- New behaviour of pure modules is proved by a case first; a pytest node is the fallback.
- A case can only reach what is importable in-process; effects stay behind the seams.
- The case format is stdlib JSON, so a second toolchain can read and run it.
