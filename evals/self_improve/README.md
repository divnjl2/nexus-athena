# Self-improvement pilot: frozen corpus

## Owner cluster inference

The existing `gpt-6.1-sol` Codex baseline and its API-equivalent price card do
not measure the owner's local inference cluster. A cluster experiment needs a
separate provider lane and must keep its run records separate from the frozen
three-arm Codex matrix. Before using a selected cluster role, probe its real
Responses API stream and function-call continuation with a scoped client key:

```text
python -m evals.self_improve.cluster_probe --base-url http://192.168.1.136:30400/v1 --model agent --key-file <private-key-file> --max-output-tokens 8192
```

The key is read from an environment variable or `--key-file`; neither form puts
its value on the command line. The probe bypasses the workstation HTTP proxy
and sends synthetic text only. The `agent` route needed an 8,192-token output
budget in the live check; a 2,048-token request once completed without visible
text. The probe does not mark a task accepted. On 2026-10-09, a separately
issued virtual key restricted to `agent` passed SSE completion, function call
and replayed function result. The response reported `qwopus3.5-9b-v3`; a
separate direct request exposed the gateway route `agent@ai-server-quadro`.
The workstation's old `LITELLM_KEY` still received HTTP 401.
For vLLM reasoning lanes, `--reasoning-effort none` requests that setting on
all three synthetic exchanges; the result records it. Keep the actual candidate
driver's setting identical to the qualified setting.

For a Codex route whose Qwen template rejects the `developer` role, a small
loopback bridge adapts only leading developer text into Responses `instructions`:

```text
python -m evals.self_improve.cluster_bridge --upstream http://192.168.1.136:30400/v1 --upstream-key-env ATHENA_CLUSTER_KEY --client-key-env ATHENA_BRIDGE_CLIENT_KEY --port 8777
```

