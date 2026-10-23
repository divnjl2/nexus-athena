# Contract: project factory entrypoint

## C-1 — From a real project request to verified execution

- **C-1.1** — WHEN a new project task is prepared THE SYSTEM SHALL record its intent without creating a passing specification or replacing an existing intent.
  - source: design
- **C-1.2** — WHEN a committed task is dispatched THE SYSTEM SHALL execute it in a separate Git worktree and leave the original project tree untouched.
  - source: design
- **C-1.3** — WHEN a cluster executor is selected THE SYSTEM SHALL address the gateway's `agent` or `worker` role through the Pi harness instead of pinning execution to one GPU lane.
  - source: design
- **C-1.4** — WHEN factory readiness is inspected THE SYSTEM SHALL report missing proof artifacts and harness availability without exposing credentials.
  - source: design
- **C-1.5** — WHEN a cluster harness starts THE SYSTEM SHALL bypass the desktop HTTP proxy for the configured gateway host.
  - source: incident
- **C-1.6** — WHEN a task is retried after an interrupted attempt THE SYSTEM SHALL resume only its registered worktree at the same committed project base.
  - source: review
