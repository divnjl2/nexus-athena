# TDD-Bench-Verified integration

Every generation mode validates the complete final unified patch against its verified
public base. Only bounded same-path Python test changes are exported; implementation,
configuration, linked paths, mode changes, malformed or stale hunks and trailing payloads
are rejected. The transcript retains the original reply and the prediction hashes the
canonical test diff. This structural check is not a semantic oracle.

Environment images and installed project runtimes are distinct. The runtime command
also accepts explicitly named `athena.public-runtime:<tag>` derivatives built by a
trusted operator from public base source and installed dependencies. It checks immutable
image identity, snapshot labels, known source bytes/links and absence of Git history and
task setup scripts, then writes a separate schema-2 receipt. Raw task images remain
forbidden. See ADR-0019 for the provisioning boundary. The initial live installation
control covers Sphinx. Compiled/generated outputs can be restored into the fresh copy
from a separately fingerprinted inventory (ADR-0020), with byte, path and symlink checks.
A real C-extension control verifies this mechanism; scientific-project installation
controls remain pending. Image admission alone does not certify a project.

Runtime inspection and offline containers explicitly use `LANG=C.UTF-8` and
`LC_ALL=C.UTF-8`. New runtime receipts require a UTF-8 filesystem encoding. This matters
for Python 3.6, where the default C locale cannot process some public Django filenames;
see ADR-0021. Preserve earlier failed preparations and reissue controls under the changed
framework fingerprints.

For public-installed images, stage the declared source inside the Linux image and recheck
each file hash/link target before overlays. The fresh copy avoids Windows bind-mount
per-file copying overhead. Undeclared files are excluded from source staging; installation
outputs remain governed by the separate artifact inventory (ADR-0022).

GitHub archives can expand `.git_archival.txt` through a tracked `export-subst`
attribute while a checkout retains placeholders. Trusted provisioning validates that
metadata relationship and restores the canonical frozen archive bytes; it does not
relax admission hashes or protected implementation checks (ADR-0024).

This is an external test-generation benchmark, not the SWE-bench Lite planning proxy.
Five gold-test tasks calibrate the harness; thirty disjoint tasks are frozen for a later
paired model evaluation. Calibration is never reported as model/Athena performance.

## Data and separation

Download the IBM harness as an HTTP archive and retain its checksum. The adapter fetches
the 500-row SWE-bench Verified parent dataset via the Hugging Face rows API, then admits
only the 449 ids in IBM's `id_list.txt`. Missing members, network failures and changed
dataset size are errors; there is no fallback to Lite or offline fixtures.

```powershell
python -m evals.tddbench fetch C:/bench/verified.sealed.json
python -m evals.tddbench prepare --dataset C:/bench/verified.sealed.json `
  --membership C:/bench/source/TDD-Bench-Verified-main/id_list.txt `
  --archive C:/bench/harness.zip --out C:/bench/run-01
```

The run manifest freezes seed, selected ids, input hashes and each harness source file.
Selection is seeded round-robin over repositories. Do not replace tasks after seeing
their results. A second prepare refuses to overwrite an existing frozen run.

`generator/*.public.json` contains only instance id, repository, base commit and issue.
`sealed/*.json` contains the evaluator's gold fixes and tests. A generator must run with
only public inputs and a base-code workspace mounted; never mount the evaluator run or
harness directory into its environment. Separate directories alone are not an OS boundary.

## Linux controller on Docker Desktop

The upstream harness imports `resource`, so run it in Linux, not native Windows Python.

```powershell
docker build -t athena-tdd-controller:20261024 `
  -f evals/tddbench/controller.Dockerfile evals/tddbench
```

The controller uses the Docker socket to build the benchmark's Linux environment and task
images. It is a trusted evaluator and must not be reused as an untrusted generator sandbox.
The one source-only dependency, wget 3.2, is pinned by archive hash and its setup inspected;
other controller dependencies use wheels. Record the final image id and installed versions.

The upstream harness executes Git commands, including clone/checkout/diff/apply/reset/clean,
inside its task workspaces. Obtain the user's separate Git authorization before using
`--git-authorized`; the flag records intent and is not itself user permission.

```powershell
# Only after actual authorization; --execute is a second explicit switch.
python -m evals.tddbench run C:/bench/run-01 `
  --harness C:/bench/source/TDD-Bench-Verified-main `
  --run-id calibration-01 --git-authorized --execute
