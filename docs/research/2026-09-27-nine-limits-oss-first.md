# Athena research digest: the nine limits, what open source closes and what stays from scratch (2026-09-27)

Scope: the nine aspects of development the frame does not cover after the ten gaps closed (see
`features/foundry-layer/README.md`, "The ten gaps on 2026-09-27"). Constraints that filter every
candidate: Python frame, native Windows 11, no Docker and no WSL on the box, executors are 3B-9B
local models behind vLLM/llama.cpp, verdicts are pytest runs, permissive licence preferred.

Method: three parallel web surveys (limits 1-3, 4-6, 7-9) over repos, PyPI, docs and papers on
2026-09-27; licences and activity read from the sources linked at the end of each section. Where a
report could not confirm a licence or a Windows path it says unknown. "OSS pick" is what we would
pip-install, vendor or copy a recipe from; "from scratch" is what no project does for us.

Summary, coarse:

| limit | how much OSS covers | what stays ours |
|---|---|---|
| 1 where clauses come from | the artifact pipeline and the repair loop | EARS from prose; clause-to-test templates; sibling-test retrieval for a 9B drafter |
| 2 oracles beyond a command | every oracle itself (visual, a11y, prose, API, LLM judge) | the adapter from each oracle's JSON to a pytest verdict with per-clause thresholds |
| 3 multi-file change | rename, codemod, structural rewrite, dependency graph | the planner that cuts a refactor into ordered one-window tasks |
| 4 external world | HTTP replay, API contracts, embedded Postgres, migrations, cloud mocks | the incident-to-red-test loop (no OSS autofix survives without a SaaS) |
| 5 effectful and concurrent code | contracts, stateful property tests, fake filesystem and git | fuzzing and race detection on Windows; subprocess record/replay |
| 6 unpinned behaviour | snapshots, approvals, characterization test generation | divergence to proposed assertion |
| 7 legacy without contracts | characterization tests, repo docs, dependency graphs, traceability stores | tests-to-clauses lifting; the clause-to-lines map from coverage (nothing does this) |
| 8 security and review | SAST, secrets, deps, threat-model-as-code, AI review via LiteLLM, policy gates | the wiring into the merge queue and the local-model prompt sizing |
| 9 evaluation of rungs | the eval runner, the trace store, change-point statistics | the drift alert over the ladder's own records |

---

## Limit 1. Where clauses come from (intent -> EARS clause -> red test)

