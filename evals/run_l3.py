"""L3 execution-closure eval — measure Athena PLAN QUALITY on a real task.

Flow (one run_id threaded through, the honest pyramid from EVALS):
  intent --planner--> spec(requirements)          [L1 metric: requirement recall]
        --planner--> scenarios (EARS->GWT)         [L1 metric: scenario coverage]
        --planner--> tasks (each verifies a scen)  -> Plan AST (Provenance+Scenarios)
        --compile--> plan2beads + validate         [L0 structural gate]
        --worker (Ralph<=3)--> code -> rpn.py
        --GROUND-TRUTH gate (pytest)--> pass/fail  [L3: closure, authoritative]

Honesty: the gate (corpus/<task>/gate_test.py) is the answer key the planner never
sees. Plan quality is judged by whether code built to the plan passes it, NOT by the
LLM's own scenarios (recorded for self-consistency only). Executor self-report is
worthless; the deterministic gate is authoritative.

Usage:  python evals/run_l3.py 01_rpn
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evals.llm import chat, LLMError                                       # noqa: E402
from lib.ast import Plan, Phase, Task, Provenance, Scenario               # noqa: E402
from lib.plan2beads import compile as compile_plan, CompileError          # noqa: E402

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _json_block(text: str):
    """Extract a JSON array/object from a model reply via balanced-bracket scanning.

    Greedy regex (first '[' .. last ']') breaks when the reply contains an inline
    example before the real answer. Instead, scan each '['/'{' start and return the
    LAST top-level structure that parses (the real answer follows any examples/prose).
    """
    text = re.sub(r"```(?:json)?|```", "", text)
    candidates = []
    for i, ch in enumerate(text):
        if ch not in "[{":
            continue
        close = "]" if ch == "[" else "}"
        depth, in_str, esc = 0, False, False
        for j in range(i, len(text)):
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
            elif c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    if c == close:
                        candidates.append(text[i:j + 1])
                    break
    for cand in reversed(candidates):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"no parseable JSON in reply: {text[:200]!r}")


def _normalize(raw, text_key: str) -> tuple[list[dict], int]:
    """Coerce an LLM hop reply to a list of dicts. Reasoning models drift in output shape
    (sometimes a bare string per item, or a single object instead of a list). We coerce
    rather than crash, and return how many items had to be coerced from a non-dict — a
    structured-output-reliability signal, not silently swallowed."""
    if isinstance(raw, dict):
        # a single object, or a wrapper like {"requirements": [...]} / {"scenarios": [...]}
        for v in raw.values():
            if isinstance(v, list):
                raw = v
                break
        else:
            raw = [raw]
    if not isinstance(raw, list):
        raw = [raw]
    items, coerced = [], 0
    for x in raw:
        if isinstance(x, dict):
            items.append(x)
        elif isinstance(x, str):
            items.append({text_key: x})
            coerced += 1
        else:
            coerced += 1
    return items, coerced


def _extract_code(text: str) -> str:
    """Pull Python source out of a reasoning-model reply (prose + optional fences)."""
    fences = re.findall(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if fences:
        # last fenced block that actually defines the function
        for blk in reversed(fences):
            if "def " in blk:
                return blk.strip()
        return fences[-1].strip()
    # no fences: take from the first top-level def/import to the end
    m = re.search(r"^(?:import |from |def )", text, re.MULTILINE)
    return text[m.start():].strip() if m else text.strip()


def hop_spec(intent: str) -> tuple[list[dict], float]:
    p = (f"You are a spec author. From this intent, list the distinct functional "
         f"requirements (what + why, no implementation). Intent:\n\n{intent}\n\n"
         f'Output ONLY a JSON array: [{{"id":"R1","text":"..."}}, ...]. No prose, no fences.')
    out, dt = chat(p, lane="planner", max_tokens=3000)
    return _json_block(out), dt


def hop_scenarios(reqs: list[dict]) -> tuple[list[dict], float]:
    p = ("For each requirement, write one executable Given-When-Then scenario that "
         "verifies it. Requirements:\n" + json.dumps(reqs) + "\n\n"
         'Output ONLY a JSON array: [{"id":"S1","requirement_key":"R1",'
         '"gwt":"Given...When...Then...","run_cmd":"<pytest cmd>"}]. No prose, no fences.')
    out, dt = chat(p, lane="planner", max_tokens=3500)
    return _json_block(out), dt


def hop_tasks(reqs: list[dict], scens: list[dict]) -> tuple[list[dict], float]:
    p = ("Decompose into implementation tasks. Each task verifies >=1 scenario id. "
         "Requirements:\n" + json.dumps(reqs) + "\nScenarios:\n" + json.dumps(scens) + "\n\n"
         'Output ONLY a JSON array: [{"id":"T1","title":"...",'
         '"verifies":["S1"],"success_check":"<cmd>"}]. No prose, no fences.')
    out, dt = chat(p, lane="planner", max_tokens=3500)
    return _json_block(out), dt


def build_plan(intent_title, reqs, scens, tasks, run_id) -> tuple[Plan, dict]:
    """Return (plan, signals). signals carries planner-quality counters that we must NOT
    hide: dropped_verifies (task->scenario links to non-existent ids) and malformed
    (LLM entries that weren't well-formed dicts — reasoning models drift in output shape)."""
    malformed = 0
    scenario_objs = []
    for i, s in enumerate(scens):
        if not isinstance(s, dict):
            malformed += 1
            continue
        scenario_objs.append(Scenario(
            id=str(s.get("id") or f"S{i+1}"),
            requirement_key=str(s.get("requirement_key", "")),
            gwt_text=str(s.get("gwt", "")), run_cmd=str(s.get("run_cmd", "true"))))
    scenario_objs = tuple(scenario_objs)
    valid_ids = {s.id for s in scenario_objs}
    dropped = 0
    task_objs = []
    for i, t in enumerate(tasks):
        if not isinstance(t, dict):
            malformed += 1
            continue
        verifies_raw = t.get("verifies", []) or []
        kept = tuple(v for v in verifies_raw if v in valid_ids)
        dropped += len(verifies_raw) - len(kept)
        task_objs.append(Task(id=str(t.get("id") or f"T{i+1}"),
                              title=str(t.get("title", t.get("id", f"T{i+1}"))),
                              success_check=str(t.get("success_check") or "true"),
                              verifies=kept))
    prov = Provenance(spec_version="sv1", scenario_version="scv1",
                      design_version="dv1", run_id=run_id)
    plan = Plan(title=intent_title, overview="", out_of_scope=(),
                phases=(Phase(key="impl", title="Implement", goal=intent_title,
                              tasks=tuple(task_objs)),),
                provenance=prov, scenarios=scenario_objs)
    return plan, {"dropped_verifies": dropped, "malformed_entries": malformed}


def _kw_hit(blob: str, keywords: list[str]) -> bool:
    """True if any keyword appears as a whole word/phrase in blob (no substring false-positives)."""
    for k in keywords:
        if re.search(r"(?<![a-z0-9])" + re.escape(k.lower()) + r"(?![a-z0-9])", blob):
            return True
    return False


def _coverage_against(texts: list[str], expected: list[dict]) -> tuple[float, list[str]]:
    """Fraction of ground-truth requirements whose distinctive keywords appear in `texts`."""
    blob = " ".join(texts).lower()
    hit, missed = 0, []
    for er in expected:
        if _kw_hit(blob, er.get("keywords", [])):
            hit += 1
        else:
            missed.append(er["id"])
    return hit / max(len(expected), 1), missed


def recall(spec_reqs: list[dict], expected: list[dict]) -> tuple[float, list[str]]:
    """Fraction of ground-truth requirements present in the spec (whole-word match)."""
    return _coverage_against([r.get("text", "") for r in spec_reqs], expected)


def execute_ralph(task_dir: str, intent: str, scens: list[dict], gate_test: str,
                  max_iter: int = 3) -> tuple[bool, int, list[str]]:
    """Generate code (worker) -> write rpn.py -> run ground-truth gate. Retry on fail."""
    target = os.path.join(task_dir, "rpn.py")
    log = []
    feedback = ""
    for it in range(1, max_iter + 1):
        p = (f"Implement the function for this intent so a hidden test suite passes.\n"
             f"Intent: {intent}\n"
             f"Requirements covered by these scenarios:\n{json.dumps(scens)}\n"
             f"{feedback}\n"
             f"Reply with ONLY the complete Python file contents (a function "
             f"eval_rpn(expr: str) -> float). No prose.")
        try:
            out, dt = chat(p, lane="worker", max_tokens=4096)
        except LLMError as e:
            log.append(f"iter{it}: LLM error {e}")
            continue
        code = _extract_code(out)
        with open(target, "w", encoding="utf-8") as f:
            f.write(code + "\n")
        g = subprocess.run([sys.executable, "-m", "pytest", gate_test, "-q"],
                           capture_output=True, text=True, cwd=task_dir)
        passed = g.returncode == 0
        tail = (g.stdout or "").strip().splitlines()[-1:] or [""]
        log.append(f"iter{it}: gen {dt:.1f}s, gate {'PASS' if passed else 'FAIL'} ({tail[0]})")
        if passed:
            return True, it, log
        # include stderr: SyntaxError / ImportError land there, not stdout — without it
        # a broken file yields blank feedback and the retry loop flails.
        feedback = (f"Previous attempt FAILED the gate.\n"
                    f"stdout:\n{g.stdout[-500:]}\nstderr:\n{g.stderr[-400:]}\n"
                    f"Fix the implementation.")
    return False, max_iter, log


def main(task_id: str):
    run_id = uuid.uuid4().hex[:8]
    task_dir = os.path.join(CORPUS, task_id)
    expected = yaml.safe_load(open(os.path.join(task_dir, "expected.yaml"), encoding="utf-8"))
    intent = open(os.path.join(task_dir, "intent.md"), encoding="utf-8").read()
    gate_test = os.path.join(task_dir, "gate_test.py")

    print(f"=== L3 eval task={task_id} run_id={run_id} ===")
    timings = {}

    reqs, timings["spec"] = hop_spec(intent)
    reqs, c1 = _normalize(reqs, "text")
    print(f"[spec]      {len(reqs)} requirements ({timings['spec']:.1f}s)")
    scens, timings["scenarios"] = hop_scenarios(reqs)
    scens, c2 = _normalize(scens, "gwt")
    print(f"[scenarios] {len(scens)} scenarios ({timings['scenarios']:.1f}s)")
    tasks, timings["tasks"] = hop_tasks(reqs, scens)
    tasks, c3 = _normalize(tasks, "title")
    print(f"[tasks]     {len(tasks)} tasks ({timings['tasks']:.1f}s)")
    coerced_total = c1 + c2 + c3
    if coerced_total:
        print(f"[shape]     {coerced_total} LLM items coerced from non-dict "
              f"(structured-output drift signal)")

    # L0 structural gate: does it compile into a valid provenance graph?
    plan, signals = build_plan(expected["target_symbol"], reqs, scens, tasks, run_id)
    dropped_verifies = signals["dropped_verifies"]
    structural_ok, structural_err = True, ""
    try:
        compile_plan(plan)
    except CompileError as e:
        structural_ok, structural_err = False, str(e)
    print(f"[L0 compile] {'PASS' if structural_ok else 'FAIL: ' + structural_err}"
          f"  (dropped task->scenario links: {dropped_verifies}, "
          f"malformed LLM entries: {signals['malformed_entries']})")

    # L1 metrics — both via whole-word match against ground-truth distinctive keywords.
    # recall: ground-truth reqs present in the SPEC. coverage: present in the SCENARIO texts
    # (semantic, NOT planner-vs-groundtruth id-name collision).
    rec, missed = recall(reqs, expected["requirements"])
    scen_texts = [s.get("gwt", "") + " " + s.get("run_cmd", "") for s in scens]
    coverage, cov_missed = _coverage_against(scen_texts, expected["requirements"])
    print(f"[L1 recall] {rec:.0%} of ground-truth reqs in SPEC (missed: {missed or 'none'})")
    print(f"[L1 cover ] {coverage:.0%} of ground-truth reqs have a SCENARIO (missed: {cov_missed or 'none'})")

    # L3 execution closure (authoritative ground-truth gate)
    gate_ok, iters, ex_log = execute_ralph(task_dir, intent, scens, gate_test)
    for line in ex_log:
        print(f"[L3 exec ] {line}")
    print(f"[L3 gate ] {'PASS' if gate_ok else 'FAIL'} after {iters} iter(s)")

    result = {
        "task_id": task_id, "run_id": run_id,
        "models": {"planner": "qwen35-a3b@8000", "worker": "qwen9b-opus@8001"},
        "spec_requirements": len(reqs), "scenarios": len(scens), "tasks": len(tasks),
        "L0_structural_ok": structural_ok, "L0_error": structural_err,
        "L0_dropped_verifies": dropped_verifies,
        "L0_malformed_entries": signals["malformed_entries"],
        "L0_coerced_items": coerced_total,
        "L1_requirement_recall": round(rec, 3), "L1_recall_missed": missed,
        "L1_scenario_coverage": round(coverage, 3), "L1_coverage_missed": cov_missed,
        "L3_gate_pass": gate_ok, "L3_iterations": iters, "L3_log": ex_log,
        "timings_s": {k: round(v, 1) for k, v in timings.items()},
        "raw": {"requirements": reqs, "scenarios": scens, "tasks": tasks},
    }
    os.makedirs(RESULTS, exist_ok=True)
    out_path = os.path.join(RESULTS, f"{task_id}-{run_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"=== result -> {out_path} ===")
    return result


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "01_rpn")
