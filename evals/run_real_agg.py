"""Real-pipeline eval over a TASK SET — the trusted measurement of Athena plan quality.

For each corpus task, runs the REAL Spec-Kit+CRISP pipeline N times via a headless Claude
Code agent (evals.real_pipeline, the canonical executor — dog-foods the Claude Code plugin),
scores requirement recall against the task's ground-truth expected.yaml, and reports a
per-task + overall distribution. Runs are answer-key-isolated (the agent never sees the gate).

Bounded concurrency: each agent run is ~9 min, so we fan out (default 4 workers) to keep
wall-clock ~30 min for 15 runs instead of ~2 h sequential.

Usage: python evals/run_real_agg.py [runs_per_task] [workers]
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evals.real_pipeline import run_real_pipeline           # noqa: E402
from evals.run_l3 import recall, _coverage_against          # noqa: E402

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
TASKS = ["01_rpn", "02_wildcard_match", "03_roman", "04_balanced", "05_semver"]


def _one(task: str, run_idx: int, stamp: int) -> dict:
    task_dir = os.path.join(CORPUS, task)
    intent = open(os.path.join(task_dir, "intent.md"), encoding="utf-8").read()
    exp = yaml.safe_load(open(os.path.join(task_dir, "expected.yaml"), encoding="utf-8"))["requirements"]
    ws = rf"D:/tmp/claude/realeval/{task}_{run_idx}_{stamp}"
    t0 = time.time()
    try:
        out = run_real_pipeline(intent, ws, timeout=1500)
    except Exception as e:  # noqa: BLE001 — one bad agent run must not sink the batch
        return {"task": task, "run": run_idx, "ok": False, "error": str(e)[:200],
                "trace": traceback.format_exc()[-400:]}
    frs = out.get("functional_requirements", [])
    rec, rmiss = recall(frs, exp)
    # coverage proxy: ground-truth reqs whose keywords appear in the FR + edge-case texts
    texts = [r.get("text", "") for r in frs] + [str(e) for e in out.get("edge_cases", [])]
    cov, cmiss = _coverage_against(texts, exp)
    return {"task": task, "run": run_idx, "ok": True, "n_frs": len(frs),
            "n_edges": len(out.get("edge_cases", [])), "recall": round(rec, 3),
            "recall_missed": rmiss, "coverage": round(cov, 3), "elapsed_s": round(time.time() - t0)}


def main(runs: int, workers: int, stamp: int):
    jobs = [(t, r) for t in TASKS for r in range(1, runs + 1)]
    print(f"=== REAL-pipeline eval: {len(TASKS)} tasks x {runs} runs = {len(jobs)} agent runs, "
          f"{workers} concurrent ===")
    results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, t, r, stamp): (t, r) for t, r in jobs}
        for fut in as_completed(futs):
            res = fut.result()
            results.append(res)
            if res["ok"]:
                print(f"  [{res['task']} #{res['run']}] recall={res['recall']:.0%} "
                      f"cov={res['coverage']:.0%} frs={res['n_frs']} ({res['elapsed_s']}s)")
            else:
                print(f"  [{res['task']} #{res['run']}] ERROR: {res['error']}")

    print("\n===== PER-TASK =====")
    per_task = {}
    for t in TASKS:
        recs = [r["recall"] for r in results if r["task"] == t and r["ok"]]
        if recs:
            per_task[t] = {"recall_min": min(recs), "recall_max": max(recs),
                           "recall_mean": round(statistics.mean(recs), 3), "n": len(recs)}
            print(f"  {t:18} recall min={min(recs):.0%} max={max(recs):.0%} "
                  f"mean={statistics.mean(recs):.0%}  (n={len(recs)})")
        else:
            per_task[t] = {"error": "all runs failed"}
            print(f"  {t:18} ALL RUNS FAILED")

    ok = [r for r in results if r["ok"]]
    overall = round(statistics.mean([r["recall"] for r in ok]), 3) if ok else None
    print(f"\n===== OVERALL: mean recall = {overall:.0%} over {len(ok)}/{len(jobs)} successful runs ====="
          if overall is not None else "\n===== OVERALL: no successful runs =====")

    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, f"real_agg-{stamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"tasks": TASKS, "runs_per_task": runs, "overall_mean_recall": overall,
                   "per_task": per_task, "runs": results}, f, indent=2)
    print(f"=== result -> {out_path} ===")


if __name__ == "__main__":
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    # stamp passed via env to keep deterministic dirs across a resume; else time-based
    stamp = int(os.environ.get("EVAL_STAMP", str(int(time.time()))))
    main(runs, workers, stamp)
