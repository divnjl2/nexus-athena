# Perimeter layer (v3.18): the adapter between the frame and the world outside it

Four of the nine limits named on 2026-09-27 were wiring: the oracles, the stand-ins, the scanners and
the eval runners exist as open source, none speaks the frame's language of clause, verdict and stage.
A fifth group followed the same evening after the box showed what it lacks: a scheduler. The layer is
25 clauses in five groups, each with a red spec before the code, implemented by the OmniCoder-9B lane
through the daemon inside the OS sandbox, reviewed by the frontier, finished by the frontier after
three lane iterations where the lane's window did not reach (ADR-0007).

| group | what | OSS wrapped | module |
|---|---|---|---|
| C-1 findings become verdicts | Vale, Bandit, gitleaks and Semgrep JSON in one shape; a threshold from the clause; a missing tool is unrun; the frame's own documents under a prose style; a judge advisory until calibrated | Vale (MIT), Bandit, gitleaks, Semgrep | `lib/findings.py`, `vale/` |
| C-2 the external world as fixtures | cassettes are spec artefacts with a freshness; PostgreSQL from the embedded binary inside the sandbox's port range; a red verdict becomes a reproduction packet admitted by the AssertFlip rule | embedded-postgres (Apache-2.0), VCR.py, the AssertFlip recipe | `lib/stands.py`, `athena repro` |
| C-3 scan and policy in the queue | scanners planned from the changed files; Rego policies over the merge record under conftest; a model's review advisory | Bandit, gitleaks, pip-audit, conftest (OPA) | `lib/scan.py`, `policy/merge.rego` |
| C-4 the rungs watched | a series row per executor per bench; a one-sided CUSUM dates a drop; a bead once per drop; a set change told apart from a rung change | ruptures as the reference, a CUSUM by hand | `lib/drift.py`, `athena drift`, `bench --series` |
| C-5 the substrate | host floors before a dispatch or a heavy gate; a lane woken through the router; strangers on a GPU against an allow-list; heavy gates under the process governor | procgov (MIT), pynvml | `lib/host.py`, `gpus.json` |

Research behind it: `docs/research/2026-09-27-nine-limits-oss-first.md` (what open source closes) and
`docs/research/2026-09-27-inference-on-this-box.md` (43 incidents by class, why Windows makes each
worse, the plan by leverage).

## The host, prepared by hand (27.09)

- `C:\ProgramData\athena\bin`: Vale 3.23, conftest 0.70, gitleaks, osv-scanner, procgov 4.1, WinSW 2.12;
  pi machine-wide under `C:\ProgramData\athena\npm`. Readable to the sandbox account.
