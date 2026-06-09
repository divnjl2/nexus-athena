---
description: Athena preset — extend Spec-Kit tasks.md with a per-task success_check.
---

# Athena preset: tasks with `success_check`

This preset stacks on top of Spec-Kit's `speckit.tasks` command (Spec-Kit presets stack
by priority). It adds ONE mandatory rule so the deterministic compiler has an executable
gate per task — the PRIMARY `success_check` seam (§5).

## Added rule

For EVERY task line `- [ ] T0NN [P] [US?] <description with file path>`, emit an indented
sub-bullet on the next line:

```
  - success_check: `<executable command, exit 0 = passed>`
```

- The command must be runnable and exit 0 must mean the task is genuinely done
  (e.g. `pytest tests/test_x.py -q`, `curl -sf localhost:8000/health`, `test -f path`).
- No prose. If a task cannot be given an executable check, it is too vague — split it.
- Keep all other Spec-Kit `tasks.md` structure intact (phases, `[P]`, `[US]`, `**Checkpoint:**`).

If this preset is unavailable, `speckit_parser` falls back to the phase `**Checkpoint:**`
command as the gate (§5 fallback).
