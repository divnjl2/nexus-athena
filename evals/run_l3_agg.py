"""Aggregate N L3 runs of one task — a single run of a non-deterministic planner is noise.

The planner (reasoning MoE) varies run-to-run even at temperature 0, so plan-quality
metrics must be reported as a distribution, not a point. This runs the same task N times
and prints mean/min/max for recall, coverage, gate pass-rate, and structured-output drift.

Usage: python evals/run_l3_agg.py 01_rpn 5
"""
from __future__ import annotations

import os
import statistics
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evals.run_l3 import main  # noqa: E402


def agg(task_id: str, n: int):
    runs = []
    for i in range(n):
        print(f"\n----- run {i + 1}/{n} -----")
        try:
            runs.append(main(task_id))
        except Exception as e:  # noqa: BLE001 — one bad run must not sink the batch
            print(f"  run {i + 1} errored: {e}")
            traceback.print_exc()
    if not runs:
        print("no successful runs")
        return

    def col(key):
        return [r[key] for r in runs]

    recalls = col("L1_requirement_recall")
    covs = col("L1_scenario_coverage")
    gates = [1 if r["L3_gate_pass"] else 0 for r in runs]
    reqs = col("spec_requirements")
    coerced = col("L0_coerced_items")

    print(f"\n===== AGGREGATE over {len(runs)} runs (task={task_id}) =====")
    print(f"spec_requirements : min={min(reqs)} max={max(reqs)} mean={statistics.mean(reqs):.1f}"
          f"   <- planner output-size instability")
    print(f"L1 recall         : min={min(recalls):.0%} max={max(recalls):.0%} "
          f"mean={statistics.mean(recalls):.0%}")
    print(f"L1 coverage       : min={min(covs):.0%} max={max(covs):.0%} "
          f"mean={statistics.mean(covs):.0%}")
    print(f"L3 gate pass-rate : {sum(gates)}/{len(runs)} = {statistics.mean(gates):.0%}")
    print(f"coerced items     : total={sum(coerced)} (structured-output drift)")
    print("\nReading: high gate pass-rate + low/variable recall = the plan under-specifies, "
          "but the task is naturally robust so execution masks it. The planner hop is the "
          "weak, unstable link — not the machinery.")


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "01_rpn"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    agg(task, n)