Supply both secrets through the named environment variables, and point the
Codex custom provider at `http://127.0.0.1:8777/v1` with the bridge client key.
The bridge binds only to loopback, forwards streamed `/v1/responses`, rejects
late or non-text developer content, and never prints keys or response bodies.
Its role adaptation changes request shape but does not change task acceptance.
Official Codex custom provider settings use `model_provider`,
`model_providers.<id>.base_url` and `env_key`; see the
[Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
Codex CLI 0.161.0 completed a live two-command tool loop through the bridge,
with a 65,536-token context setting and `workspace-write` sandbox. This was a
synthetic transport smoke, not a benchmark candidate or acceptance result.

The deployed bridge is managed by GitOps in `homelab-infra/apps/athena-bridge`
at revision `90f9d7e5994994fe4d18582cc73903cf7c2ccd66`. It runs one Pod,
mounts the Python source from a ConfigMap, reads the two keys from a SOPS
Secret, and has no Service. From the Windows workstation, access it through
an SSH tunnel and a pod port-forward:

```text
ssh -o IdentityAgent=none -L 127.0.0.1:8777:127.0.0.1:8777 ai-server 'kubectl -n athena-eval port-forward deploy/athena-cluster-bridge 8777:8777'
```

Point Codex at `http://127.0.0.1:8777/v1` with the bridge client key from a
private file outside Git. The Pod has a read-only filesystem, no service
account token, and egress only to DNS and the gateway. The optional
`cluster_bridge_pod.py` renders a standalone manifest for local inspection;
the live cluster uses the GitOps resources. A Codex CLI smoke through the Pod
also completed two command executions and read back the expected file token.
After its source update, the full streamed text/function/replay probe also
passed through the Pod's forwarded endpoint.

`cluster_pilot.py` records real cluster candidates under a **different root and
schema** from the priced Codex baseline. It requires a route probe from the
last 24 hours, keeps the bridge key outside artifacts, and sets `cost_usd` to
`null` until owner-cluster cost is measured. Run one development candidate and
then submit its saved patch to the same pinned SWE-bench harness:

```text
python -m evals.self_improve.cluster_pilot candidate --task psf__requests-5414 --arm codex --root <cluster-run-root> --client-key-file <private-bridge-key> --probe-report <passed-pod-probe.json>
python -m evals.self_improve.cluster_pilot gate --task psf__requests-5414 --arm codex --root <cluster-run-root> --wsl-distro Ubuntu --harness-python <linux-swebench-python>
```

A candidate patch and completed Codex turn are still unverified until `gate`
preserves the official report. This separate lane is not a cell in the frozen
three-arm `gpt-6.1-sol` comparison, and it cannot make a USD cost claim yet.
The runner writes Codex JSONL and stderr to disk during execution, so a timeout
or interrupted parent leaves the partial trace for diagnosis. An incomplete
candidate is never submitted to the gate automatically.
`cluster_report.py --root <cluster-run-root> --split development` revalidates
every official record before summarizing it. Missing cells and interrupted
attempts remain visible; either one keeps the report incomplete and prevents a
paired comparison. Its USD cost fields stay `null` until cluster cost is
measured. It lists model identifiers reported by the synthetic preflight probe;
these do not establish the model or GPU lane of every benchmark request. This
exploratory report does not enter the priced three-arm pilot.
`cluster_batch.py` runs at most one development task pair per invocation by
default. It fixes the Athena commit, model role, bridge URL and context window
across existing records, grades a complete preserved candidate, and stops for
review when an attempt or gate is partial. A fresh passing probe and private
client key are required before a new candidate. Its output report is
`<cluster-run-root>/reports/development.json`; an incomplete run exits 2.
For Codex 0.161.0, `--model-catalog
evals/self_improve/agent_catalog_codex_0.161.0.json` gives the local `agent`
role explicit context, tool and reasoning metadata. The runner snapshots the
catalog for each attempt, checks its hash on resume and independent grading,
and leaves the full catalog override scoped to that Codex process. A local
loopback bridge can be used with the same private client key and a fresh probe;
`--bridge-url` must match that probe. `--docker-image <immutable-sha256-id>`
selects the same pinned Linux SWE-bench harness backend as the cloud baseline.
The old WSL gate remains available with `--wsl-distro` and `--harness-python`.
The catalog format is version-sensitive; the
[Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
documents `model_catalog_json` as a full catalog override.

On 2026-10-21, a direct `agent` route probe and a local bridge probe passed
SSE completion, function call and replay. The response reported
`qwopus3.5-9b-v3`; that preflight observation does not establish the lane of
every future request. A bounded Codex coding smoke with the explicit catalog
completed two shell commands without the missing-metadata warning, but failed
an exact-byte acceptance check: PowerShell `echo >` wrote UTF-16LE with CRLF
instead of the requested UTF-8 with LF. This is a coding-quality observation,
not a completed SWE-bench task. The SSH/pod-forward path truncated some SSE
streams during diagnosis; the direct local bridge passed its full probe.

The first real Codex candidate through that local bridge, for development task
`psf__requests-5414` on 2026-10-21, timed out at the fixed 900-second limit.
Its preserved trace contains 53 completed shell commands but no completed
Codex turn and no patch. The agent repeatedly requested lines beyond the end
of an 817-line file, including requests starting at line 2500. The runner
recorded `executor_error` with exit code 124; the official acceptance harness
was not invoked, and this attempt contributes no verified result. The probe
and shell loop establish transport for that run, while the observed failure
concerns the agent's task execution. This single task does not establish an
overall cluster model success rate. Any revised prompt or route needs a new
attempt with its own provenance and independent gate.
The paired `codex_athena` candidate reached the same 900-second limit with
62 completed shell commands, 27 of them failing, no completed Codex turn and
no patch. It reproduced the URL error but spent many commands on malformed
PowerShell/Python one-liners. Both candidates are `executor_error`; neither
entered the official gate. This paired failure does not support a quality
comparison between the two prompts.

The local Windows vLLM lane at `127.0.0.1:8001` passed that three-exchange
probe with `qwen3.5-9b`, 2,048 output tokens and reasoning effort `none`.
This is a local lane check, not a cluster gateway check. A separate Codex CLI
0.161.0 smoke against that lane failed with HTTP 400: Codex sent a `developer`
role that its Qwen chat template rejected. A local diagnostic adapter moved
that content into the request instructions, after which the lane rejected the
request against its 30,720-token context limit. Neither attempt generated a
benchmark candidate. The cluster route has since passed those transport checks,
but has not yet produced a graded task in a separate cluster evaluation lane.
On 2026-10-11, the ignored local `.athena/cluster-pilot-v3` root contains two
independently graded development pairs (four attempts). Neither arm solved
either task: the plain Codex arm saved two empty patches; the Athena arm saved
one nonempty unresolved patch and one empty patch. The report still has 56
missing development cells, no paired comparison, and no measured cluster USD
cost. The second Athena candidate consumed 7,260,632 input tokens and 1,258
seconds end to end without a patch. These are exploratory observations, not a
completed benchmark or evidence that the framework improves coding quality.

Cluster candidate provenance fingerprints the raw trace and stderr files; even
a line-ending change invalidates the candidate before official grading.
Cluster graded-attempt time includes the independent gate. If an ungraded
attempt remains, total time is unknown and only graded time is a lower bound.

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
It lists candidates that never reached an independent gate and charges their
cost and tokens when their saved evidence validates. If usage cannot be proven,
the total is unknown and a verified lower bound is shown; these attempts keep
the comparison incomplete. It reports Wilson intervals for success rates.
Verified-success time includes the candidate and the official SWE-bench gate;
an unfinished gate leaves total time unknown and reports a measured lower bound.
A string naming the official
gate does not authenticate a report by itself; the eventual runner must capture
the independent harness output and preserve its execution logs.
Complete reports also show a fixed-seed paired bootstrap interval, wins and
regressions on the same tasks, and counts of failure reasons. They reject a
smaller replacement corpus.
Every reported failure needs a nonempty reason; an official success cannot be
counted in the failure reasons.

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
Report hashes and self-declared completion alone are insufficient evidence, so
the holdout gate reloads every attempt and official harness artifact, recomputes
the complete baseline and optimizer development reports, and checks every
development prompt against the selected instruction bytes and Athena commit.
The promotion file must also name that commit and the two exact report files
under the run root's `reports/` directory. Generate report bodies with
`python -m evals.self_improve.evidence --stage baseline` and
`--stage development --optimizer-instructions <frozen-text-file>` using the
same `records/` and `artifacts/` paths; save their exact stdout bytes and
SHA-256 in the promotion file. A partial or altered report keeps holdout closed.

`baseline_batch.py` resumes the two-arm matrix one task at a time. It validates
all existing independent records before skipping them, gates a complete
ungraded candidate, and stops for review on partial candidate or gate data.
It also checks for extra ungraded attempts beside already graded cells before
skipping a pair. It never retries an executor error automatically. Pin `--athena-root` and
`--athena-commit` to one clean framework checkout for the whole batch; pass
`--max-pairs 1` for a bounded continuation. Its exit code is 2 while the
40-task baseline is incomplete, and its partial report is written under
`<root>/reports/partial-baseline.json`.

On Windows, use the pinned Linux SWE-bench harness image with Docker Desktop:

```text
docker build -f evals/self_improve/Dockerfile.swebench -t athena-swebench:5.0.2 evals/self_improve
docker image inspect athena-swebench:5.0.2 --format '{{.Id}}'
python -m evals.self_improve.baseline_batch --root <fresh-run-root> --athena-root <clean-framework-checkout> --athena-commit <commit> --model gpt-6.1-sol --price-card evals/self_improve/price_card_gpt-6.1-sol_2026-10-09.json --docker-image <sha256-image-id> --max-pairs 1
```

The runner accepts only an immutable image ID for this backend, mounts the
private harness work directory and Docker socket, and runs the unchanged
SWE-bench 5.0.2 package inside Linux. Its image includes a pinned Docker CLI:
the official package calls that binary to stop and remove evaluation
containers. A missing CLI or nonzero harness exit leaves the gate unproved.
Record the image ID for every batch.
The gate reads v5 reports from `logs/run_evaluation/`. A direct Windows run
of the same package rewrote an LF candidate patch as CRLF before applying it
inside Linux; the local `.athena/pilot-v4` run on 2026-10-21 is diagnostic and
must not be included in the baseline matrix. Its first gate also exposed the
old adapter's incorrect `logs/evaluation/` lookup. The failed gate marker is
retained, so that attempt must not be silently retried.
The next `pilot-v5` diagnostic used a Docker image with the correct report
path, but that image lacked the Docker CLI required by the official cleanup
routine. Its first two development pairs were independently graded, with
both arms resolving both tasks; the Codex arm cost $0.1228876 and the Athena
arm $0.3043696 in API-equivalent estimates. Those four reports are preserved
as calibration, not combined with the next fixed-image baseline. The four
leftover evaluation containers (five across the two diagnostic roots) were
removed by exact name after their reports were validated, and the two task
images were removed. The Docker Desktop VHD
on D: has limited host free space; check and clean only completed benchmark
objects after each bounded batch.

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
the image and evaluation script. It also binds the exact harness command,
prediction, stdout and stderr files to the gate envelope so later report
validation detects changes to those artifacts. Stdout and stderr are saved as
the harness runs, so a timeout leaves partial diagnostics without a verdict.
An attempt-bound start marker also prevents a timed-out gate from being treated
as a candidate that has never entered acceptance testing.
Its per-instance reports are under `logs/run_evaluation/`. It uses a one-task
local JSON snapshot so the harness cannot silently fetch changed acceptance
data. On this Windows host, pass `--docker-image <sha256-image-id>` to
`pilot.py gate`. A provisioned WSL harness remains an alternative via
`--wsl-distro Ubuntu --harness-python /path/to/venv/bin/python`.

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

The 2026-10-10 prompt-byte audit reclassified local `pilot-v3` as protocol
calibration. Its four official harness reports resolved two Astropy task pairs,
with API-equivalent cost estimates of $0.1466868 for Codex and $0.37549 for
Codex + Athena. However, Windows saved each `prompt.txt` with CRLF while the
recorded SHA-256 was computed from LF text. Normalizing CRLF to LF reproduces
each hash, but the saved bytes do not match the recorded fingerprint. The
stricter validator now rejects all four records, so **none count toward the
40-task baseline**. Their original files remain under ignored `.athena/pilot-v3`
for audit; do not rewrite them to make the check pass. The runner now saves and
sends identical UTF-8 bytes. Under the current sandbox, WSL and Docker access
are denied, preventing a fresh official gate run. The runner writes stdout and
stderr directly to artifact files while Codex runs. A timeout retains partial
diagnostics and classifies the candidate as an executor error.
The attempt loader now also checks the saved issue input, candidate diff,
invocation, exact trace and stderr bytes, completed-turn usage, price calculation and exact one-task harness
dataset against each record. An official verdict cannot compensate for a
changed or missing leg of that evidence.

To extend the benchmark to 50 or more tasks, publish a new manifest version with a
new selection seed before running candidates. Retain each older manifest
and all run records for comparison. Keep the same per-repository split rule where
possible; document any new repositories or changed eligibility rules. Never add
tasks to the frozen manifest after viewing optimizer results.
