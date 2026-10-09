# Self-improvement pilot: frozen corpus

`manifest.json` freezes 40 real SWE-bench Verified issues from revision
`78f471bf655a3137b2e8a75af1501690ec009ec3`: four per eligible repository,
with three development tasks and one holdout task per repository. Selection is
deterministic across the ten repositories with at least four Verified tasks.
Each entry pins the issue input, repository base commit and acceptance material by
SHA-256. Verify it with `python -m evals.self_improve.corpus verify`.

The manifest contains no task text or test patch. A runner must fetch the pinned
dataset revision, verify the fingerprints, and pass only `problem_statement` and
`hints_text` to the agent. The holdout is **procedurally isolated**: it is a public
dataset, so secrecy against an agent with unrestricted network access is not proven.
Optimizer candidate generation and selection must use development tasks only; a
finalist gets one holdout evaluation after its configuration is fixed.

This corpus is an input, not a result. The repository currently has no 40-task,
three-arm execution report. Published plan-quality evals and the `athena bench`
executor matrix measure different questions and cannot serve as that report.

`evidence.py` validates one JSONL record per attempt against the frozen corpus and
the bytes of its gate artifact. `--stage baseline` requires 80 task-arm cells
(Codex and Codex plus Athena); `--stage final` requires all 120, including the
optimizer. A report exits with code 2 while a required cell is absent.
It charges every failed attempt to the total cost of the
arm and reports Wilson intervals for success rates. A string naming the official
gate does not authenticate a report by itself; the eventual runner must capture
the independent harness output and preserve its execution logs.
Complete reports also show a fixed-seed paired bootstrap interval, wins and
regressions on the same tasks, and counts of failure reasons. They reject a
smaller replacement corpus.

`workspaces.py` plans baseline attempts before optimizer attempts and creates fresh
Git worktrees at the exact issue base commits. `codex_driver.py` records the
Codex JSONL trace, prompt, invocation and candidate diff; the candidate is still
unverified. Its price card computes an API-equivalent token estimate, which must
be labeled separately from actual subscription billing.

`pilot.py plan --stage baseline` lists the 80 baseline cells. `pilot.py candidate`
runs exactly one Codex task-arm attempt after fetching and verifying the pinned
source row. It writes only a candidate patch and trace. The optimizer arm is a
separate stage; a holdout attempt requires a promotion file matching the frozen
instruction text and the hashes of complete baseline and development reports.

Local runner smoke on 2026-10-09: `codex exec --json` returned exit code 0 and
31,707 input tokens (28,160 cached), but produced a zero-byte patch. Its trace
reported that nested filesystem tool calls were blocked by the current host
policy. This is an environment finding, not a benchmark result. Candidate records
now label empty patches separately from accepted fixes, and task attempts retain
the issue input, timestamps, source revision, and Athena commit when used.

`pilot.py gate` writes a one-task snapshot from the pinned dataset and feeds the
candidate patch to the official SWE-bench harness outside the agent worktree.
Each harness run id includes the task, arm, attempt and patch hash to prevent
reuse of a cached verdict for another patch. The resulting record points to an
unchanged official `report.json` and its SHA-256. An absent report leaves the
task unproved. The adapter pins `swebench==5.0.2`, whose Verified rows include
the image and evaluation script. Its per-instance reports are under
`logs/evaluation/`. It uses a one-task local JSON snapshot so
the harness cannot silently fetch changed acceptance data. On Windows, pass
`--wsl-distro Ubuntu --harness-python /path/to/venv/bin/python` to `pilot.py gate`;
the Ubuntu WSL Docker daemon is available on the development host.

Infrastructure calibration on 2026-10-09 used official gold patches, never agent
outputs. Version 5.0.2 refused the Lite row `psf__requests-1963`
(`KeyError: image`). Version 4.1.0 reached its test container, but
`pytest -rA test_requests.py` remained active for over 18 minutes without a
verdict; the calibration container was stopped. A SWE-bench Verified v5 smoke
for `pytest-dev__pytest-5809` also stalled in `test_pastebin.py` and was
stopped. A separate Verified v5 smoke for `pytest-dev__pytest-7324` completed
in 174 seconds and the official report counted it as resolved. These are
harness checks, not benchmark results. The earlier 36-task Lite manifest and
its selection code remain in `manifest_lite_v1.json` and `corpus_lite_v1.py`.
No agent result from it was accepted. The Verified v2 manifest was frozen before
any agent comparison; successor clauses C-1.4, C-1.5 and C-2.7 record the change.

To extend the benchmark to 50 or more tasks, publish a new manifest version with a
new selection seed before running candidates. Retain each older manifest
and all run records for comparison. Keep the same per-repository split rule where
possible; document any new repositories or changed eligibility rules. Never add
tasks to the frozen manifest after viewing optimizer results.
