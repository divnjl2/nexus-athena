# SWE-bench-Lite N=100 — committed run snapshot

100 real GitHub issues from [SWE-bench-Lite](https://www.swebench.com/) driven through the
Athena frame (intent → plan), one JSON per instance. This is the durable evidence behind
[`../RESULTS_100.json`](../RESULTS_100.json) — every number below is recomputable from these
files. Per-instance scratch outputs normally live in the gitignored `../results/`; this is a
frozen snapshot.

## Headline (90/100 plans produced)

| Driver | plans | file_recall | behaviour_coverage | perfect@1.0 |
|---|---|---|---|---|
| **claude** (agent pipeline) | 39 | **1.000** | **0.940** | 35/39 |
| **local** (qwen35-a3b, 1-shot recovery) | 51 | 0.863 | 0.935 | 45/51 |
| **all** | **90** | **0.922** | **0.937** | 80/90 |

- **file_recall** — does a plan task name the gold patch's changed file (basename)? Deterministic.
- **behaviour_coverage** — of the issue's `FAIL_TO_PASS` tests, what fraction does a plan
  scenario / edge-case cover? Judged on the local lane (see below).

## What each JSON holds

```
instance_id, driver ("claude"|"local"), parse_ok,
n_edge_cases, n_scenarios,            # plan size
plan: {edge_cases, scenarios, plan_files},
fail_to_pass, gold_targets,           # the answer key
file_recall: {gold_files, matched, recall},
behaviour_coverage: {per_test:[{test,covered,why}], covered, total, ratio},
raw_tail                              # last 1200 chars of the driver output (diagnosability)
```

## Honest caveats (read these)

- **~60% of headless `claude -p` runs hit an Anthropic Usage-Policy false-positive** on benign
  issues — the agent never ran the frame. You can see this verbatim in the `raw_tail` of the
  `driver:"claude"` instances that have no plan. The local lane (`driver:"local"`) was used to
  recover those; `claude` and `local` numbers are reported separately, never blended.
- **local is single-shot, not the agentic pipeline** — hence its lower file_recall (0.863).
- **10/100 unrecovered** — the local 35B exhausted its reasoning budget or emitted malformed
  JSON on the hardest django issues (see their `raw_tail`).

## Two harness bugs caught mid-run (and fixed)

Both were "the harness lied" — corrected by evidence, not guesswork:
1. The empty plans looked like a JSON-parser drop; the `raw_tail` field (added mid-run) proved
   they were Usage-Policy blocks — the frame never ran.
2. behaviour_coverage first read **0.122**; that was a name-matching bug (full pytest node-id
   vs the judge's short function name) zeroing real coverage. Counting the judge's
   `covered==true` verdicts directly gives the real **0.937**. Locked by `tests/test_swebench_judge.py`.

## Reproduce

```bash
python -m evals.swebench.run 100 --resume --workers=4               # claude agent pass
python -m evals.swebench.run 100 --driver=local --workers=2         # local gap-fill (filter-free)
python -m evals.swebench.judge 100 --resume --workers=2             # behaviour_coverage (local lane)
```
