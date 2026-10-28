# ADR-0013: Execute candidate tests in environment-only runtimes

- Status: accepted
- Date: 2026-10-25
- Deciders: implementation within the operator-approved benchmark work
- Supersedes: ADR-0011's controller-image-only restriction for candidate pytest tools
- Cited by: features/tdd-benchmark C-6.1 and C-6.3

## Context
Public base-code tests need project dependencies without inheriting task-image history or evaluator inputs.

## Decision
An inspected upstream environment-only image may supply the project's Python and test
dependencies. Task images remain forbidden: they contain a cloned repository and history.
Require an empty /testbed and no task setup script, pin the immutable image identity and
bind the runtime receipt to a public snapshot. An image name alone is insufficient.

The model can submit test files and pytest nodes, not host argv or shell commands. Send
payload through stdin, keeping the output mount empty at launch. Copy public base code
into fresh temporary storage, overlay only test files and run fixed pytest arguments in
an offline, non-root, bounded container. Keep evaluator files and API credentials out.

Record a separate test-run budget and runtime identity in generation receipts. Every tool
invocation receives its own container name; timeout cleanup targets only that container.
Model-visible feedback excludes host commands and contains only execution diagnostics.

## Consequences
Use the shared typed JUnit classifier: assertion failure differs from import, collection,
skip, missing report and timeout. This local tool output is diagnostic, not a trusted
oracle verdict. Model-authored tests can manipulate in-process behavior; an independent
evaluator and the trust challenge set remain necessary. A successful scripted protocol
control is not model performance or a paired Athena benchmark result.
