# Athena — start here

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
