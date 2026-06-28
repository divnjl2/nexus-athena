"""Drive the Athena frame on SWE-bench-Lite intents and score plan quality.

EXPENSIVE: each instance is a full headless `claude -p` frame session (~$2-3, ~10 min).
Capped by `--n`; runs in document order. Hold large runs behind an explicit invocation.

Per instance:
  1. intent = instance.problem_statement (the GitHub issue, optionally + hints_text).
  2. frame -> {edge_cases, scenarios:[{covers}], plan_files} via claude -p (real_pipeline-style).
  3. score:
     - behaviour_coverage (PRIMARY, LLM judge): fraction of FAIL_TO_PASS tests whose asserted
       behaviour is covered by some scenario/edge-case.
     - file_recall (SECONDARY, deterministic): score.file_recall vs the gold patch.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

from evals.swebench.loader import load_instances
from evals.swebench.score import fail_to_pass, file_recall, gold_patch_targets

CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
ATHENA = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _prompt(problem_statement: str, hints: str) -> str:
    hint_block = f"\n## Maintainer hints\n{hints}\n" if hints.strip() else ""
    return f"""You are the Athena planning agent. Run the spec-driven planning frame on ONE
real GitHub issue, faithfully (read {ATHENA}/commands/specify_root.md, scenarios.md,
crisp/3_design.md). Produce a genuine spec + scenarios + plan; be EXHAUSTIVE about the
behaviours and edge cases the fix must satisfy. You do NOT have the repo — reason from the
issue text only; name likely files by basename if implied.

## Issue (the intent)
{problem_statement}
{hint_block}
## Final message — ONLY this JSON (no prose):
{{"edge_cases":["..."],"scenarios":[{{"id":"S1.1","covers":"<behaviour>"}}],
"plan_files":["likely_file.py"]}}"""


def _json_block(text: str):
    text = re.sub(r"```(?:json)?|```", "", text)
    depth = start = -1
    for i, c in enumerate(text):
        if c == "{" and depth < 0:
            depth, start = 0, i
        if depth >= 0:
            depth += (c == "{") - (c == "}")
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    depth, start = -1, -1
    return None


def run_instance(instance: dict, *, timeout: int = 1800) -> dict:
    """Drive the frame on one issue. Returns the parsed plan summary + deterministic scores."""
    proc = subprocess.run(
        [CLAUDE, "-p", _prompt(instance["problem_statement"], instance.get("hints_text", "")),
         "--output-format", "json", "--dangerously-skip-permissions"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    raw = proc.stdout or ""
    try:
        env = json.loads(raw)
        result_text = env.get("result", raw) if isinstance(env, dict) else raw
    except json.JSONDecodeError:
        result_text = raw
    plan = _json_block(result_text) or {"edge_cases": [], "scenarios": [], "plan_files": []}
    fr = file_recall(set(plan.get("plan_files", [])), instance)
    return {
        "instance_id": instance["instance_id"],
        "n_edge_cases": len(plan.get("edge_cases", [])),
        "n_scenarios": len(plan.get("scenarios", [])),
        "fail_to_pass": fail_to_pass(instance),
        "gold_targets": gold_patch_targets(instance["patch"]),
        "file_recall": fr,
        "plan": plan,
        "note": "behaviour_coverage requires the LLM judge (held; run as a second pass)",
    }


def _save(result: dict) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{result['instance_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return path


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    offline = "--offline" in sys.argv
    results = []
    for inst in load_instances(n, offline=offline):
        iid = inst["instance_id"]
        try:
            r = run_instance(inst)
        except Exception as e:  # one bad/timed-out instance must not kill the batch
            r = {"instance_id": iid, "error": f"{type(e).__name__}: {str(e)[:120]}"}
        path = _save(r)
        results.append(r)
        ok = "ERROR" if "error" in r else (
            f"edge={r['n_edge_cases']} scen={r['n_scenarios']} "
            f"file_recall={r['file_recall']['recall']:.2f}")
        print(f"[{len(results)}/{n}] {iid}: {ok} -> {path}", flush=True)
    print(json.dumps(results, ensure_ascii=False, indent=1))