### (a) Existing work
- github/spec-kit (specify-cli) - MIT, v1.0.12 Sep 2026. Spec/plan/tasks templates, PowerShell scripts. No EARS (open issue #1356), no test generation.
- Fission-AI/OpenSpec - MIT, active Sep 2026. Delta specs with SHALL requirements and Scenario blocks (`schemas/spec-driven/`). Node 20; Windows path undocumented.
- Kiro (AWS) - proprietary. requirements.md in EARS -> design.md -> tasks.md; the three-artifact contract is the reference design.
- CoverUp (plasma-umass) - Apache-2.0, FSE 2025. Coverage-guided prompt-and-repair loop for pytest; providers are OpenAI/Anthropic/Bedrock, a local-endpoint adapter is missing.
- qodo-cover - AGPL-3.0, unmaintained since 2025-06. Its acceptance filter (builds, passes, raises coverage) is the same idea as our C-2.1 admission.
- Hypothesis ghostwriter (+ CrossHair backend) - MPL-2.0 / Apache-2.0. Property scaffolds from type hints; deterministic, no model.
- Pynguin - MIT, 0.47.0 with an LLM-on-stall mode (release year read as 2026 by one survey and 2024 by another; verify on the releases page). Regression assertions, not spec-derived.
- YATE (paper, 2025) - rule-based static repair of a drafted test before re-prompting: +32% lines, +22% mutants killed in the paper. No code URL found.
- BMAD-METHOD, Tessl tile - MIT, prompt-heavy and frontier-sized; skip.

### OSS pick
CoverUp's loop shape (Apache) plus YATE-style static pre-repair rules, on top of our own admission rule; OpenSpec's SHALL-plus-Scenario schema as the shape of a drafted clause; Hypothesis ghostwriter for invariant-type clauses.

### (b) Reusable vs build
Reusable: the repair loop, the coverage feedback, the spec schema, the ghostwriter. Build: EARS from prose (no project produces it today), the clause-to-test template library, sibling-test retrieval into the drafter's packet, the local-endpoint adapter.

### (c) Smallest experiment
Arm 6 of `tools/draft_acceptance.py`: add three static repairs before each re-prompt (missing import, keyword-only argument, undefined result key) and one sibling spec of the same clause group in the packet. Measured against arms 4 and 5 (5 of 13, 4 of 13).

### (d) Pitfalls
Every OSS drafter is tuned for frontier models; our measurements say the 9B fails on signature reading, not on prose. The lever is retrieval and static repair, not a bigger prompt.

Sources: spec-kit releases, spec-kit issue #1356, OpenSpec repo, Kiro requirements docs, CoverUp repo and paper (arXiv 2403.16218), qodo-cover repo, Pynguin releases, YATE (arXiv 2507.18316), Hypothesis changelog.

---

## Limit 2. Oracles beyond "run a command"

### (a) Existing work
- Playwright (Node) `toHaveScreenshot` + pixelmatch - Apache-2.0 / ISC. Visual snapshots, headless Chromium, Windows native. The Python bindings lack the screenshot assertion.
- axe-core via @axe-core/playwright or axe-playwright-python - MPL-2.0. WCAG 2.2 violations as JSON.
- Vale - MIT, Aug 2026, single Go binary. Prose linting with a style YAML. textlint (MIT, Node) second.
- Spectral - Apache-2.0, active. OpenAPI/AsyncAPI rulesets for API ergonomics.
- Inspect AI (UK AISI) - MIT, 2026. Eval harness with native vLLM, llama-cpp-python, Ollama and openai-api providers; sandboxes need Docker, plain scoring does not.
- DeepEval - Apache-2.0. pytest-shaped metrics with a custom local judge class and schema enforcement.
- promptfoo - MIT. YAML comparisons against any OpenAI-compatible URL; prompt A/B rather than verdicts.
- Storybook 9 Vitest addon, BackstopJS, Lost Pixel - only if a component layer appears.

### OSS pick
Inspect AI as the judge harness for local models; Node Playwright with pixelmatch and axe-core for UI; Vale for prose; Spectral for APIs.

### (b) Reusable vs build
Reusable: every oracle. Build: one adapter per oracle that turns its JSON into a pytest node bound to a clause, with a threshold the clause names (the C-9.5 pattern), and the golden-file discipline of C-9.6 for screenshots.

### (c) Smallest experiment
One clause on `athena check --text` output: Vale with a five-rule style on the rendered report, bound through a config that names the clause (the C-9.4 binding pattern). Then one LLM-judge clause on a packet's brief with Inspect AI scoring through the 9B lane, and its agreement with the operator measured on twenty packets.

### (d) Pitfalls
A judge is a third-kind oracle: it must be calibrated against a human on a sample before it gates anything, and it belongs in the advisory column until then. Visual snapshots invite "update the baseline" as the fix; C-9.3 already refuses that flag.

Sources: Playwright Python assertions, axe-playwright-python on PyPI, Vale repo, Spectral repo, Inspect providers page, DeepEval custom-LLM guide, promptfoo providers.

---

## Limit 3. Architectural change across many files

### (a) Existing work
- LibCST codemods - MIT, 1.9.0 (2026). Format-preserving transforms, `RenameCommand`, import helpers.
- rope - LGPL-3.0, 1.15.0. Cross-module rename and move with reference resolution; offset-based API.
- ast-grep / ast-grep-py - MIT, 0.45.3 Aug 2026. Structural search and rewrite by YAML rule; wheels for Windows.
- grimp + import-linter - BSD-2, grimp 3.17 Sep 2026 with a Rust core and Windows wheels. Import graph, layer contracts, shortest chains.
- Codemod CLI - Apache-2.0. YAML workflows with multi-step, matrix and approval gates; ast-grep first-class; Windows unknown.
- Aider repo-map - Apache-2.0. tree-sitter plus PageRank ranking; extractable.
- OpenRewrite for Python - archived Jan 2026, Python only through the commercial Moderne. Bowler archived. Comby needs WSL. OpenHands Refactor SDK - closed beta.

### OSS pick
rope for semantic rename, LibCST for format-preserving codemods, ast-grep for cheap rewrites and post-edit assertions, grimp as the dependency graph that orders tasks and import-linter as the gate.

### (b) Reusable vs build
Reusable: every engine. Build: the planner. Nothing open-source decomposes a refactor into ordered small tasks; walking the grimp graph leaf-first, emitting one task per module with its specs, and gating each with import-linter contracts is ours. The 9B's role shrinks to filling codemod parameters, which is where a small model is reliable.

### (c) Smallest experiment
Rename one public function used in four modules: rope does the rename in one step as a baseline; then the same change as four leaf-first tasks through the daemon, each judged by its specs and the layer contract. Measure iterations, green rate, and whether the merge queue ever saw a conflict.

### (d) Pitfalls
Codemods are deterministic and cheap; the expensive part is deciding the order and the boundaries, and that is a plan, not a packet.

Sources: LibCST releases, rope releases, ast-grep-py on PyPI, grimp on PyPI, import-linter release notes, Codemod repo, rewrite-python repo (archived), OpenHands blog on the Refactor SDK.

---

## Limit 4. The external world without Docker

### (a) Existing work
- VCR.py / responses / respx / pook - MIT. HTTP record and replay for requests and httpx; cassettes are fixtures.
- Schemathesis - MIT, 2026. OpenAPI/GraphQL property tests, stateful links.
- Pact Python v3 - MIT, GA Dec 2025 on a Rust FFI. Consumer/provider contracts; only if more than one service.
- embedded-postgres (fork of pgserver) - Apache-2.0 plus the PostgreSQL licence, 18.6.3 Sep 2026. A pip wheel with a real PostgreSQL 18 and pgvector, win_amd64. pytest-postgresql (LGPL-3) as the fixture layer; pytest-alembic (MIT) for migrations.
- moto - Apache-2.0. AWS mocks in process. MinIO's community binaries are gone (archived early 2026); SeaweedFS or Garage if an S3 binary is needed.
- OpenTelemetry Python SDK with a file exporter - Apache-2.0. Capture layer for traces and logs.
- Sentry self-hosted - FSL; Docker only; Seer/Autofix is private and gated off self-hosted.
- AssertFlip (uw-swag) - Apache-2.0, ICSE 2026. Issue to failing test by writing a passing test on the buggy behaviour and inverting it. SWT-Bench (MIT) as the evaluation set; Otter and BLAST as papers.

### OSS pick
embedded-postgres + pytest-postgresql + pytest-alembic for the database, VCR.py/respx for HTTP, Schemathesis for contracts, moto for cloud, OpenTelemetry file exporter for capture, AssertFlip's recipe for the repro loop.

### (b) Reusable vs build
Reusable: all the stand-ins. Build: the incident loop. Capture a trace, extract the request shape and the state into a fixture, hand the 9B AssertFlip's two-step prompt, admit the result with the C-2.1 rule (fails on the bug, passes on the fix). No OSS product does this outside a SaaS.

### (c) Smallest experiment
One real failure from the daemon's own ledger (a red verdict with its tail) turned into a red spec by the AssertFlip recipe through the 9B, judged by the admission rule; ten failures, admitted count.

### (d) Pitfalls
Cassettes rot; every replay fixture needs a freshness policy and redaction, and a clause that says so. The sandbox's network fence must stay closed: stand-ins run in process or on loopback inside the proxy range.

Sources: embedded-postgres on PyPI, pgserver repo, pytest-alembic, moto, MinIO status (InfoQ 2025-12), Sentry self-hosted issue #3249, AssertFlip repo, SWT-Bench repo, Otter (arXiv 2502.05368), BLAST (arXiv 2509.01616), Pact Python v3 announcement, Schemathesis.

---

## Limit 5. Effectful and concurrent code

### (a) Existing work
- Hypothesis RuleBasedStateMachine - MPL-2.0. Model-based tests with shrinking. hypothesis-jsonschema (0.23.1, 2024) for schema strategies.
- icontract - MIT, 2.7.3 Jan 2026. Design by contract, CrossHair-native (`--analysis_kind icontract`). deal (MIT, 4.24.6) adds purity and side-effect markers.
- pyfakefs - Apache-2.0. In-memory filesystem. fake-git-remote, pytest-git, dulwich for local git fixtures.
- CrossHair - MIT, 0.0.109. Analysis kinds asserts, PEP316, icontract, deal, hypothesis; an audit hook stops dangerous side effects; nondeterministic code gives wrong or failed results by design.
- detangle (PyPI, 2026) - licence unknown. The only Python deterministic-simulation loop found: deterministic asyncio scheduling, schedule fuzzing, replay token, shrinking; asyncio only.
- atheris - Apache-2.0, Linux/macOS only. ThreadSanitizer on free-threaded CPython - Linux/clang builds. Neither runs here.

### OSS pick
icontract on the pure core so CrossHair and the mutation gate see the contracts; Hypothesis stateful tests for anything with state; pyfakefs and local git fixtures for effects; detangle evaluated on the daemon's asyncio if it ever gains one.

### (b) Reusable vs build
Reusable: contracts, stateful tests, fakes. Build: fuzzing and race detection on Windows (a Hypothesis-driven fuzz loop; schedule perturbation through `sys.settrace` for threads), and a record/replay layer for subprocess and git so the effectful edge gets the treatment HTTP already has.

### (c) Smallest experiment
A stateful Hypothesis model of the merge queue (admit, rebase, check, mutation, fast-forward) against `lib/refinery.py` with an in-memory git fake; count the states it visits and the bugs it finds in an afternoon.

### (d) Pitfalls
CrossHair's equivalence proofs end where I/O begins; the injected-runner style we used for git is the right seam and should be a clause, not a habit.

Sources: Hypothesis docs, icontract on libraries.io, deal on PyPI, hypothesis-jsonschema on PyPI, pyfakefs, fake-git-remote, CrossHair contract kinds and the nondeterminism note, detangle on PyPI, atheris repo, py-free-threading TSan guide.

---

## Limit 6. Unpinned behaviour and characterization

### (a) Existing work
- syrupy - Apache-2.0, 2026. pytest snapshots with serializers. ApprovalTests.Python (Apache-2.0) for approvals and combination approvals. pytest-snapshot superseded. TextTest (LGPL) for whole-program text approval.
- Pynguin - MIT. Search-based regression tests with assertions; executes the code under test, so it runs inside the sandbox.
- Hypothesis ghostwriter - MPL-2.0. Roundtrip, idempotent and equivalence skeletons.
- CrossHair diffbehavior - MIT, already our C-8.2 gate.
- Daikon - MIT, 5.9.1 Sep 2026. Likely-invariant inference; JVM, weak Python front end; the idea to copy.
- DiffSpec (paper) - differential tests from a natural-language spec; prompt design reference.
- qodo-cover - AGPL, unmaintained; reference only.

### OSS pick
syrupy for golden masters (our C-9.6 discipline generalised), ApprovalTests combination approvals for pinning behaviour tables, Pynguin plus the ghostwriter for characterization without a model.

### (b) Reusable vs build
Reusable: pinning and generation. Build: divergence to proposed assertion. Diff two runs or two snapshots, mine Daikon-style invariants from the traces, and let the small model only phrase the contract sentence. This is exactly what the frontier did by hand on 27.09 for nine functions.

### (c) Smallest experiment
Feed the pass-2 diffbehavior report (eleven functions) to a script that turns each counterexample into a proposed sealed assertion; count how many the reviewer keeps unchanged.

### (d) Pitfalls
A characterization test pins the bug with the behaviour; the admission rule must still require the forged break, or the sealed tier fills with regressions dressed as readings.

Sources: syrupy, ApprovalTests.Python, Pynguin on PyPI, Daikon repo, qodo-cover repo, TextTest repo.

---

## Limit 7. Legacy code without contracts (spec archaeology)

### (a) Existing work
- Pynguin 0.47.0 (MIT) with LLM-on-stall, YAML prompt templates: the characterization engine; its LLM hook can point at the vLLM lane.
- Hypothesis ghostwriter (MPL-2.0): property skeletons per function for a 3B to fill.
- CoverUp (Apache-2.0): the coverage-guided loop, pattern to copy; Windows untested.
- OpenSpec (MIT): brownfield delta specs and an onboarding explore step; frontier-sized prompts.
- deepwiki-open (MIT): repository to wiki through RAG with Ollama or local models; behaviour-doc drafts.
- GitNexus (PolyForm Noncommercial): the best tree-sitter call/import/inheritance graph with Cypher and MCP; the licence blocks commercial use. pydeps / code2flow (BSD-2 / MIT) as the safe lightweight graph; CodeQL CLI needs a GHAS licence for private repos.
- StrictDoc (Apache-2.0): requirements tree, trace matrix, web UI, code-level relation markers. Sphinx-Needs (MIT), doorstop (LGPL-3), OpenFastTrace (GPL-3, Java) as alternatives.
- SpecGen (ICSE 2025), KBSpec: LLM to JML specifications with a mutate-and-verify repair loop; Java, mine the loop.

### OSS pick
Pynguin plus the ghostwriter for characterization, OpenSpec's delta and explore flow as the onboarding skeleton, StrictDoc as the traceability store if the frame's own contract.md ever needs a matrix, tree-sitter plus pydeps for the graph until GitNexus's licence question is settled.

### (b) Reusable vs build
Reusable: test generation, docs, graphs, traceability. Build: lifting tests into clauses through a small model (the reverse of drafting, and probably easier: a passing test is a concrete example, a clause is its generalisation), and the clause-to-lines ownership map derived from coverage, which nothing open-source produces and which is the frame's spine.

### (c) Smallest experiment
One foreign repository of about two thousand lines without tests: Pynguin for an hour, then the 9B asked to phrase one EARS clause per admitted test, admitted by the EARS validator (C-2.2) and by a human on a sample of twenty. Cost in frontier tokens per admitted clause is the number to publish.

### (d) Pitfalls
Characterization pins the present, including its bugs; the onboarding contract must mark every lifted clause `source: archaeology` so a later reviewer knows nobody chose it.

Sources: Pynguin releases, CoverUp repo, OpenSpec repo, deepwiki-open repo, GitNexus repo and licence, StrictDoc FAQ, SpecGen (ICSE 2025), CodeQL CLI licence.

---

## Limit 8. Security and review as practice

### (a) Existing work
- Semgrep CE / OpenGrep - LGPL-2.1; Semgrep's rules carry a restricted licence, OpenGrep is the free fork; native Windows since the Fall 2025 release. Bandit (Apache-2.0) for Python SAST.
- gitleaks (MIT) and trufflehog (AGPL-3) for secrets; Go binaries.
- pip-audit and OSV-Scanner (Apache-2.0), Grype via winget, for dependencies and SBOM.
- pytm (MIT, Python, needs Graphviz), Threagile (MIT, YAML), OWASP Threat Dragon (Apache-2.0) for threat modelling as code.
- PR-Agent (Apache-2.0, now community-governed): review, describe, improve through any LiteLLM model, so through our lanes. reviewdog and Danger (MIT) as sinks and scripted rules. CodeRabbit is SaaS only.
- conftest (OPA, Apache-2.0): Rego policy over JSON and YAML, the executable checklist.

### OSS pick
OpenGrep, Bandit, gitleaks, pip-audit with OSV, pytm, PR-Agent through LiteLLM to the 9B lane, conftest over the frame's own provenance and merge records.

### (b) Reusable vs build
Reusable: every scanner and the review bot. Build: the wiring into the merge queue as stages with clauses (the C-11.2 pattern), the prompt sizing of PR-Agent for a 30k window, and the policy set in Rego that says what a record must carry before it merges.

### (c) Smallest experiment
Two new stages in `athena merge`: `scan` (OpenGrep + Bandit + gitleaks on the diff, refuse on a finding above a threshold) and `policy` (conftest over the merge record: provenance present, sealed untouched, mutation stage ran). Measured on the last thirty merges replayed.

### (d) Pitfalls
A review bot on a 9B will flatter; keep it advisory and measure agreement with the operator before it can refuse. Threat models as code are only as alive as the clause that regenerates them from the architecture graph.

Sources: Semgrep CE Fall 2025 release notes, OpenGrep, Bandit, gitleaks, trufflehog, pip-audit, OSV-Scanner, Grype install docs, pytm (OWASP dev guide), Threagile, Threat Dragon, PR-Agent stewardship note, reviewdog, conftest.

---

## Limit 9. Continuous evaluation of the rungs

### (a) Existing work
- promptfoo - MIT, 0.121.x. Evals with a SQLite store under `~/.promptfoo`, a generic openai provider with a base URL, assertions and a diff UI.
- DeepEval - Apache-2.0. pytest-shaped metrics with a custom judge; judges need at least the 9B.
- Inspect AI - MIT. Tasks, solvers, scorers, `.eval` logs, vLLM and openai-api providers; sandboxes need Docker, plain tasks do not.
- lm-evaluation-harness - MIT. `local-completions` against vLLM, 200+ tasks: raw capability sanity per rung.
- Phoenix (Arize) - ELv2. pip, single process, SQLite, traces and LLM evals. Langfuse needs Postgres, ClickHouse and Redis: skip.
- SWE-smith / terminal-bench - MIT / Apache-2.0. Task generation and terminal tasks; Docker and Linux; borrow the task format only. OpenAI evals: hosted shutdown 2026-11, skip.
- ruptures (BSD), statsmodels CUSUM, evidently (Apache-2.0) for change points and drift over a pass-rate series.

### OSS pick
promptfoo as the per-rung regression runner over the frame's own task set (the ladder's records are already a task set with provenance), lm-eval `local-completions` as the raw capability check after a model or runtime swap, Phoenix for traces, ruptures with a CUSUM over the pass-rate series.

