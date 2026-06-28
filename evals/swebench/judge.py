"""behaviour_coverage judge — the PRIMARY SWE-bench-Lite metric (cheap second pass).

Reads the plans saved by run.py (results/<id>.json), re-loads each instance by id (for the
problem_statement + FAIL_TO_PASS), and asks an LLM, per FAIL_TO_PASS test, whether some plan
scenario / edge-case plausibly covers the behaviour that test checks. Cheap relative to the
frame run (one small judge call per instance). Self-contained: does NOT depend on run.py's
in-memory state, so it can run any time after the plans land.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

from evals.swebench.loader import load_instances
from evals.swebench.score import fail_to_pass

CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _prompt(problem_statement: str, f2p: list[str], plan: dict) -> str:
    scen = "\n".join(f"- {s.get('id','?')}: {s.get('covers','')}" for s in plan.get("scenarios", []))
    edges = "\n".join(f"- {e}" for e in plan.get("edge_cases", []))
    tests = "\n".join(f"- {t}" for t in f2p)
    return f"""You are grading whether a PLAN anticipated the behaviours a bug fix must satisfy.

## Issue
{problem_statement[:1500]}

## The required tests (FAIL_TO_PASS — each asserts a behaviour the fix must produce)
{tests}

## The plan's scenarios (id: behaviour it covers)
{scen or "(none)"}

## The plan's edge cases
{edges or "(none)"}

For EACH required test, decide if ANY plan scenario or edge-case plausibly covers the
behaviour that test checks (infer the behaviour from the test name + the issue). Output ONLY
this JSON:
{{"per_test":[{{"test":"<name>","covered":true,"why":"<short>"}}]}}"""


def _parse_judgement(text: str, f2p: list[str]) -> dict:
    """Pure: extract the per_test verdicts, coerce to a coverage ratio. Testable offline."""
    text = re.sub(r"```(?:json)?|```", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    per = []
    if m:
        try:
            per = json.loads(m.group(0)).get("per_test", [])
        except json.JSONDecodeError:
            per = []
    covered_names = {p.get("test") for p in per if p.get("covered") is True}
    # count by membership in the real f2p list (judge may paraphrase names)
    hit = sum(1 for t in f2p if any(t == p.get("test") or t in str(p.get("test", "")) for p in per
                                    if p.get("covered") is True)) if per else 0
    total = len(f2p)
    return {
        "per_test": per,
        "covered": hit,
        "total": total,
        "ratio": (hit / total) if total else 0.0,
    }


def judge_one(instance: dict, plan: dict, *, timeout: int = 300) -> dict:
    f2p = fail_to_pass(instance)
    proc = subprocess.run(
        [CLAUDE, "-p", _prompt(instance["problem_statement"], f2p, plan),
         "--output-format", "json", "--dangerously-skip-permissions"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    try:
        env = json.loads(proc.stdout or "")
        text = env.get("result", proc.stdout) if isinstance(env, dict) else proc.stdout
    except json.JSONDecodeError:
        text = proc.stdout or ""
    return _parse_judgement(text, f2p)


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    offline = "--offline" in sys.argv
    by_id = {i["instance_id"]: i for i in load_instances(n, offline=offline)}
    ratios = []
    for iid, inst in by_id.items():
        rp = os.path.join(RESULTS_DIR, f"{iid}.json")
        if not os.path.exists(rp):
            print(f"[skip] {iid}: no saved plan"); continue
        saved = json.load(open(rp, encoding="utf-8"))
        if "error" in saved:
            print(f"[skip] {iid}: run errored"); continue
        try:
            v = judge_one(inst, saved.get("plan", {}))
        except Exception as e:
            print(f"[err]  {iid}: {type(e).__name__}"); continue
        saved["behaviour_coverage"] = v
        json.dump(saved, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        ratios.append(v["ratio"])
        print(f"[ok]   {iid}: behaviour_coverage={v['ratio']:.2f} ({v['covered']}/{v['total']})")
    if ratios:
        print(f"\nMEAN behaviour_coverage over {len(ratios)} instances: {sum(ratios)/len(ratios):.3f}")
