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

from evals.swebench.loader import load_instances
from evals.swebench.score import fail_to_pass

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
    """Judge via the LOCAL planner lane (qwen35-a3b). Using `claude -p` here would re-trigger
    the same Anthropic Usage-Policy false-positive on the very issues we recovered locally,
    so the judge runs on the same filter-free lane — and it's free."""
    f2p = fail_to_pass(instance)
    from evals.llm import chat, LLMError
    try:
        text, _ = chat(_prompt(instance["problem_statement"], f2p, plan),
                       lane="planner", max_tokens=4000, timeout=timeout, strict_finish=False)
    except LLMError:
        text = ""
    return _parse_judgement(text, f2p)


def _judge_saved(iid: str, inst: dict, *, resume: bool):
    rp = os.path.join(RESULTS_DIR, f"{iid}.json")
    if not os.path.exists(rp):
        return iid, None, "no saved plan"
    saved = json.load(open(rp, encoding="utf-8"))
    # tolerant of the pre-parse_ok schema: a real plan = no error AND (parse_ok or scenarios)
    has_plan = saved.get("parse_ok") or saved.get("n_scenarios", 0) > 0
    if "error" in saved or not has_plan:
        return iid, None, "no parseable plan"
    if resume and isinstance(saved.get("behaviour_coverage"), dict):
        return iid, saved["behaviour_coverage"]["ratio"], "cached"
    try:
        v = judge_one(inst, saved.get("plan", {}))
    except Exception as e:
        return iid, None, type(e).__name__
    saved["behaviour_coverage"] = v
    json.dump(saved, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return iid, v["ratio"], f"{v['covered']}/{v['total']}"


if __name__ == "__main__":
    import sys
    from concurrent.futures import ThreadPoolExecutor, as_completed

    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5
    offline = "--offline" in sys.argv
    resume = "--resume" in sys.argv
    workers = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--workers=")), "4"))
    by_id = {i["instance_id"]: i for i in load_instances(n, offline=offline)}

    ratios = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(_judge_saved, iid, inst, resume=resume): iid for iid, inst in by_id.items()}
        for fut in as_completed(futs):
            iid, ratio, tag = fut.result()
            if ratio is None:
                print(f"[skip] {iid}: {tag}")
            else:
                ratios.append(ratio)
                print(f"[ok]   {iid}: behaviour_coverage={ratio:.2f} ({tag})")
    if ratios:
        print(f"\nMEAN behaviour_coverage over {len(ratios)} judged instances: "
              f"{sum(ratios)/len(ratios):.3f}")
