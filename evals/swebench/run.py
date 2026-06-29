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
    """Largest top-level balanced JSON object, string/escape-aware (a `}` inside a string
    value must not close the object — the naive scanner dropped whole valid plans)."""
    text = re.sub(r"```(?:json)?|```", "", text)
    cands, i, n = [], 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth, in_str, esc, end = 0, False, False, None
        for j in range(i, n):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is not None:
            cands.append(text[i:end + 1])
            i = end + 1
        else:
            i += 1
    for c in sorted(cands, key=len, reverse=True):
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
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
    parsed = _json_block(result_text)
    plan = parsed or {"edge_cases": [], "scenarios": [], "plan_files": []}
    fr = file_recall(set(plan.get("plan_files", [])), instance)
    return {
        "instance_id": instance["instance_id"],
        "n_edge_cases": len(plan.get("edge_cases", [])),
        "n_scenarios": len(plan.get("scenarios", [])),
        "parse_ok": parsed is not None,   # False = agent output had no parseable JSON (diagnose via raw)
        "fail_to_pass": fail_to_pass(instance),
        "gold_targets": gold_patch_targets(instance["patch"]),
        "file_recall": fr,
        "plan": plan,
        "raw_tail": result_text[-1200:],  # keep the tail so a parse miss is diagnosable
        "note": "behaviour_coverage requires the LLM judge (held; run as a second pass)",
    }


def _save(result: dict) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"{result['instance_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return path


def _existing_ok(iid: str) -> bool:
    """Resume: an instance is 'done' if it has a saved non-error result with a real plan.
    Tolerant of the pre-parse_ok schema (judge by a non-empty plan when the flag is absent)."""
    p = os.path.join(RESULTS_DIR, f"{iid}.json")
    if not os.path.exists(p):
        return False
    try:
        d = json.load(open(p, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if "error" in d:
        return False
    if "parse_ok" in d:
        return bool(d["parse_ok"])
    return d.get("n_scenarios", 0) > 0 or d.get("n_edge_cases", 0) > 0  # older schema


def _one(inst: dict) -> dict:
    iid = inst["instance_id"]
    try:
        r = run_instance(inst)
    except Exception as e:  # one bad/timed-out instance must not kill the batch
        r = {"instance_id": iid, "error": f"{type(e).__name__}: {str(e)[:120]}"}
    _save(r)
    return r


if __name__ == "__main__":
    import sys
    from concurrent.futures import ThreadPoolExecutor, as_completed

    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1
    offline = "--offline" in sys.argv
    resume = "--resume" in sys.argv          # skip instances already done (parse_ok)
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), "")
    workers = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--workers=")), "4"))
    only_ids = {x.strip() for x in only.split(",") if x.strip()}

    insts = load_instances(n, offline=offline)
    if only_ids:
        insts = [i for i in insts if i["instance_id"] in only_ids]
    if resume:
        insts = [i for i in insts if not _existing_ok(i["instance_id"])]

    print(f"[run] {len(insts)} instances to run (workers={workers}); skipping done={resume}", flush=True)
    done = ok = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(_one, i): i["instance_id"] for i in insts}
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if "error" in r:
                tag = f"ERROR {r['error'][:50]}"
            elif not r.get("parse_ok"):
                tag = "NO-PLAN (policy/parse — see raw_tail)"
            else:
                ok += 1
                tag = (f"edge={r['n_edge_cases']} scen={r['n_scenarios']} "
                       f"file_recall={r['file_recall']['recall']:.2f}")
            print(f"[{done}/{len(insts)}] {r['instance_id']}: {tag}", flush=True)
    print(f"[run] complete: {ok}/{len(insts)} produced a parseable plan", flush=True)
