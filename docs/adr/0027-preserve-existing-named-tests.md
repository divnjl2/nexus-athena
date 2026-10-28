# ADR-0027: Preserve pre-existing named test definitions

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
Status: accepted after Seaborn-3187 diagnostic attempt 6.

## Context
The model replaced an existing 684-line test file with its own overlay. Native
forward checks passed the proposed reference. Trust audit withheld publication
for declared gaps. Independent scoring of the unchanged rejected candidate failed
on an implementation-specific formatter-offset assertion. These are distinct defects.

## Decision
Before test execution or patch export, compare Python AST definitions of existing
functions and methods whose names start with test, keyed by class/function scope.
Preserve their ordered definitions, including bodies, signatures and decorators.
Reject deletion, modification and added definitions shadowing an old name. Allow
additive tests and edits outside protected definitions. Reject altered files whose
syntax the host parser cannot compare; unchanged files need not be reparsed.

## Consequences
Apply this policy to native exports, direct canonical patch exports and offline
overlays. This structural guard does not establish semantic equivalence: changes
to imports, helpers, fixtures, class configuration or dynamic collection can still
affect behavior. Independent checks remain necessary. Historical artifacts and
their benchmark outcomes remain unchanged.
