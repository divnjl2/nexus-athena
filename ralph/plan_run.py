"""plan_run.py — the FULL Athena pipe as ONE autonomous command.

front  ->  athena compile (seams: intent/ast/compile)  ->  master-plan (bridge)  ->
PLAN_RUN: for each task -> ATHENA_TASK (OpenHands execute -> gate) -> WRITEBACK (check the box).

One command, N tasks. Emits the full seam trace (one run_id per task) + the written-back
master-plan. Executor model via PLAN_PORT (default 8036=14B; 35B was stuck).
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import uuid
import re
import urllib.request

sys.path.insert(0, "/root/he_eval")
from lib import seams
from lib.plan_parser import parse as plan_parse
from lib.plan2beads import compile as compile_plan
from lib.hermes_plan import render_master_plan
from human_eval.data import read_problems

N = int(os.environ.get("PLAN_N", "10"))
PORT = os.environ.get("PLAN_PORT", "8036")
WORK = pathlib.Path("/root/plan_run")
shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True)
SEAMS = WORK / "seams.jsonl"
OH = "/root/oh_venv/bin/openhands"
ENV = {**os.environ, "OPENHANDS_SUPPRESS_BANNER": "1", "LLM_MODEL": "openai/local",
       "LLM_BASE_URL": f"http://localhost:{PORT}/v1", "LLM_API_KEY": "sk-noauth"}
problems = list(read_problems().items())[:N]


def extract_code(content):
    if "</think>" in content:                  # reasoning models: drop the think block
        content = content.split("</think>")[-1]
    content = content.strip()
    m = re.search(r"```(?:python)?\s*(.*?)```", content, re.DOTALL)
    return m.group(1).strip() if m else content


def complete_code(prompt, port, timeout=150):
    """STRUCTURED executor: model returns ONLY code; harness writes the file. No agent."""
    sys_msg = "You are a Python code generator. Output ONLY runnable Python — no prose, no markdown fences."
    user = ("Implement this function completely. Keep the exact signature and include any needed imports. "
            "Output ONLY the Python code:\n\n" + prompt)
    body = json.dumps({"messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}],
                       "max_tokens": 4096, "temperature": 0}).encode()
    req = urllib.request.Request(f"http://localhost:{port}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return extract_code(json.loads(r.read())["choices"][0]["message"]["content"])
    except Exception:
        return ""


def emit(result, src, dst, run_id, recs):
    rec = seams.make_record(result, src=src, dst=dst, ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            run_id=run_id, ts_ns=time.time_ns(), parent_span_id=recs[-1].span_id if recs else "")
    recs.append(rec)
    seams.record_seam(rec, path=SEAMS)
    return rec


# ===== STAGE 1: FRONT (a plan.md with N tasks) =====
print(f"=== STAGE 1: FRONT — {N} tasks ===", flush=True)
fl = ["# Plan: humaneval-pipe", "## Overview",
      f"Implement {N} HumanEval functions end-to-end through the Athena pipe.",
      "## Out of Scope", "- anything else"]
for i, (tid, p) in enumerate(problems, 1):
    e = p["entry_point"]
    fl += [f"## Phase {i}: {e}", f"**Goal:** {e} correct", "### Tasks",
           f"- [ ] T{i}.1 implement {e} in sol_{i}.py", f"  - success_check: `python3 test_{i}.py`", f"  - files: `sol_{i}.py`"]
front_md = "\n".join(fl)
(WORK / "front.plan.md").write_text(front_md)
print(f"  front.plan.md: {N} phases / {N} tasks", flush=True)

# ===== STAGE 2: COMPILE — parse -> AST -> seams -> master-plan =====
print("=== STAGE 2: COMPILE (Athena glue) ===", flush=True)
plan_recs = []
pid = uuid.uuid4().hex
plan = plan_parse(front_md)
emit(seams.seam_intent(f"implement {N} humaneval", True), "Hermes", "CRISP", pid, plan_recs)
emit(seams.seam_ast_wellformed(plan), "front", "AST", pid, plan_recs)
emit(seams.seam_compile_pure(compile_plan, plan), "AST", "compiler", pid, plan_recs)
master = render_master_plan(plan, plan_id="humaneval-pipe")
emit(seams.seam_structural("seam.master_plan", master, required=("## Tasks", "plan_id:")), "compiler", "PLAN_RUN", pid, plan_recs)
(WORK / "master.md").write_text(master)
for r in plan_recs:
    print(f"  {r.name:22} {'OK' if r.passed else 'FAIL'}", flush=True)
print(f"  master-plan: {master.count('task_id:')} ATHENA_TASK entries", flush=True)

# ===== STAGE 3: PLAN_RUN — drive each task (executor -> gate -> writeback) =====
print("=== STAGE 3: PLAN_RUN (executor -> gate -> writeback) ===", flush=True)
npass = 0
t0 = time.time()
for i, (tid, p) in enumerate(problems, 1):
    e = p["entry_point"]
    rid = uuid.uuid4().hex
    recs = []
    # FRESH clean workspace per task (only solution.py + test_solution.py) — a cluttered
    # shared cwd confuses OpenHands into editing nothing (harness bug, fixed 2026-06-10).
    ws = WORK / f"t{i}"
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir()
    (ws / "solution.py").write_text("")
    (ws / "test_solution.py").write_text(f"from solution import {e}\n\n{p['test']}\ncheck({e})\n")
    emit(seams.seam_intent(f"implement {e}", True), "PLAN_RUN", "ATHENA_TASK", rid, recs)
    # --- ATHENA_TASK: STRUCTURED-COMPLETION executor + Ralph retry ---
    # Atomic code-gen: the model RETURNS code, the harness writes the file + runs the gate.
    # No agent loop -> nothing to wander into (the agentic path invited /sdk-exploration ->
    # empty files). Executor is pluggable behind the gate; structured = right tool for atomic.
    ok = False
    nbytes = 0
    attempts = 0
    for attempt in range(3):                                  # Ralph: retry until the gate passes
        attempts = attempt + 1
        code = complete_code(p["prompt"], PORT)
        (ws / "solution.py").write_text(code)
        (ws / f"completion_{attempt}.py").write_text(code)
        g = subprocess.run(["python3", "test_solution.py"], cwd=str(ws), capture_output=True, text=True)
        ok = g.returncode == 0
        nbytes = (ws / "solution.py").stat().st_size
        if ok:
            break
    emit(seams.SeamResult("seam.gate", ok, () if ok else (f"failed after {attempts} attempts",)), f"structured@{PORT}", "gate", rid, recs)
    # --- WRITEBACK: mark the box in the master-plan ---
    if ok:
        master = master.replace(f"- [ ] task_id: T{i}.1", f"- [x] task_id: T{i}.1")
        npass += 1
    (WORK / "master.md").write_text(master)
    print(f"  [{i}/{N}] T{i}.1 {e:22} executor->gate {'PASS' if ok else 'FAIL'} ({nbytes}B, {attempts}att) -> writeback [{'x' if ok else ' '}]  pass={npass}/{i}", flush=True)

elapsed = time.time() - t0
checked = master.count("- [x]")
print(f"=== DONE: {npass}/{N} passed | master-plan written back {checked}/{N} checked | {elapsed/60:.1f}m ===", flush=True)
print(f"=== trace: {SEAMS} ({sum(1 for _ in open(SEAMS))} seams across {N+1} run_ids) ===", flush=True)