### (b) Reusable vs build
Reusable: runner, store, statistics. Build: the drift alert. `athena bench` and C-5.3 already report per rung; the missing piece is a nightly run of a fixed task set per lane, the series in SQLite, and a change-point detector that opens a bead when a rung drops.

### (c) Smallest experiment
Twenty tasks from this week's ledger as a fixed set; run nightly on each lane through `athena bench`; after the next model or runtime swap, see whether the CUSUM fires before a human notices.

### (d) Pitfalls
A rung's pass rate moves with the packets, not only with the model; the fixed set must be frozen with its packets and provenance, or the series measures the frame's drift, not the model's.

Sources: promptfoo self-hosting and providers docs, DeepEval custom-LLM guide, Inspect AI site, lm-evaluation-harness repo, Phoenix repo, Langfuse vs Phoenix comparison, SWE-smith repo, terminal-bench repo, OpenAI evals deprecation note, drift-detection survey 2026.

---

## What is genuinely from scratch, across all nine

1. EARS clauses from prose, and tests lifted back into clauses (limits 1 and 7). No project does either; both are small-model tasks with an admission rule, which is the frame's own pattern.
2. The clause-to-lines ownership map from coverage (limit 7). Nothing open-source produces it; it is the spine of the gate and stays ours.
3. The planner that cuts a refactor into ordered one-window tasks over a dependency graph (limit 3).
4. The incident-to-red-test loop without a SaaS (limit 4), and divergence-to-assertion (limit 6): both are "capture, then let the small model phrase it, then admit by the forge".
5. Fuzzing and race detection on Windows (limit 5).
6. The drift alert over the ladder's own records (limit 9), and the merge-queue wiring for scanners and policy (limit 8).

Order of work by leverage, same rule as on 25.09: what unblocks the local rung first. Limit 1's static pre-repair and retrieval (an afternoon, measured against 5 of 13); limit 8's two merge stages (a day, all OSS); limit 9's nightly set (a day); limit 7's one foreign repository (the number nobody has); limit 3's planner last, because it is the only one that needs design before code.
