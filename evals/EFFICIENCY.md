# Efficiency — what the approach saves vs. a no-plan baseline

A grounded, honest estimate. **Measured** numbers come from this repo's evals (the N=100
SWE-bench-Lite run, `swebench/showcase_100/`); **theory** rows are reasoned from the
cost-of-change literature + our measured plan completeness. Two levers are kept separate
because they are easy to conflate.

## Summary

| What | vs base (no-plan agent / Claude) | status |
|---|---|---|
| End-to-end time / task (non-trivial) | **−25…40%** | theory (cost-of-change + our spec completeness) |
| Cost / task | **−~100%** (API → 0) | conditional — single-shot impl parity NOT met (0.10 proxy); needs a cluster coding-agent loop (see caveats) |
| Throughput on the corpus | **~2.3×** | **measured** (60% of headless Claude runs were Usage-Policy-blocked; local recovered them) |
| Back-end code↔spec audit | a query (`trace_proof`) instead of a manual review | architectural (v4) |

## Lever A — rework reduction (the main time saver)

Not from the model — from putting a complete spec + edge cases + an executable
`success_check` **before** the code.

- Cost-of-change curve (Boehm / IBM): a missed requirement caught at the spec stage ≈ 1×,
  at review ≈ 5×, in tests ≈ 10×, in prod ≈ 30–100×. The frame moves edge-case discovery to
  the spec stage.
- Our data: the "snake" intent (4 sentences) expanded to **24 edge cases / 44 FRs / 31
  scenarios**, including the non-obvious ones (legal tail-chase, within-tick reversal) — the
  exact cases a no-plan agent discovers *during debugging*, each one a code→test→fix loop.
- **Estimate: −25…40% end-to-end on non-trivial tasks; ~0 on trivial ones** (`add(a,b)` has
  nothing to save). Savings scale with edge-case density.

## Lever B — local model at parity (throughput + cost)

This one has **measured** numbers from the N=100 run:

- **Cost:** ~$2.65/task on Claude → ~$0 on the local GPU lane. 100 tasks ≈ $265 → ~$0.
- **Throughput (measured):** headless Claude hit a **60% Usage-Policy false-positive block
  rate** → only 39/100 produced a plan. The local lane recovered the set to 90/100 — **~2.3×
  effective throughput** on identical work from dodging the filter alone, plus no API
  rate-limit so parallelism is bounded only by GPU.

## What this does NOT save / risks in the estimate

- **Trivial tasks**: the frame's spec stages are pure overhead — a net negative.
- **Implementation parity does NOT hold for a single completion (MEASURED).** Planning parity
  holds (local behaviour_coverage **0.935** vs Claude **0.940**), but a *cluster-only,
  single-shot* implementer (the 9B worker lane writes one diff; `evals/swebench/parity.py`,
  `--driver` cluster-only, no Anthropic) scored **0.100 mean proxy over 10 issues** — file
  pick hit the gold file 3/10, full file+hunk match 1/10. Two failure modes: a completion
  can't *explore* the repo to find the file (7/10 wrong file), and a one-shot diff rarely
  lands on the right lines. This is a **floor**, not a ceiling: it shows *one completion ≠ an
  agent loop*, not that local models can't implement. A fair test needs a cluster CODING AGENT
  (opencode/aider on the local lane) that greps the repo and iterates against the test gate —
  that is the next build, and the real `FAIL_TO_PASS` gate needs Docker (down on this box).
  **Net: Lever B's cost win is real only if a proper cluster agent closes this gap; single-shot
  does not.**
- **Planning itself costs** ~$2.65/task on Claude — but ~$0 on local, and a plan is reused
  (one spec → many tasks).

## One line

On real non-trivial tasks: roughly **−⅓ time** from the front-loaded spec, **~2.3× throughput**
and **~$0 cost** from the local lane — the last conditional on confirming the local model
implements (not just plans) at parity, which is worth measuring the same way we measured
planning.
