# Self-improvement pilot: frozen corpus

`manifest.json` freezes 36 real SWE-bench Lite issues from revision
`6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2`: three per repository, with two
development tasks and one holdout task per repository. Selection is deterministic.
Each entry pins the issue input, repository base commit and acceptance material by
SHA-256. Verify it with `python -m evals.self_improve.corpus verify`.

The manifest contains no task text or test patch. A runner must fetch the pinned
dataset revision, verify the fingerprints, and pass only `problem_statement` and
`hints_text` to the agent. The holdout is **procedurally isolated**: it is a public
dataset, so secrecy against an agent with unrestricted network access is not proven.
Optimizer candidate generation and selection must use development tasks only; a
finalist gets one holdout evaluation after its configuration is fixed.

This corpus is an input, not a result. The repository currently has no 36-task,
three-arm execution report. Published plan-quality evals and the `athena bench`
executor matrix measure different questions and cannot serve as that report.

`evidence.py` validates one JSONL record per attempt against the frozen corpus and
the bytes of its gate artifact. A report exits with code 2 while any of the 108
task-arm cells is absent. It charges every failed attempt to the total cost of the
arm and reports Wilson intervals for success rates. A string naming the official
gate does not authenticate a report by itself; the eventual runner must capture
the independent harness output and preserve its execution logs.

To extend the benchmark to 50 or more tasks, publish a new manifest version with a
new selection seed before running candidates. Retain the original 36-task manifest
and all run records for comparison. Keep the same per-repository split rule where
possible; document any new repositories or changed eligibility rules. Never add
tasks to the frozen manifest after viewing optimizer results.
