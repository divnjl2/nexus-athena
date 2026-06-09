# Ralph Executor Contract (AGENTS.md)

You are an executor invoked on exactly ONE Beads issue. Obey this contract.

## On start
- Run `bd prime` to load the graph context.
- Read your issue: `bd show <id>` — title + body carry the task, its `success_check`, and `files`.

## While working
- Work ONLY on the claimed issue. Never touch another agent's claim.
- Use `bd ready` / `bd show` to understand dependencies; never pick a new issue yourself —
  the loop hands you exactly one.
- Anything out of scope you discover -> `bd create ... --label discovered-from:<id>` (a new
  issue). Do NOT silently expand scope into the current issue.

## Before exit
- Ensure the issue's `success_check` passes. The external `gate.sh` is authoritative — your
  self-report does not count.
- Run `bd sync` to persist the Dolt state before the session is killed.

## Never
- Never mark an issue closed yourself — the loop closes it only if `gate.sh` passes.
- Never edit files outside the workdir.
- Never trust your own "looks done" — only the gate's exit code matters.