python -m evals.tddbench report C:/bench/run-01 --run-id calibration-01
```

One worker limits memory and build concurrency. The default test timeout is 600 seconds;
image construction has its own upstream behavior and can take longer. The mount includes
only the isolated benchmark directory, not the user's Athena working copy.

## Conservative scoring

Keep upstream raw reports unchanged. The adapter reads per-instance `report.json` beneath
the run id and checks actual before/after outcomes instead of trusting the aggregate alone.
The upstream runner uses separate initial/before/final log directories; its completed
gold report is in `gold/<instance_id>/report.json`. The first real calibration confirmed
that the upstream aggregate and that final per-instance report agree.

The upstream formula counts old-code ERROR as fail-before and ignores skipped tests. Our
additional gate instead requires actual FAILED outcomes, corresponding tests PASSED after
the fix, no unknown/error/skipped outcomes, and agreement with the upstream resolved flag.
Missing reports and disagreements are INCOMPLETE. Preserve the official score and coverage
alongside this stricter status; do not present it as an unmodified official leaderboard score.

The report retains selected/evaluated/pass/fail/incomplete counts. Unrun tasks never count
as model failures or successes. Gold calibration can reveal environment or harness defects;
it cannot establish the benefit of Athena or the quality of generated specs.

## Public workspaces and code tools

Export each issue and its base source outside the evaluator directory:

```powershell
python -m evals.tddbench snapshot --public C:/bench/run-01/generator/evaluation.public.json `
  --instance psf__requests-2931 --out C:/generator/requests-2931
python -m evals.tddbench sandbox --workspace C:/generator/requests-2931 `
  --output C:/generator-output/tool-01 -- python -c "print('code tool ready')"
```

Snapshot uses GitHub's base-commit HTTP archive; it does not run Git or include repository
history. It fingerprints the archive, issue bytes and source files, refuses overwrite,
sealed fields, traversal, escaping/cyclic links and ambiguous paths. Unsupported archives are explicit
errors, not silently incomplete checkouts. The source server supplies the requested
revision; the receipt records its URL and downloaded bytes, not a Git tree verification.

Sandbox is dry-run by default; `--execute` launches it. Source and issue are read-only;
output must be empty and separate. Root filesystem is read-only, no network, no Docker
socket, non-root uid, bounded memory/CPU/processes. The prebuilt controller image is reused
for its Python tools only; neither harness nor evaluator directories are mounted. Never
use a task image for generation: its cloned repository can contain future Git history.

The standalone sandbox command is an inspection boundary. Project tests use the generator's
runtime tool below, which reconstructs POSIX metadata in its Linux workspace. The generator
calls the chosen model, exposes public tool results and accounts for contract/trust work
within the same arm budget. The cohort comparison still needs its complete orchestration
and independent evaluator runs.

Contained symlinks are stored as inert host files with explicit target metadata. Readers
receive link identity and the resolved public target, not placeholder text as source code.
File modes are recorded. The Linux pytest tool restores real links and executable bits
before tests, with temporary storage explicitly executable. No host symlinks or elevated
Windows privileges are required. Candidate overlays cannot replace or traverse source
links. This preserves link/file-mode behavior, not every checkout timestamp or directory
attribute. See ADR-0016 for the observed thirty-task preparation failures and fix.

## Direct generation protocol

```powershell
python -m evals.tddbench generate --workspace C:/generator/requests-2931 `
  --out C:/generator-output/direct-2931 --endpoint http://localhost:8000/v1 `
  --model YOUR_MODEL --max-calls 12 --max-output-tokens 4096
