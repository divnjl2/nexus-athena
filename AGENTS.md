# Athena — start here (any agent: Claude Code, OpenHands, Codex, a local worker)

1. Read `CORE.md` first: goal, language, priorities, constraints. Under forty lines; it is
   the file every clause cites and every agent loads before anything else.
2. Work happens per feature under `features/<name>/`: `contract.md` (what is guaranteed,
   numbered clauses), `scenarios.md` (how each clause is proved, one runnable command each),
   `plan.md` (which task carries which spec). `features/contract-layer/README.md` explains
   the artifacts and who writes which; everything else there is derived, never hand-edited.
3. Done means PASS from the loop, on committed artifacts:

   ```bash
   python athena.py check features/<name>/contract.md --front features/<name>/plan.md \
       --ledger features/<name>/spec_ledger.json --text
   python athena.py gate --text        # every contract in the repo, the cheap lane
   ```

   The Stop hook in `.claude/settings.json` runs the gate; `CONTRACT_CRITERION_BYPASS=1`
   is the only bypass, on the operator's word.
4. New behaviour is a clause plus an executable spec, pinned with `python athena.py contract pin`.
   A requirement that changes is superseded, never edited. A clause born from a failure
   carries `source:`; `python athena.py lessons rerun` checks that the lesson still holds.
5. A decision that outlives the task is a record in `docs/adr/`, cited with `see:`. A failure
   from the world enters with `python athena.py intake` (draft clause + red spec). On a parallel
   branch take a lane: `ATHENA_LANE=N`, ids via `python athena.py contract next-id`.
6. Design history lives in `docs/history/`. Tasks are tracked in bd (`AGENTS.md`).

The same rules bind every executor: a task is done when `python athena.py check` on the touched
contract reports PASS and the diff is not empty; an executor's own 'done' is never evidence.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
