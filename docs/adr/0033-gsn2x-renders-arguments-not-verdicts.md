# ADR-0033: Native gsn2x renders bounded arguments, not verdicts

- Status: accepted
- Date: 2026-10-29

## Context
The user explicitly selected jonasthewolf/gsn2x for argument visualization. A
custom result dashboard alone did not satisfy that intent. A graph can also
mislead if a successful tool run appears to establish global correctness.

## Decision
Export archived formal receipts into GSN goal, strategy, context, assumption and
solution nodes, and execute an explicitly installed native gsn2x binary. YAML is
emitted in its JSON-compatible representation and validated by native gsn2x.
Retain source receipt bytes, derived per-case evidence views, renderer command,
binary hash and raw renderer output. Provide a local HTML wrapper with zoom and
links into the native SVG and evidence files.

The global goal remains explicitly unconfirmed. Fidelity of formal properties to
user intent and project-wide coverage remain undeveloped goals. Result nodes
state only what the archived tool reported; NO_COUNTEREXAMPLE is not rewritten
as proven correctness. A renderer-success exit code validates diagram structure,
not truth, freshness, completeness or independence of the argument.

## Tradeoffs
- Reuse native GSN validation/layout rather than implement a diagram renderer.
- Preserve required YAML source and SVG output alongside the preferred HTML view.
- A bounded archived case is useful before full live evidence invalidation exists;
  the diagram labels that boundary explicitly.
- Wide graphs require zoom/navigation; decomposition into modules is a later option.
- The native executable is optional and is not vendored or implicitly installed.

## Source
https://github.com/jonasthewolf/gsn2x

## Consequences
The graph preserves unresolved claims rather than turning successful rendering
into successful assurance. Exporters must retain the source receipt and require
fresh SVG output; stale diagrams cannot stand in for a new renderer invocation.
The HTML view is a navigation layer over native GSN artifacts.
`lib/gsn_case.py` is an explicit effect seam in the architecture allowlist for the
native renderer subprocess; argument construction remains a pure function.
