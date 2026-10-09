# Self-improvement pilot: frozen corpus

## Owner cluster inference

The existing `gpt-6.1-sol` Codex baseline and its API-equivalent price card do
not measure the owner's local inference cluster. A cluster experiment needs a
separate provider lane and must keep its run records separate from the frozen
three-arm Codex matrix. Before using a selected cluster role, probe its real
Responses API stream and function-call continuation with a scoped client key:

```text
python -m evals.self_improve.cluster_probe --base-url http://192.168.1.136:30400/v1 --model agent --key-env ATHENA_CLUSTER_KEY
```

The key is read from an environment variable or `--key-file`; neither form puts
its value on the command line. The probe bypasses the workstation HTTP proxy
and sends synthetic text only. Its 2,048-token output budget allows reasoning
models to complete the short probes; `--max-output-tokens` can change it after
checking the selected lane's limits. It does not mark a task accepted or establish
which upstream lane served the request. A gateway administrator must verify
actual role routing separately. On 2026-10-09, direct gateway readiness was
HTTP 200, but the workstation's existing `LITELLM_KEY` received HTTP 401; no
cluster agent result has been recorded.
For vLLM reasoning lanes, `--reasoning-effort none` requests that setting on
all three synthetic exchanges; the result records it. Keep the actual candidate
driver's setting identical to the qualified setting.

The local Windows vLLM lane at `127.0.0.1:8001` passed that three-exchange
probe with `qwen3.5-9b`, 2,048 output tokens and reasoning effort `none`.
This is a local lane check, not a cluster gateway check. A separate Codex CLI
0.161.0 smoke against that lane failed with HTTP 400: Codex sent a `developer`
role that its Qwen chat template rejected. A local diagnostic adapter moved
that content into the request instructions, after which the lane rejected the
request against its 30,720-token context limit. Neither attempt generated a
benchmark candidate. The cluster's 64k `agent` role and its gateway still need
a scoped key and an end-to-end Codex tool-loop smoke before benchmark use.

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
be labeled separately from actual subscription billing. The committed
`price_card_gpt-6.1-sol_2026-10-09.json` uses the standard text-token rates
published on the [official GPT-6.1 Sol model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol):
$2 input, $0.10 cached input, $2.50 cache writes and $10 output per million
tokens. Every arm pins a 272,000-token context window and a 240,000-token
compaction threshold to stay within the model's standard-rate range. Codex's
JSONL trace aggregates usage by turn, not by individual model request, so these
figures remain an API-equivalent estimate rather than a billing statement.

`pilot.py plan --stage baseline` lists the 80 baseline cells. `pilot.py candidate`
runs exactly one Codex task-arm attempt after fetching and verifying the pinned
source row. It writes only a candidate patch and trace. The optimizer arm is a
separate stage; a holdout attempt requires a promotion file matching the frozen
instruction text and the hashes of complete baseline and development reports.

`baseline_batch.py` resumes the two-arm matrix one task at a time. It validates
all existing independent records before skipping them, gates a complete
ungraded candidate, and stops for review on partial candidate or gate data.
It never retries an executor error automatically. Pin `--athena-root` and
`--athena-commit` to one clean framework checkout for the whole batch; pass
`--max-pairs 1` for a bounded continuation. Its exit code is 2 while the
40-task baseline is incomplete, and its partial report is written under
`<root>/reports/partial-baseline.json`.

Local runner smoke on 2026-10-09: `codex exec --json` returned exit code 0 and
31,707 input tokens (28,160 cached), but produced a zero-byte patch. Its trace
reported that nested filesystem tool calls were blocked by the current host
policy. A separate scratch run with `danger-full-access` created the requested
file, but that mode grants too much host access for untrusted benchmark tasks.
Codex CLI 0.161.0 under WSL `workspace-write` reached HTTP 403 from the model
service. These are environment findings, not benchmark results. The Windows
failure came from `--ignore-user-config` dropping the configured native sandbox
implementation. The runner now pins `windows.sandbox=elevated` explicitly while
keeping `workspace-write`. A scratch Codex run produced a 155-byte patch, and a
direct sandbox check allowed writing inside that workspace but denied writing to
its sibling. See the [official Windows sandbox guide](https://learn.chatgpt.com/docs/windows/windows-sandbox)
for the supported setting. The runner now classifies failed turns, process exits
and tool-policy blocks without a patch as executor errors; such attempts cannot
be sent to the acceptance matrix. A completed run with a patch and one denied
tool call retains that warning and remains eligible for the independent gate. A run that
chooses to make no change remains a measurable empty patch. Task attempts retain
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

The official v5 harness skips execution for an empty patch and lists it in
`results.json`. Such a task-arm cell is unresolved only when its one-task summary
names that task as the sole submitted empty patch and reports no harness error.
The summary is preserved and hashed just like a per-instance report; infrastructure
errors remain unproved.

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

The first real `astropy__astropy-13579` Codex attempt under the pre-cap runner
passed the official harness. Its paired Athena attempt produced source and
contract changes, but also generated `.athena` caches and cumulative turn usage
above 272,000 tokens. These attempts are retained as protocol calibration, not
included in the baseline comparison. The next run uses the same frozen corpus,
model and acceptance tests, with one common context limit and a candidate patch
rule that excludes generated `.athena` caches for every arm. The original
calibration records remain in the local `pilot-v2` artifact directory.

To extend the benchmark to 50 or more tasks, publish a new manifest version with a
new selection seed before running candidates. Retain each older manifest
and all run records for comparison. Keep the same per-repository split rule where
possible; document any new repositories or changed eligibility rules. Never add
tasks to the frozen manifest after viewing optimizer results.