- Our two lanes (`omni_3090.bat`, `nb3b_3060.bat`) run under procgov: a commit ceiling per process
  tree (32 GB, 8 GB), recursive. llama-swap still owns the launch and the port; the operator's 9B lane
  and llama-swap's config are untouched. **Correction 28.09 00:40:** the 27.09 edit had left only the
  comment line in both launchers; no procgov process existed on the box all evening, and the claim above
  was written from the intent, not from `Get-Process procgov`. Found by the zombie probe. Two more facts
  on the way to the real thing: procgov re-quotes its command line and breaks an inline
  `bash -lc "... \"...\" ..."` (bash: `unexpected end of file`, llama-swap: `upstream command exited
  prematurely`), so the launchers now pass one file, `omni_entry.sh` / `nb3b_entry.sh`; and procgov's
  recursive wait does not end a job whose leader died, so `serve_omni_3090.sh` is now the lane's own
  supervisor: the API server runs in bash's foreground and, when it exits, bash sweeps vLLM engine
  processes whose parent is gone (the 9B lane's engine, whose parent lives, is never matched) and exits,
  which ends procgov, closes the job and lets llama-swap relaunch on the next request.
- The OmniCoder launcher claims its KV pool in bytes (9.255 GB, what vLLM logged at a clean start,
  455,680 tokens) and derives the fraction from the memory free at launch minus the driver's reserve,
  capped at 0.70: a neighbour on the card lowers the claim instead of making the start impossible.
- pip: embedded-postgres (PostgreSQL 18), pip-audit, semgrep, inspect-ai, vcrpy, schemathesis, moto,
  nvitop, pynvml. Side effect: the installs broke the global Python's aiohttp and with it every pytest
  run on the host; repaired by a clean reinstall. A venv for the frame is the standing fix, not done.

## Measured so far (running log, updated as the queue drains)

### The lane's landings and the review

| task | verdict | iteration | review |
|---|---|---|---|
| T1.1 findings from four tools | green, then red on review, green again | 2, then 1 | the first landing keyed the Vale reader on the sample's file name; S1.1 gained a second file, the rework iterates every file |
| T1.2 threshold verdict, missing tool | green | 2 | worst finding wins whatever its position |
| T1.3 the prose style | red x3, finished by the frontier | 3 + finish | the 9B does not know Vale's config grammar; and the first "green" was a config Vale rejected with an empty output that read as clean: S1.4 gained a control document that must trip all three rules |
| T1.4 judge record | green | 1 | |
| T2.1 cassettes, stale ones | green | 1 | |
| T4.1 series rows, set digest | green, then red on review | 1 | the digest was bytes, unserialisable into the JSON row; and the series verdict's drop was a bare `True` where the wiring needs the CUSUM's record: S4.1 and S4.4 tightened |
| T4.2 the CUSUM | green, red on review, green on rework, finished by the frontier | 1 + 1 + finish | the sealed second reading caught the first: it fired on one bad night and on a recovered dip; the rework passed every case with a fixed drop of 0.4 from the reference and a run count, and missed a fall from 0.8 to 0.4 by the width of a comparison (S4.4's series). The frontier wrote the one-sided CUSUM: deficit against a reference with slack k, decision interval h, start where the accumulation last left zero. Three tries taught the same lesson: a spec is a grader, and a 9B optimises the grader |
| T4.3 `athena drift`, `bench --series` | red x3, finished by the frontier | 3 + finish | the lane's window overflowed on athena.py every time; the frontier wired it |
| T2.2 the embedded postgres stand | red x3, finished by the frontier | 3 + finish | the lane's stand used the package's wrapper, which picks a random port outside the sandbox's range, and left a `NameError`; worse, its attempts inside the sandbox started clusters it never stopped: twenty orphaned `postgres.exe` under the sandbox account, killable only with elevation. The finish drives the binaries from an ASCII copy under ProgramData (initdb dies on the cp1251 profile path), on a port in 60084-60089, and keeps postgres as its own child in a kill-on-close job object |
| T5.1 host state and floors | green | 2 | |
| T5.2 wake through the router | green | 1 | |
| T5.3 the inventory and its strangers | red x3, finished by the frontier | 3 + finish | the lane read the inventory at the wrong level and matched patterns as path suffixes where the inventory promises substrings, so every process was a stranger |
| T5.4 the governor around a heavy gate | green | 1 | |
| T2.3 the reproduction packet and the AssertFlip admission | green | 1 | |
| T2.4 `athena repro` | red x3, finished by the frontier | 3 + finish | athena.py again: the window overflowed (30,465 of 30,720 tokens) and the landing keyed on the spec's sample name (`if "test_demo.py::test_a" in tail`); the frontier wired the command, and found on the way that both health probes of T5.5 unpacked a string (never exercised while the lane was up) |

Pattern of the evening: the visible spec alone is a grader a 9B learns to satisfy; the sealed second
reading and the reviewer's strengthened cases are what turned three spec-fitting landings into real
ones. Every strengthening was a change to the spec, never to the lane's code by hand.

### Frame defects the run surfaced, each now a spec

- A lane fresh from a restart reports zero prefix queries; the lane-state reader divided by zero and
  took the daemon down while it parked.
- The daemon read the bead's id from the ready list after the claim, where the task no longer was:
  green tasks stayed in progress, red ones never reopened, and a green task was re-dispatched forever.
- The daemon reopened a bead the frontier had closed as finished while the lane's red attempt ran.
- The daemon read "closed" as a substring of the bead's JSON, where a closed dependency also says so:
  T3.1 was left in progress on a red verdict because T1.2 was closed under its dependencies.
- An attempt whose worker died before any check ran (the 9B's window overflowed on the packet) has no
  check row; the lesson writer indexed it and took the daemon down, and T3.1's first record was lost.
- The GPU inventory found a real stranger among the desktop noise: the intender card evaluation
  (`eval/card/run_per_field.py`) shares the 3090 with the lane; its bead stays open. The desktop shell
  set was found on the 3090 too (Windows composes on both cards when a monitor hangs on each) and is
  now allowed there; a Python process on the lane's card remains a stranger.

### The substrate switched on, first tick (27.09 23:36)

The daemon ran from the work tree with `--host-floors ram=6G,vram=1G --wake --gpu-allowlist gpus.json`.
Two design faults showed in the first minute, both mine: the floors were checked on every GPU, and the
display card next to the lane's is always full, so the lane's tasks parked forever with the right
reason and the wrong scope; and the inventory read the display card too, where every desktop app
holds a graphics context, so it opened 25 beads for Task Manager, Docker Desktop and a VPN client.
Fixed as: the VRAM floor applies to the lane's GPU (`--lane-gpu`), a GPU marked `watch: false` in the
inventory is not read. The floor's message itself was exact: `vram on RTX 3060 floor 1.0G, available
0.3G`.

A third fault the next tick after T2.4 (28.09 00:05): `vram on RTX 3090 floor 1.0G, available 0.9G` parked
T3.1 on the lane's own card. The lane holds that card by design (vLLM claims its KV pool at start), so
free VRAM there is near zero whenever the lane is up. Fixed as: the VRAM floor guards the wake (the lane
must fit before it is started), the RAM floor guards every dispatch; when the lane answers health, its
card is spoken for and the floor is not applied.

### The proof by class (`tools/chaos_probe.py`, `.athena/chaos.jsonl`)

| probe | what used to happen | now |
|---|---|---|
| `seed` past int32 | the V2 runner crashed | 200 in 0.4 s |
| `hog`, 8 GB under a 4 GB procgov ceiling beside the lane | the lane died of the host's malloc (20:02 the same day) | the hog dies with MemoryError in 0.6 s, the lane answers health and generation |
| `zombie`, the lane's API process killed hard | a child held 8 GB of VRAM for five hours | first run 00:23: **failed, and taught the most** — the EngineCore (a `multiprocessing.spawn` child, whose command line never says `vllm.entrypoints`) lived on with 21.7 GB of commit and the 3090; the relaunch died of `ERROR_COMMITMENT_LIMIT` (1455) with 4.9 GB of commit free on a 141.8 GB limit (the operator's vault build, card evaluation, WSL and the 3B lane held the rest); and there was no procgov to close the job (see the correction above). Rerun after the supervisor: see below |
| `neighbour`, 6 GB held on the card during a restart | the restart was refused (fixed fraction) | pending |
| `load429`, concurrency above the router's limit | the lane crashed on KV overflow (June) | 24 concurrent: 12 x 200, 12 x 429, health 200 after (28.09 00:23) |

### Tokens

Filled when the layer merges: the lane's input and output through the 9B per task, and the frontier's
share (clauses, specs, reviews, two finishes).