# Dry-run by default. Add --execute to contact the explicitly configured provider.
```

Credentials are read only from `ATHENA_BENCH_API_KEY` or the environment variable named
by `--api-key-env`. Do not embed credentials in the endpoint URL. No model or provider
fallback is selected. The transcript contains the public issue, source reads, model replies
and tool results. The receipt retains requested/served model identity, returned usage,
call limits, elapsed time, public-input hashes and prediction hash. Missing provider usage
remains unknown, not zero. Truncation and transport errors are INCOMPLETE; there are no
hidden retries. Each requested turn consumes the fixed call budget, including invalid reads.

The direct generator supports list/read/finish actions and, when a verified runtime is
provided, a bounded offline pytest action. `GENERATED` means only that a candidate unified patch was emitted;
syntax, applicability and semantic correctness are left to the independent evaluator.
The receipt never labels generation itself as model performance. Scripted protocol
controls are explicitly marked `source_kind=scripted-control` and are not inference results.

The `athena` mode executes the actual contract fast lane described below. The `athena-trust`
arm freezes that candidate, obtains a separate review and executes the native audit.
These stages have engineering controls, not real model benchmark results yet.

## Native Athena generation

Add `--mode athena` and a matching `--runtime` to generation. Finish uses a structured
`proposal` with `contract`, `scenarios`, `files` and `reference`, instead of an arbitrary
patch. Clauses use normal Athena EARS Markdown; scenarios bind clause ids to bounded
`python -m pytest ...` commands selecting submitted tests. Native code pins scenarios,
runs real specs through the offline bridge, generates the ledger and folds the native
check. Coverage, todo and drift participate. Evidence is explicitly the fast lane with
`allow_partial=True`, not a full reverse-leg verification.

Regression tests should fail on buggy base code. The green baseline is the agent's own
public reference proposal, never the evaluator's gold solution. `reference` accepts a
map of known implementation paths to full text or exact-anchor edits such as
`[{"path":"module.py","old":"return 0","new":"return 1"}]`. Anchors must occur exactly
once. Both direct and Athena run actions can test a proposal using the same optional
`implementation` field, so the code tool capability is shared.

All native baseline executions consume the same per-arm test-run budget. Infra errors
and exhausted budgets remain INCOMPLETE, not semantic failures. Native check outputs
retain framework fingerprints. Only the deterministic diff of test files becomes the
evaluator prediction; reference implementation edits are excluded and public source
remains unchanged. A green spec on a self-proposed reference is not independent evidence
of oracle validity: external old/gold evaluation and reviewer-owned trust are still needed.

## Offline tests during generation

The evaluator operator selects the matching upstream environment-only image, not a task
image. Prepare an immutable runtime receipt before a model run:

```powershell
python -m evals.tddbench runtime --workspace C:/generator/requests-1766 `
  --image sweb.env.x86_64.1f92e6d7cef88badc4f744:latest --out C:/generator/runtime-1766.json
python -m evals.tddbench generate --workspace C:/generator/requests-1766 `
  --out C:/generator-output/direct-1766 --endpoint http://localhost:8000/v1 `
  --model YOUR_MODEL --runtime C:/generator/runtime-1766.json --max-test-runs 4 --test-timeout 60
```

Generation remains dry-run unless `--execute` is present. Runtime preparation inspects a
local image and probes its Python/pytest and empty repository directory; it does not pull
images or use Git. Do not guess the dependency image for a different task. The receipt
binds the selected image id to exactly one public snapshot.

The model's run action contains `files` and `tests`. Test overlays and submitted test
nodes are validated; runner-configuration replacements are refused. An optional
`implementation` proposal may replace only known public Python implementation files,
either with full source or exact-anchor edits. It does not change the public snapshot.
The payload arrives over stdin, base source is copied inside the container and each run
starts fresh. API credentials and evaluator mounts are absent. Each invocation is limited
to 2 GiB memory, one CPU, 1 GiB temporary storage and its configured timeout. Timeout
cleanup addresses only that invocation's container.

Tool feedback distinguishes PASS, ASSERTION_FAIL, TOOL_ERROR and TIMEOUT. Local assertion
failure on old code is useful feedback, not independent proof of a valid spec. The final
candidate still needs evaluation on both old and corrected code. Capture all arm budgets
and runtime hashes before making a paired comparison.

## Frozen review and trust

Use `--mode athena-trust` for generation. A successful native proposal becomes
`AWAITING_REVIEW`; `candidate.json` is frozen but there is no evaluator `prediction.json`.
One call is reserved within `--max-calls` for the fresh-context reviewer. The generator
cannot consume that call or see the review tests. Then run the separate stages:

```powershell
python -m evals.tddbench review --workspace C:/generator/task `
  --generation C:/generator-output/trust-task --out C:/reviews/task `
  --endpoint http://localhost:8000/v1 --model YOUR_MODEL
