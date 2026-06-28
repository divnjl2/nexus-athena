# SWE-bench-Lite eval — real intent → plan, with a ground-truth answer key

Repurposes [SWE-bench-Lite](https://www.swebench.com/) (300 real GitHub issues across 12
Python repos) to measure **plan quality on real intents** — the best fit for L3
execution-closure, since each issue ships a gold patch + the tests that must pass.

## The mapping

| SWE-bench field | Role in the eval |
|---|---|
| `problem_statement` | the NL **intent** fed to the Athena frame |
| `FAIL_TO_PASS` | **answer key (primary):** the behaviours the fix must satisfy |
| `patch` (gold) | **answer key (secondary):** the files/symbols actually changed |
| `hints_text` | optional maintainer context |

## What it measures

- **behaviour_coverage (PRIMARY, LLM judge):** of the `FAIL_TO_PASS` tests, what fraction
  assert a behaviour that some plan scenario / edge-case covers. This is the *fair* metric —
  the frame sees only the issue text, not the repo, so it is judged on whether it anticipated
  the right behaviours, not on guessing repo paths.
- **file_recall (SECONDARY, deterministic):** basename overlap between the plan's task
  `files:` and the gold patch's changed files. Informational unless the frame is given repo
  context. Computed by `score.file_recall` (no LLM).

## Layout

```
evals/swebench/
├── loader.py     # HF streaming (princeton-nlp/SWE-bench_Lite) + offline fixture fallback
├── score.py      # DETERMINISTIC: gold_patch_targets / fail_to_pass / file_recall  (unit-tested)
├── run.py        # EXPENSIVE driver: frame plan via `claude -p` per instance + scoring
├── fixtures/     # 2 committed instances for offline tests (no network)
└── README.md
```
Deterministic core is covered by `tests/test_swebench_score.py` (offline, no LLM).

## Running

```bash
# offline smoke (no network, no LLM)
python -m evals.swebench.loader 2 --offline

# REAL run — EXPENSIVE: one full `claude -p` frame session per instance (~$2-3, ~10 min each)
python -m evals.swebench.run 5            # 5 instances, document order
python -m evals.swebench.run 5 --offline  # against the 2 fixtures only
```

## Cost & caveats

- Each instance = a full headless frame session (~$2-3, ~10 min). Cap `n`; 20 instances ≈ $50.
- `behaviour_coverage` needs the LLM judge (mapping `FAIL_TO_PASS` → covered-by-scenario);
  `run.py` returns the deterministic signals now and marks the judge as a held step.
- HF download goes through the host firewall; `loader` falls back to the committed fixtures
  when `huggingface.co` is unreachable.
