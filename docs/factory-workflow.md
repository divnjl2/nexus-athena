# Athena in an existing project

This is the working entrypoint for the owner's project factory. The frontier agent researches the request, writes the contract and executable acceptance scenarios, and decomposes it into small plan tasks. The local harness implements those tasks through the homelab gateway. Athena's deterministic dispatch verdict and the project's gate decide whether a patch can be reviewed. A failed attempt is evidence for another attempt or escalation; its timeout is not a limit on the project task.

## Start a task

From any shell on this Windows host, set a path to this Athena checkout and the target Git repository:

```powershell
$athenaFrame = 'C:\Users\пк\Desktop\_athena_optimizer'
$project = 'C:\path\to\your-project'
python "$athenaFrame\factory.py" prepare $project telegram-auth 'Allow known Telegram IDs and deny unknown IDs'
python "$athenaFrame\factory.py" doctor $project telegram-auth
```

`prepare` creates only `features/telegram-auth/intent.md`. It refuses to overwrite an existing intent. The task is **awaiting specification** at this point: no generated example test is counted as proof.

The frontier agent then writes `features/telegram-auth/contract.md`, `scenarios.md`, and `plan.md` in the target project. It puts a real, initially failing acceptance command on each scenario and ties each small task to a scenario. It may use `python "$athenaFrame\athena.py" init features/telegram-auth --title ...` from the project root as a format example, but must replace its example version test before treating the feature as real work. The project's own `CORE.md`, `AGENTS.md`, security policy and acceptance criteria remain under the owner's control.

From the project root, pin and check the authored specifications, then commit them:

```powershell
python "$athenaFrame\athena.py" contract pin features/telegram-auth/scenarios.md --contract features/telegram-auth/contract.md --write
python "$athenaFrame\athena.py" check features/telegram-auth/contract.md --front features/telegram-auth/plan.md --run --text
git add features/telegram-auth
git commit -m 'Specify Telegram authorization'
```

At this stage a red acceptance scenario can be expected because the feature is not implemented. Record the failure as the baseline; never edit the scenario to make an executor's patch look green.

## Execute and judge

```powershell
python "$athenaFrame\factory.py" run $project telegram-auth T1.1 --executor pi-cluster-worker --iterations 3
```

`run` refuses uncommitted feature artifacts, creates a sibling Git worktree, and invokes Athena `dispatch` there. It leaves that worktree and the dispatch record for review. Repeating the same command resumes the registered worktree while the project's HEAD is unchanged. The project's current working tree is not modified. The `worker` role uses the cluster GPU pool; use `pi-cluster-agent` for tasks needing the longer context available on the `agent` role. `--executor claude` is the frontier implementation rung. An attempt that stays red should be decomposed, retried from its checkpoint, or escalated according to the evidence. The patch is offered for merge only after independent checks and review.

OpenHands is an available adapter in `athena dispatch`. `factory.py run --executor openhands` uses `openai/agent` and the same private gateway provider configuration as Pi, without putting a key on the command line. On this host the OpenHands SDK is currently absent; `factory.py doctor` reports this explicitly. The local Pi harness is installed and is the ready path today. The entrypoint adds the gateway host to `NO_PROXY` for the child process, because the inherited desktop proxy otherwise returned a connection error for the LAN address.

## Review and finish

In the returned worktree, inspect the diff and run the feature check and the project-wide gate:

```powershell
python "$athenaFrame\athena.py" check features/telegram-auth/contract.md --front features/telegram-auth/plan.md --run --text
python "$athenaFrame\athena.py" gate --text
```

The frontier reviewer checks the patch against the original intent, negative cases and changed-file radius. A green executor claim has no weight without these results. Only then merge or cherry-pick the worktree commit into the project branch. Store confirmed failures as lessons with provenance; do not rewrite the original requirement or the project's acceptance test during optimization.

The existing Athena daemon and Beads queue can run many such plan tasks once a project has its own Beads database. `factory.py` is the single-task entrypoint; it does not claim that unattended cross-project scheduling or optimizer promotion is already in service.

## First end-to-end check (2026-10-23)

A disposable Git project was given a committed contract, a red `add(2, 3) == 5` acceptance test, and a task limited to `calc.py`. `factory.py run` sent the packet to `pi-cluster-worker` through the live homelab gateway. Athena reported `PASS` on iteration 1 of 1, one changed file, and an independent green pytest command; the source project's `calc.py` remained unchanged while the worktree changed `a - b` to `a + b`. The synthetic task validates wiring and isolation, not success rates on the owner's real projects.
