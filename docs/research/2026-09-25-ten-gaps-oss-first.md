# Athena research digest: ten gaps, state of the art as of 2026-09-25

Scope: local spec-first factory (EARS clauses in contract.md, red specs in scenarios.md/pytest, dispatcher -> pi harness -> small local model, relay, refinery merging green worktrees, clause-to-lines map, mutation layer, forge). Executors: Nanbeige4.2-3B (llama.cpp), Qwen3.5-9B / OmniCoder-9B (vLLM 0.21, native Windows, 3090+3060). Frontier (Opus) writes clauses/specs and reviews.

Method: primary sources (repos, docs, arXiv). Stars / last-push month were read from the GitHub API on 2026-09-25. "OSS pick" = the repo we vendor/fork/pip-install to cover most of the gap; "Build" is only claimed where no maintained OSS covers it. Athena-side facts are limited to the task description; nothing else about Athena is assumed.

---

## Gap 1. Regeneration from spec + behavioural equivalence

### (a) Existing work
- GitHub Spec Kit - https://github.com/github/spec-kit - MIT, 138.9k stars, pushed 2026-09. Specify -> Plan -> Tasks -> Implement templates + `specify` CLI; agent-agnostic; constitution file. No equivalence checking. Feature request for EARS: https://github.com/github/spec-kit/issues/1356.
- OpenSpec - https://github.com/Fission-AI/OpenSpec - MIT, 70.3k, 2026-09. Single living spec + change proposals (delta specs); no oracle.
- Kiro specs - https://kiro.dev/docs/specs/ - proprietary IDE. requirements.md in EARS ("WHEN ... THE SYSTEM SHALL ..."), design.md, tasks.md; tasks map back to requirement IDs; recommends many small per-feature specs (https://kiro.dev/docs/specs/best-practices/). Closest published analogue to contract.md.
- Tessl framework + registry - https://docs.tessl.io/use/spec-driven-development-with-tessl , tile https://github.com/tesslio/spec-driven-development-tile (MIT, 54, 2026-03). Framework closed beta; "existing code -> spec" workflow documented. Little to reuse beyond prompts.
- CrossHair `diffbehavior` - https://github.com/pschanely/CrossHair - MIT, 1.3k, 2026-09; docs https://crosshair.readthedocs.io/en/latest/diff_behavior.html . SMT-driven search for inputs where two functions diverge. Requires type annotations, deterministic code, deep-copyable/equality-comparable args; "target the smallest piece of logic"; absence of counterexample is not proof.
- Hypothesis - https://github.com/HypothesisWorks/hypothesis - MPL-2.0, 9.0k, 2026-09; CrossHair backend `hypothesis-crosshair` https://github.com/pschanely/hypothesis-crosshair (MIT, 28, 2026-09). Property tests + `settings(backend="crosshair")`.
- Research: EnsLLM uses diffbehavior to cluster LLM candidates by equivalence (https://arxiv.org/abs/2503.15838); DiffSpec derives differential tests from NL specs (https://arxiv.org/abs/2410.04249); CodeSpecBench (executable behavioural specs from LLMs, https://arxiv.org/abs/2604.12268); "Do coverage and mutation scores of LLM test suites correlate with effectiveness" (https://arxiv.org/abs/2607.22880).

### OSS pick
CrossHair (pschanely/CrossHair, MIT, 1.3k, 2026-09) + Hypothesis (MPL-2.0). Spec Kit is worth reading for templates only; Athena already has the spec layer.

Integration plan:
1. `athena regen <module>` packs contract.md clauses + scenarios.md + public signatures only (no old body) and dispatches a fresh worktree.
2. Glue (~150 LOC): for every public function with type hints, run `crosshair diffbehavior old.mod.f new.mod.f --per_condition_timeout 20`; collect counterexamples into the verdict.
3. Equivalence gate = red specs green AND diffbehavior clean AND per-clause mutation score of the regenerated module >= score of the original (uses Gap 3 tooling).
4. Hypothesis strategies for the module's public types live next to scenarios.md and are reused by both gates.

### (b) Reusable vs build
Reusable: CrossHair CLI, Hypothesis, Kiro's spec layout as a checklist. Build: the regen packet (signature-only view of the module), the three-part gate, and reporting per clause.

### (c) Smallest experiment
Pick one pure module (5-10 functions, typed, <300 LOC). Regenerate 5x with the 9B model from clauses+specs only. Measure: specs pass rate, diffbehavior counterexamples per function, mutation score delta vs original, LOC delta. Success: >=3/5 regenerations pass all three gates.

### (d) Pitfalls
diffbehavior needs annotations and no I/O; wrappers with subprocess/network need `--unblock` and become meaningless. Equivalence to the *old body* is the wrong target if the old body had bugs; the spec is the oracle, diff is a smell detector. Mutation-score parity is noisy on small modules (see Gap 3).

---

## Gap 2. Oracles of the second kind (architecture, budgets, snapshots, UI)

### (a) Existing work
- import-linter - https://github.com/seddonym/import-linter - BSD-2, 1.2k, 2026-09. Contracts (`forbidden`, `layers`, `independence`, custom) in `.importlinter`; `lint-imports` exit code.
- Tach - https://github.com/tach-org/tach - MIT, 2.8k, 2026-09. Rust-backed; `tach.toml` with `depends_on` and public interfaces; `tach check` non-zero on violation.
- pytest-archon - https://github.com/jwbargsten/pytest-archon - Apache-2.0, 91, 2025-09. ArchUnit-style `archrule(...).match(...).should_not_import(...)` inside pytest; low activity.
- pytest-memray - https://github.com/bloomberg/pytest-memray - Apache-2.0, 424, 2026-09. `@pytest.mark.limit_memory("10 MB")`, `--fail-on-increase`. Linux/macOS only (memray needs ptrace/ld tricks) - not usable natively on Windows.
- pytest-benchmark - https://github.com/ionelmc/pytest-benchmark - BSD-2, 1.45k, 2026-08. `--benchmark-compare=<id> --benchmark-compare-fail=mean:10%`; JSON storage. Works on Windows.
- syrupy - https://github.com/syrupy-project/syrupy - MIT, 888, 2026-09. `assert x == snapshot`, `--snapshot-update`; extension classes for JSON/image.
- UI oracles: Playwright `expect(page).toHaveScreenshot()` (Apache-2.0); for TUIs, pytest-textual-snapshot (SVG snapshots).

### OSS pick
import-linter (seddonym/import-linter, BSD-2, 1.2k, 2026-09) for structure; pytest-benchmark for time budgets; syrupy for golden output. Skip memray on native Windows; use `tracemalloc` peak inside a pytest fixture (stdlib) as the memory oracle.

Integration plan:
1. Extend the clause grammar with `oracle: run_cmd` (already exists per description) and three canned oracle kinds: `arch` -> `lint-imports --config <generated .importlinter>`, `perf` -> `pytest -m bench --benchmark-compare-fail=mean:<pct>%`, `golden` -> `pytest --snapshot-warn-unused` on a syrupy dir.
2. Generator (~100 LOC) renders an `.importlinter` from EARS clauses of the shape "the <pkg> SHALL NOT import <pkg>" / "layers".
3. Clause-to-lines map records the config line, not code lines, for these clauses.
4. Refinery runs these oracles after unit specs, same red/green semantics.

### (b) Reusable vs build
Reusable: all four tools as-is. Build: clause -> config renderer, a tracemalloc budget fixture (~30 LOC), and baseline storage per branch for benchmark/snapshot.

### (c) Smallest experiment
On one package with 3 layers: write 3 arch clauses, 2 perf clauses (<=20% regression), 1 golden clause. Break each on purpose in a worktree; assert refinery refuses all 6 and accepts the clean branch. Measure total oracle time (<60 s target).

### (d) Pitfalls
Benchmarks on a box also running vLLM are noisy: pin to one core, use `--benchmark-min-rounds`, compare medians, require 2 consecutive failures. Snapshot tests invite "update snapshot" as the fix; forbid `--snapshot-update` inside executor runs (policy in relay). Tach and import-linter disagree on namespace packages; pick one.

---

## Gap 3. Mutation testing as a merge gate; hidden test tier

### (a) Existing work
- mutmut - https://github.com/boxed/mutmut - BSD-3, 1.45k, 2026-09. v3: in-process trampoline, coverage-based test selection, `mutate_only_covered_lines`, pragmas. **Requires fork -> no native Windows** (docs: https://mutmut.readthedocs.io/). Does not rerun mutants when tests change.
- cosmic-ray - https://github.com/sixty-north/cosmic-ray - MIT, 658, 2026-08. Session DB (sqlite), operators, `cr-filter-git` (skips mutants outside `git diff -U0 <branch>` lines; src/cosmic_ray/tools/filters/git.py), `cr-filter-pragma`, `cr-filter-operators`, local + HTTP distributors. Pure multiprocessing, runs on Windows.
- poodle - https://github.com/WiredNerd/poodle - MIT, 5 stars, 2026-04 (tiny). mutatest - MIT, 102, last push 2023-02 (dead).
- Comparison papers: IEEE 2024 "Analysis and Comparison of Mutation Testing Tools for Python" (https://ieeexplore.ieee.org/document/10818231/); ACM SBQS 2024 (https://dl.acm.org/doi/10.1145/3701625.3701659); hybrid fault-driven mutation (https://arxiv.org/html/2601.19088v1).
- Hidden/strengthened tests: "Investigating Test Overfitting on SWE-bench" (https://arxiv.org/abs/2511.16858): 21.8% (Claude 3.7) / 33.0% (GPT-4o) of patches passing generated tests fail hidden tests; refinement against visible tests raises it to 25.5%/35.9%; showing only pass/fail still leaves 57-72% overfit among refined samples. "Probe to Generate" mutation-guided augmentation of SWE-bench tests (https://arxiv.org/abs/2604.01518): 1,014 added tests over 211 instances; top-10 agents lose 4.2-9.0 points resolved rate. Meta's mutation-guided test generation (https://arxiv.org/abs/2501.12862).

### OSS pick
cosmic-ray (sixty-north/cosmic-ray, MIT, 658, 2026-08). Reason: works on native Windows, has a git-diff line filter out of the box, sqlite session is resumable. mutmut is faster but fork-only.

Integration plan:
1. `athena mutate --changed` = `cosmic-ray init` on the worktree, `cr-filter-git --branch main`, then `cosmic-ray exec` with `--distributor local` and N workers = free cores.
2. Glue (~120 LOC): map surviving mutants' (file,line) through the clause-to-lines map -> per-clause score; write into the verdict.
3. Refinery gate: per-clause score on *owned* lines >= threshold (start 0.7) and no survivor on lines added in this task; whole-module score only advisory.
4. Hidden tier: keep `scenarios_sealed/` outside the packet; relay denies reads of that path; refinery runs it after public specs go green.

### (b) Reusable vs build
Reusable: cosmic-ray whole pipeline, its filters. Build: clause aggregation, threshold policy, sealed-tier path policy in relay, cache of "mutant already killed by test T" keyed by (file hash, mutant id) to skip re-runs.

### (c) Smallest experiment
One module, 30 mutants on changed lines. Measure wall time (target < 3 min on 8 cores), per-clause score, and how many surviving mutants the Opus reviewer judges "real gap" vs equivalent. Then run 10 executor tasks with and without the gate; count post-merge regressions caught by sealed tests.

### (d) Pitfalls
Equivalent mutants inflate false reds; allow `# pragma: no mutate` only in commits from the reviewer role. Test-selection by coverage misses tests that exercise a line indirectly through mocks. cosmic-ray needs `timeout` multiplier for slow suites; infinite loops in mutants are the norm. Hidden tests still leak through error messages: strip the sealed run's output to pass/fail + test id in what the executor sees.

---

## Gap 4. Spec-authoring throughput with a small model

### (a) Existing work
- Otter / Otter++ (ICML 2025) - https://arxiv.org/abs/2502.05368 . Issue -> fail-to-pass tests: 31.4% single, 37.0% ensemble of 5, <$0.10/issue with GPT-4o; rule-based repair of generated tests.
- TDD-Bench-Verified - https://github.com/IBM/TDD-Bench-Verified - Apache-2.0, 35, 2026-07. 449 instances; admissibility = fails on old code, passes on new code, adequate coverage of the diff. Harness is reusable as the admissibility definition.
- SWE-smith - https://github.com/SWE-bench/SWE-smith - MIT, 787, 2026-09. Synthesizes bugs (LM-modify, procedural AST rewrites, PR mirroring, combining) and keeps only tasks that break >=1 test; 52k tasks. Directly matches "forge makes repair tasks by breaking owned lines".
- Heterogeneous prompting + execution feedback for issue test generation (https://arxiv.org/html/2508.06365).
- EARS + LLM: "Automated EARS-Based Requirements Generation with Lightweight LLMs" (ICTMOD 2025, IEEE); cross-task LLM RE evaluation (https://arxiv.org/html/2608.21531); Kiro's EARS requirements.md is the production example; Spec Kit issue #1356 asks for EARS.

### OSS pick
SWE-smith (SWE-bench/SWE-smith, MIT, 787, 2026-09) for the forge side; TDD-Bench-Verified harness semantics for admissibility. No maintained OSS drafts EARS from code; that stays a prompt (Opus) plus a syntactic validator we write.

Integration plan:
1. `athena forge` imports SWE-smith's procedural modifiers (`swesmith/bug_gen/procedural`) and applies them only to lines owned by a clause; keep tasks where the clause's specs go red (their fail-to-pass rule).
2. `athena draft-specs <clause>` asks the 9B model for pytest cases; glue admits a test only if it fails at HEAD~task and passes at HEAD (two `pytest -x <nodeid>` runs) and touches the clause's lines (coverage.py contexts).
3. EARS validator (~80 LOC regex/grammar: Ubiquitous/Event/State/Optional/Unwanted/Complex patterns) rejects malformed clause drafts before Opus review.
4. Log acceptance rate per model/prompt as a first-class metric.

### (b) Reusable vs build
Reusable: SWE-smith modifiers, TDD-Bench harness logic, EARS patterns. Build: fail-before/pass-after admission, clause-line coverage check, EARS validator, acceptance dashboard.

### (c) Smallest experiment
20 clauses from one module. 9B drafts 3 tests each. Measure: admitted % (fail-before, pass-after, covers owned lines), % accepted by Opus without edit, time per clause. Baseline from Otter suggests 30-40% admitted for issue-level; clause-level should be higher; set target 60%.

### (d) Pitfalls
Small models write tests that pass trivially (asserting the function returns something); admission must require red at HEAD~task. Tests that hard-code implementation details raise mutation score but block regeneration (Gap 1) - flag tests that import private names. EARS drafts often merge two responses into one clause; validator should require exactly one SHALL.

---

## Gap 5. Local orchestrator daemon

### (a) Existing work
- Beads - https://github.com/gastownhall/beads (steveyegge/beads redirects) - MIT, 27.4k, 2026-09. Issue graph in Dolt (embedded) with JSONL export; hash IDs; `bd ready` = no open blockers; `bd update <id> --claim` atomic assignee+in_progress; hooks; `AGENTS.md` generation.
- Gas Town - https://github.com/gastownhall/gastown - MIT, 18.2k, 2026-09. Roles: Mayor, Polecats (ephemeral workers), Refinery (Bors-style bisecting merge queue), Witness (stuck detection, nudges), Deacon (patrol), Dogs, Crew. Work state in git worktrees ("hooks") survives crashes; GUPP = no-progress detector. Go + tmux; Claude Code-centric.
- Ralph loops - https://github.com/frankbria/ralph-claude-code (MIT, 9.6k, 2026-09), https://github.com/snarktank/ralph (MIT, 21.9k, 2026-02). Fresh context per iteration, task list + progress file, exit detection.
- Claude Managed Agents - https://platform.claude.com/docs/en/managed-agents/overview . Session (event log outside the context), harness, sandbox as three decoupled primitives; sandbox treated as untrusted.
- OpenHands eval harness - https://github.com/All-Hands-AI/OpenHands/blob/main/evaluation/benchmarks/swe_bench/README.md . `run_infer.sh ... num_workers n_runs`, per-instance containers, resumable output JSONL.
- hermes-agent - https://github.com/NousResearch/hermes-agent - MIT, 248.9k, 2026-09. Cron + self-monitoring pattern (already in local memory notes).

### OSS pick
Beads (gastownhall/beads, MIT, 27.4k, 2026-09) as the ledger/ready-queue/lease; Gas Town's Refinery and Witness are the reference designs, not code to vendor (Go, tmux, Claude-specific).

Integration plan:
1. `athena daemon` loop: `bd ready --json` -> pick by priority -> `bd update --claim` -> dispatcher packs -> pi run in worktree -> refinery verdict -> `bd close` or `bd update --status blocked --notes <verdict id>`.
2. Lease = claim + heartbeat comment every N min; a Witness thread reopens claims with stale heartbeat (crash safety) and kills the worktree process group.
3. Retry/backoff: attempt counter in the bead; attempts 1-2 same model, 3 escalate (Gap 6), 4 -> `needs-human` label.
4. Idempotency: task id + packet hash as worktree name; on restart, an existing green worktree is re-verified, not re-run.
5. Merge serialisation: refinery is single-threaded, rebases and re-runs specs before merge (Bors semantics).

### (b) Reusable vs build
Reusable: bd CLI end to end. Build: ~300 LOC daemon, heartbeat/witness, backoff policy, packet-hash idempotency.

### (c) Smallest experiment
Queue 10 tasks, run 2 workers, kill -9 the daemon twice mid-run. Success: no task lost or run twice to completion, no orphaned worktrees, merges linear, all verdicts present.

### (d) Pitfalls
Dolt embedded DB + Windows file locking; test concurrent `bd` calls. Worktree reuse across attempts leaks partial edits - always start from a fresh worktree unless the attempt is a "repair" of a red one. Nudge storms: cap witness actions per task per hour.

---

## Gap 6. Escalation ladders / cascades

### (a) Existing work
- FrugalGPT - https://github.com/stanford-futuredata/FrugalGPT - Apache-2.0, 287, 2025-02. Cascade with learned scorer; cheap first, escalate under threshold.
- RouteLLM - https://github.com/lm-sys/RouteLLM - Apache-2.0, 5.5k, last push 2024-08 (stale). Prompt-only routers; out-of-distribution signal loss noted by later work.
- SWE-Router - https://arxiv.org/abs/2607.00053 . Let the cheap model run a few turns, then route on the partial trajectory; Bayes-optimality argument; trajectory dataset released.
- Scrouting / SuperScout - https://arxiv.org/abs/2608.04804 . 7B scout writes a ~4 KB handoff (implicated files, notes, verified repro test); router uses text embedding + scout hidden state. Key ablation: sending everything to the cheapest fixer *with the handoff* matched the router (159/266 at $0.227) - the handoff, not routing, carried the gain.
- Fail-Fast, Restart-Smart - https://arxiv.org/abs/2608.03222 . Failure predicted from trajectory prefix (length, redundant exploration, loops); 14.6-20.4% token savings at 5% FPR; restart with prior edits as optional context raised Qwen3.6-27B from 66.6% to 71.8%.
- Task-to-model optimisation for enterprise coding assistants (https://arxiv.org/pdf/2608.08528); routing/cascade survey (https://arxiv.org/pdf/2602.09902).

### OSS pick
None covers a local coding-agent cascade as a library; RouteLLM is stale and prompt-only. Build the ladder (small), reuse FrugalGPT's scorer idea and Fail-Fast's prefix features. This is justified "build": the logic is <200 LOC and depends on Athena's verdict schema.

Integration plan:
1. Ladder: 3B -> 9B -> Opus. Escalate on: red verdict twice, relay tool-call error rate > x, or Fail-Fast signals (turns > p90 for that clause size, repeated identical tool calls, no file write after k turns).
2. Pre-dispatch features logged per task: packet tokens, files owned, clause count, spec count, lines owned, prior attempts. After ~100 verdicts fit a logistic regression per lane (scikit-learn) and use it only to *skip* 3B when p(fail) > 0.8.
3. Adopt the Scrouting lesson: the cheap lane's output is a handoff (files, notes, repro) even when it fails; the escalated packet includes it.

### (b) Reusable vs build
Reusable: feature ideas and thresholds from the papers; sklearn. Build: ladder policy, feature logging, handoff format.

### (c) Smallest experiment
50 tasks, three arms: 9B only; 3B->9B cascade; 3B->9B with handoff. Measure resolved %, GPU-minutes per resolved task, escalation rate. Predictors: correlate packet tokens / files owned / spec count with 3B failure; report AUC.

### (d) Pitfalls
Prompt-only routers drift when the codebase changes; retrain from verdict log, not once. Early-abort false positives waste more than they save on short tasks - apply Fail-Fast only after the median turn count. A cascade multiplies cost when the small model nearly always fails; measure per clause type and disable the 3B rung where its win rate < 20%.

---

## Gap 7. Provenance for agent runs

### (a) Existing work
- in-toto attestation framework - https://github.com/in-toto/attestation - Apache-2.0, 375, 2026-09. Statement + predicate + DSSE envelope; Python bindings; SLSA provenance is one predicate type.
- SLSA v1.0 provenance predicate - https://slsa.dev/spec/v1.0/provenance . buildDefinition{buildType, externalParameters, internalParameters, resolvedDependencies}, runDetails{builder.id, metadata{invocationId, startedOn, finishedOn}, byproducts}.
- OpenSSF TAC proposal for an AI-authorship predicate `openfab/generation` - https://github.com/ossf/tac/issues/628 . Per-range human/AI attribution, model id, SHA-256 prompt fingerprint, acceptance contract (checks run), N-of-M sign-offs; draft v0.1, Apache-2.0 reference impl.
- W3C PROV-DM; PROV-AGENT (https://arxiv.org/abs/2508.02866) maps LLM calls and tool calls to prov:Activity with prov:used/prov:generated, agent as prov:Agent; implementation lineage in ORNL Flowcept (https://github.com/ORNL/flowcept, MIT, 37, 2026-08).
- OpenLineage - https://github.com/OpenLineage/OpenLineage - Apache-2.0, 2.7k, 2026-09. Run/Job/Dataset events with facets; Python client. MLflow - Apache-2.0, 28.1k, 2026-09 - run params/artefacts/traces.
- Survey: agent traces to trust (https://arxiv.org/html/2606.04990).

### OSS pick
in-toto/attestation (Apache-2.0) Python package for the envelope; SLSA v1 predicate as the shape; adopt `openfab/generation` fields where SLSA has none. OpenLineage/MLflow are heavier than needed for one box; keep as optional exporters.

Integration plan:
1. Verdict record = in-toto Statement, subject = merged blob/tree digests, predicateType = `athena/verdict/v1` (SLSA-shaped).
2. Fields: externalParameters{task id, packet sha256, clause ids, prompt template sha256}; internalParameters{model id + weights sha256 or HF revision, runtime (vLLM 0.21 / llama.cpp build), sampling (temperature, top_p, seed, max_tokens), tool set hash, relay version, sandbox mode}; resolvedDependencies{base commit, lockfile digest}; byproducts{pi transcript sha256, test log sha256, mutation report sha256}; metadata{invocationId, startedOn, finishedOn}; plus openfab-style per-range authorship and human sign-off list.
3. Sign with a local key (DSSE) only for merged verdicts; store `.athena/verdicts/<id>.json` in git alongside the merge commit.
4. Optional exporter to MLflow for charts.

### (b) Reusable vs build
Reusable: in-toto Statement/DSSE libs, SLSA field vocabulary. Build: predicate schema, collectors in dispatcher/relay/refinery, digest computation for local model weights.

### (c) Smallest experiment
Replay: given only the verdict record, re-run one task with the same model, seed, packet, and check identical patch hash (vLLM with temperature 0 and fixed seed; llama.cpp with `--seed`). Report reproducibility rate over 20 tasks; record which fields were missing when replay diverged.

### (d) Pitfalls
Bitwise reproducibility on GPUs is not guaranteed (batching, kernels); record it as "replayable to same verdict", not same tokens. Prompt hash must cover the *rendered* packet, including repo-map and lessons. Model "name" is not identity - hash weights or pin HF revision + quant config.

---

## Gap 8. Capacity-aware scheduling for local lanes

### (a) Existing work
- vLLM metrics - https://docs.vllm.ai/en/latest/design/metrics.html . `vllm:num_requests_running`, `vllm:num_requests_waiting`, `vllm:kv_cache_usage_perc`, `vllm:prefix_cache_queries/hits`, `vllm:request_queue_time_seconds`, `vllm:time_to_first_token_seconds`; swapped/cpu-cache metrics deprecated in v1.
- llama.cpp server - https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md . `GET /slots` (per-slot busy state), `GET /metrics` (`llamacpp:requests_deferred`, `n_busy_slots_per_decode`).
- llama-swap - https://github.com/mostlygeek/llama-swap - MIT, 5.8k, 2026-09. Per-model `concurrencyLimit`, `ttl`, `unloadTimeout`, groups (config.example.yaml at repo root); `/running`, `/api/models/unload`, `/metrics`. Already in front of the lanes here.
- LiteLLM router - https://docs.litellm.ai/docs/routing . Per-deployment `rpm/tpm/max_parallel_requests`, `least-busy`, `usage-based-routing-v2`, cooldown (`allowed_fails`), `order` for fallback. MIT core, 59.6k, 2026-09.
- SGLang router - https://pypi.org/project/sglang-router/ , Apache-2.0. Cache-aware prefix-tree routing across workers (SGLang backends). vLLM production-stack router (Apache-2.0, 2.6k, 2026-09): roundrobin/session/prefix-aware(WIP), static backends without k8s.

### OSS pick
llama-swap (already deployed) + LiteLLM router semantics; add a ~150 LOC client-side admission controller that reads vLLM `/metrics` and llama.cpp `/slots`. No standalone OSS does "prefix-aware admission for two heterogeneous local lanes"; SGLang router assumes SGLang workers.

Integration plan:
1. `athena lanes` polls `/metrics` every 2 s; lane state = (running, waiting, kv_usage, prefix_hit_rate).
2. Dispatcher admits a task to a lane only if `waiting == 0` and `kv_usage < 0.85` and running < concurrencyLimit-1 (KV headroom rule already learned locally); otherwise it parks the task (stays claimed in beads with `waiting-lane`).
3. Prefix affinity: hash the packet's static prefix (system + contract.md); route tasks with equal prefix to the same lane while it is warm, to keep vLLM prefix-cache hits high.
4. Expose LiteLLM-style `rpm`/`max_parallel_requests` per lane in athena config; cooldown a lane after 2 consecutive 5xx.

### (b) Reusable vs build
Reusable: metrics endpoints, llama-swap limits, prometheus_client parser. Build: admission rule, prefix affinity, park/resume in daemon.

### (c) Smallest experiment
Submit 12 packets (6 share a prefix) against the 9B lane with `--max-num-seqs 4`. Compare naive fan-out vs admission+affinity: p95 TTFT, preemptions (queue-time histogram), prefix hit ratio, total wall time. Target: no KV overflow crash, hit ratio > 0.6 for shared-prefix tasks.

### (d) Pitfalls
`kv_cache_usage_perc` lags; sample twice before admitting. Prefix caching breaks when lessons/repo-map are placed before contract.md; keep the variable part last. llama-swap swapping a model to serve another lane invalidates warm caches - pin groups as persistent for the run.

---

## Gap 9. Sandboxing a local coding agent on native Windows

### (a) Existing work
- Anthropic sandbox-runtime - https://github.com/anthropics/sandbox-runtime - Apache-2.0, 5.3k, 2026-09. **Windows alpha**: runs the child as a dedicated local user `srt-sandbox` (CreateProcessWithLogonW, then restricted token in a job object), WFP egress fence keyed on that SID (allow loopback proxy range 60080-60089 only), NTFS explicit ACEs for allowRead/allowWrite/deny paths, `npx @anthropic-ai/sandbox-runtime windows-install` one-time elevated. Known gaps: schannel CRL fetch blocked, per-user tool installs unreachable, DNS not fenced, proxy token visible in argv.
- OpenAI Codex CLI Windows sandbox - https://openai.com/index/building-codex-windows-sandbox/ , docs https://learn.chatgpt.com/docs/windows/windows-sandbox , code `codex-rs/windows-sandbox-rs` (Apache-2.0, in https://github.com/openai/codex , 126k, 2026-09). Rejected AppContainer (open-ended toolchains break); "elevated" mode = dedicated low-privilege users + ACLs + firewall rules; "unelevated" = restricted token from current user + ACLs + env-level offline. Rust modules: token.rs, wfp.rs, workspace_acl.rs, deny_read_*.rs, desktop.rs, conpty.
- fastrender windows_sandbox.md - https://github.com/wilsonzlin/fastrender/blob/main/docs/windows_sandbox.md . Job object (kill-on-close, active-process-limit, memory cap) + zero-capability AppContainer; fallback restricted token + Low IL; notes network is not blocked in fallback.
- MidBox - https://github.com/Meterel/MidBox - no license, 0 stars, 2026-01. Sandbox user + AppContainer + restricted token; PowerShell entry; loopback disabled. Not vendorable (no license).
- Sandboxie-Plus - https://github.com/sandboxie-plus/Sandboxie - GPL-3.0, 19.5k, 2026-09. Kernel driver; `Start.exe /box:Name /wait /silent cmd`, `/terminate`; copy-on-write filesystem view. GPL applies only if we ship it; invoking the installed binary is fine.
- Microsoft: CreateProcessInSandbox APIs (https://learn.microsoft.com/en-us/windows/win32/secauthz/createprocessinsandbox).

### OSS pick
anthropics/sandbox-runtime (Apache-2.0, Windows alpha) as the wrapper the relay uses for `run_cmd`; Codex's `windows-sandbox-rs` as the reference implementation if we need a Rust port later. Sandboxie-Plus as the fallback for a stronger filesystem view when the driver is acceptable.

Integration plan:
1. Relay executes every tool `run_cmd` via `srt` (sandbox-runtime CLI) with `filesystem.allowWrite=[worktree]`, `allowRead=[repo, Python install, toolchain]`, network default deny, loopback allow to the lane ports through the proxy allowlist.
2. One-time `windows-install` in the machine bootstrap script; verify at daemon start (`initialize()` fails loudly if fence missing).
3. Job-object memory/time caps come free; add an Athena-side wall clock kill.
4. Fallback path (no admin): Codex-style unelevated restricted token - implement only if sandbox-runtime install is refused.

### (b) Reusable vs build
Reusable: sandbox-runtime as-is (alpha), Sandboxie CLI. Build: relay glue, allowlist generation from the packet's owned files, install verification. Nothing needs a kernel driver of our own.

### (c) Smallest experiment
Inside the sandbox run a 9B task that (a) writes inside worktree, (b) tries to write `%USERPROFILE%`, (c) curls github.com, (d) POSTs to the local lane. Expect a/d pass, b/c blocked; measure added latency per command (<300 ms target) and pytest slowdown.

### (d) Pitfalls
Per-user toolchains (Scoop, `pip --user`, nvm) invisible to `srt-sandbox` - install Python/uv machine-wide or grant read on those paths. The machine already has a default-deny outbound firewall (local notes): WFP rule ordering may conflict; test explicitly. AppContainer is a dead end for a shell-driving agent (both OpenAI and Anthropic avoided it). Restricted token alone does not block sockets.

---

## Gap 10. Project memory for agents

### (a) Existing work
- aider repo map - https://aider.chat/docs/repomap.html , code `aider/repomap.py` (~27 KB) in https://github.com/Aider-AI/aider - Apache-2.0, 49.2k, 2026-05. tree-sitter tags -> file dependency graph -> personalised PageRank -> signature map under `--map-tokens` (default 1k).
- HumanLayer 12-factor agents, Factor 3 "own your context window" - https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md - Apache-2.0, 26.4k, 2025-09. Custom serialisation, keep prompt in the first 40% of the window.
- Letta (MemGPT) - https://github.com/letta-ai/letta - Apache-2.0, 24.9k, 2026-09. Core memory blocks + recall + archival. mem0 - https://github.com/mem0ai/mem0 - Apache-2.0, 66k, 2026-09. Fact extraction to vector store.
- SWE-Exp - https://arxiv.org/abs/2507.23361 , code https://github.com/cslsolow/SWE-Exp (Apache-2.0, 46, 2025-10). Experience bank of successful and failed repairs at several granularities; 73.0% pass@1 on SWE-bench Verified with Claude 4 Sonnet.
- DreamBench-SWE - https://arxiv.org/abs/2608.20664 . Multi-session memory hygiene; no memory 11.7%, verbatim event log 45.6%, one mem0 config 53.9%; authors explicitly do not claim superiority of any memory system.
- ExpeL, Reflexion, Agent Workflow Memory (procedural lesson extraction); MemHarness (https://arxiv.org/abs/2607.28272) reconstructs rather than replays memories (not SWE-evaluated).

### OSS pick
Vendor `aider/repomap.py` (Apache-2.0) for structural context; a plain lessons JSONL for episodic memory. Letta/mem0 are conversation-memory servers and did not show a robust SWE gain in DreamBench-SWE; do not add a vector DB for this.

Integration plan:
1. `athena pack` calls a trimmed repomap (tree-sitter-languages + networkx, ~600 LOC vendored) seeded with the task's owned files and clause identifiers; budget 800-1500 tokens; placed *after* the static prefix (Gap 8 caching).
2. Lessons: refinery appends one record per red verdict: {clause id, file, failure class, one-line rule, verdict id}. Packing selects lessons by exact clause id and file path match only (no embeddings), max 5, max 60 tokens each.
3. Failed-attempt handoff (Gap 6) is a separate, task-scoped memory - the diff and last test output of the previous attempt, truncated to 2 KB.
4. Lesson decay: drop a lesson after 10 packets in which it was included and the verdict was green.

### (b) Reusable vs build
Reusable: repomap.py, tree-sitter grammars. Build: lesson schema, selector, decay, and a size guard.

### (c) Smallest experiment
30 tasks x 3 arms with the 9B model: no map; map only; map + lessons. Fixed packet budget. Measure resolved %, packet tokens, first-attempt green rate. Secondary: whether lessons from failures of the same clause reduce repeat failures (count same failure class recurring).

### (d) Pitfalls
Memory bloat kills small models faster than it helps; enforce a hard token cap and log packet size in the verdict. Verbatim past patches induce copy-paste of stale code; store rules, not diffs, except in the task-scoped handoff. Repo maps on Windows paths: normalise separators before hashing for cache keys.

---

## Suggested order of work by leverage

1. Gap 3 + Gap 4 first: cosmic-ray on changed lines with per-clause scores, and fail-before/pass-after admission for 9B-drafted tests. They make every later green verdict trustworthy and feed the forge with SWE-smith style tasks.
2. Gap 5 (beads-backed daemon with leases, witness, single-threaded refinery) - turns the pipeline into a machine that runs unattended; small code, big throughput gain.
3. Gap 8 + Gap 10 together: admission control and prefix affinity plus a capped repo map and lessons - they set the packet shape, and cache hit rate depends on it.
4. Gap 6 + Gap 7: ladder with logged features and in-toto verdict records - both need the verdict log from steps 1-3; provenance fields should be fixed before the log grows.
5. Gap 1, Gap 2, Gap 9 last: regeneration gates (CrossHair) and arch/perf oracles are valuable but depend on mature specs; sandbox-runtime Windows is alpha, so wire it behind a flag and test as it stabilises.

## What Athena already has that covers part of each gap

(Only from the task description.)
1. Regeneration: EARS clauses + executable red specs are already the source of truth; the mutation layer gives one of the two equivalence signals. Missing: signature-only regen packet and diffbehavior.
2. Second-kind oracles: clauses carry a run_cmd, so arch/perf/golden checks can be clauses today; missing are the config renderers and baselines.
3. Mutation gate: a mutation layer and clause-to-lines map exist; missing are changed-lines filtering, per-clause thresholds in the refinery, and a sealed tier.
4. Spec authoring: the forge already breaks owned lines to create repair tasks (SWE-smith's fail-to-pass idea); missing is admission of model-drafted tests and an EARS validator.
5. Daemon: dispatcher, relay, refinery (merges only green worktrees) are the worker and merge halves; missing is the ready-queue/lease/retry loop around them.
6. Ladder: two local lanes and a frontier reviewer already form an implicit ladder; missing are logged features and thresholds.
7. Provenance: verdicts exist as a concept in the refinery; missing is a fixed schema and signing.
8. Scheduling: lanes sit behind llama-swap/LiteLLM per local notes; missing is metric-driven admission.
9. Sandbox: the relay normalises tool calls, which is the right choke point to wrap commands; no OS-level isolation yet.
10. Memory: the clause-to-lines map is already a precise, non-embedding index for selecting lessons by clause and file.
