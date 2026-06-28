# Athena plan-quality evals

The unit + real-bd integration tests prove the **machinery** (graph compiles, edges
materialize, idempotent). They say nothing about whether the **plans Athena generates
are good**. Plan quality is the output of non-deterministic LLM hops — it needs an
eval harness, not a golden assertion.

## The pyramid (cheap → honest)

| Level | What it checks | Authoritative? | Cost |
|---|---|---|---|
| **L0 structural** | plan compiles: scenarios resolve, no cycles, success_check present, derived-from chain intact | yes (deterministic) | free |
| **L1 metrics** | requirement recall (spec vs ground-truth), scenario coverage, dropped task→scenario links | yes (keyword match vs answer key) | free |
| **L2 judge panel** | adversarial LLM judges (completeness / feasibility / find-a-hole), advisory only | no (advisory) | medium |
| **L3 execution closure** | code built to the plan passes an independent **ground-truth gate**; iters-to-green | **yes (deterministic gate)** | high (live executor) |

**Honesty rule (load-bearing):** the L3 gate (`corpus/<task>/gate_test.py`) is an answer
key the planner never sees. Plan quality is judged by whether code built to the plan
passes *that*, NOT by the LLM's own scenarios (recorded for self-consistency only).
Executor self-report is worthless; the deterministic gate is authoritative.

## Layout

```
evals/
├── llm.py                       # reasoning-aware OpenAI client (planner@8000, worker@8001)
├── run_l3.py                    # orchestrator: intent → spec → scenarios → tasks → compile → execute → gate
├── corpus/<task>/
│   ├── intent.md                # the ONLY input the planner sees
│   ├── expected.yaml            # ground-truth requirements + distinctive keywords (answer key)
│   └── gate_test.py             # authoritative ground-truth pytest (planner-blind)
└── results/<task>-<run_id>.json # per-run metrics + raw spec/scenarios/tasks (versioned)
```

Run: `python evals/run_l3.py 01_rpn` (needs live vLLM lanes :8000 / :8001).

## First run finding (01_rpn) — why the pyramid needs all levels

On the RPN-calculator task the planner (qwen35-a3b) produced a **shallow spec**: it
captured surface mechanics (signature, naming, file location) but missed the
substantive behaviour — division-by-zero, malformed input, float division, chaining.

- **L1 recall = 40%** (missed R3 div-by-zero, R4 malformed, R5 chaining)
- **L1 scenario coverage = 20%** (scenarios are example-driven; they don't exercise the edge cases)
- **L3 gate = PASS @ iter 1**

The gate passed *anyway* because a correct RPN evaluator naturally handles those cases
(Python `/` raises on zero, popping an empty stack raises, a stack handles chaining).
**Lesson: execution-closure alone can MASK plan gaps on "naturally robust" tasks** —
L1 recall is what surfaces under-specification. Treat L3 PASS + low L1 as
"code works, plan under-specified", not "plan is good".

## Known limitations (do not over-trust)

- **L1 coverage is conservative**: keyword match over scenario text under-counts when
  scenarios use concrete examples (`"3 4 +"`) instead of requirement vocabulary
  (`"operator"`). It under-claims, never over-claims — safe direction.
- **L2 judge panel not yet wired** — the design slot exists; add when needed.
- **Single corpus task** — add tasks with genuinely separable files/functions to
  exercise multi-task decomposition (RPN is one function, so task-decomposition is light).
- Metrics depend on `expected.yaml` keyword quality; keep keywords distinctive per
  requirement (no generic words shared across requirements).
