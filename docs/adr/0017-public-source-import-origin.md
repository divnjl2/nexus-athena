# ADR-0017: Public source import origin

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

## Context
Environment-only images can contain another installed version of the target project.
A successful test against that copy is not evidence about the selected public base.
Observed on the Pytest source layout: root-only PYTHONPATH resolved site-packages,
while adding src resolved the selected source module.

## Decision
The offline runner orders existing src, lib and root directories on PYTHONPATH.
Before pytest it resolves the repository's declared top-level module in a separate
process and requires a physical origin inside the copied public source. Missing or
external origins are infrastructure errors, even if a successful JUnit file exists.
This is an origin guard, not proof that imports or compiled extensions will work.

The model receives the inspected runtime Python version, and the reviewer receives
the same version from the frozen generation receipt. No evaluator metadata enters
that context. The transported bootstrap supports the observed Python 3.6 runtime;
an actual Python 3.6 syntax/helper control is retained separately from project tests.

## Consequences
Environment-image availability, project-import readiness and benchmark success
remain distinct. In particular, missing pytest or missing compiled project artifacts
must not be converted into assertion witnesses.