python -m evals.tddbench trust --workspace C:/generator/task `
  --generation C:/generator-output/trust-task --runtime C:/generator/runtime-task.json `
  --review C:/reviews/task/review.json --out C:/audits/task
# Both commands are dry-run by default. Add --execute to each to perform its stage.
```

The reviewer sees only public issue/base code and the frozen proposal. The normal model
review uses the same requested model and a separate conversation; returned served-model
identity and usage are retained. Its call counts against the original total, even when
truncated. Review must cover every live clause and every bound spec. Reviewer declarations
are not independent semantic truth or signed attestations. Human review is explicitly a
different origin; its work must not be hidden in a model-only comparison. Scripted reviews
cannot release real model candidates as if they were independent inference.

Trust runs actual `lib.spec_trust.audit`, not a prompt imitation. It uses the public
agent-proposed reference, valid alternatives and activated violations. The activation
must first ASSERTION_FAIL on the clean reference and then PASS on the violation. Candidate
and activation tests run in separate containers without each other's submitted files.
Every execution uses the original arm's test budget. Default limits are twelve model
calls and twelve test runs for all modes; more clauses can legitimately exhaust them.
Freeze chosen study limits before real inference rather than adjusting them after results.

Missing, changed, incomplete or over-budget review remains INCOMPLETE. Only PASS releases
the exact frozen test patch to `prediction.json`. Review cannot repair candidate tests.
The wrapper records the pinned container runtime separately: native audit environment
metadata describes the host orchestrator. A native PASS is scoped curated evidence and
still requires external old/gold-code evaluation before any model-quality claim.

## Model submissions

Evaluation uses the existing frozen thirty-task cohort. Put model-generated test patches
in a JSON array or JSONL file inside the benchmark directory. Each row requires
`instance_id` and a string `model_patch`. Duplicate and out-of-cohort ids are rejected.
Missing predictions remain INCOMPLETE in the full cohort; they do not shrink the denominator.
Empty test patches remain submissions, never substituted with gold tests.

```powershell
python -m evals.tddbench run C:/bench/run-01 --harness C:/bench/source `
  --run-id direct-01 --git-authorized --mode evaluation --predictions predictions/direct.json
# Inspect the command first; add --execute to run it.
python -m evals.tddbench report C:/bench/run-01 --run-id direct-01 --mode evaluation
```

The runner evaluates supplied patches; it does not generate them or prove they were
generated blind. Retain generator provenance separately. A synthetic or manually authored
submission must not be presented as model performance, even in evaluation mode.

## Sources
- https://github.com/IBM/TDD-Bench-Verified
- https://arxiv.org/abs/2412.02883
- https://www.swebench.com/SWE-bench/guides/evaluation/

## Review input representation and diagnostics

Independent review receives lossless `reference_delta` line arrays in Python ndiff
format. Restore mode 1 is the validated base; mode 2 is the model-proposed reference.
Unchanged source occurs once and redundant proposal reference copies are omitted.
No source is truncated and the original context limit remains enforced. This encoding
does not make the proposed reference a gold oracle or attest reviewer semantics.

Passports must list exactly the scenario IDs bound to each clause. Bounded pytest
commands accept only `-q`, `-v`, and `-vv`; other flags are rejected explicitly before
execution. Audit validation errors preserve charged generation/review budgets and a
bounded typed explanation. Only the native challenge policy can release a prediction.

Before every completion, `execution_budget` states remaining generation calls including
the current request, reserved review calls, remaining shared test runs and the output
acceptance limit. It is trusted operator metadata retained in the transcript and charged
to the existing context budget. It grants no extra execution or provider spending cap.

Existing named test function/method AST definitions cannot be changed, removed or
shadowed by an overlay or exported patch. Additive tests remain supported. This
structural guard does not attest helper, fixture, import or dynamic collection semantics.

Independent review now requests a different valid mechanism and representation when
the public issue permits that freedom, and asks for issue-based justification of exact
literals and internal state. These are reviewer instructions, not a semantic-diversity
verifier. Native acceptance, real knowledge gaps and execution error typing are unchanged.

Review context includes remaining shared calls/tests and audit cost estimates derived
from each clause's bound commands. Pending native execution is a phase status; reviewers
must retain real semantic gaps, and native evidence still handles actual execution failures.
