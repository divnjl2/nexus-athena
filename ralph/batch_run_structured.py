"""HumanEval battle-test — STRUCTURED executor (the harness that hits ~100% delivery).

Same archive/trace format as batch_run.py (results.jsonl + all_seams.jsonl + archive/<task>/
for the Console), but the executor is a direct structured completion (model returns ONLY
code -> harness writes the file -> gate), NOT agentic OpenHands. Default model port 8036 (14B,
fast+stable). HE_START / HE_LIMIT slice; HE_PORT picks the model.
"""
import json
import os
import pathlib
import re
import shutil
import statistics as st
import subprocess
import sys
import time
import urllib.request
import uuid

sys.path.insert(0, "/root/he_eval")
from lib import seams
from lib.ast import Plan, Phase, Task
from lib.plan2beads import compile as compile_plan
from human_eval.data import read_problems

LIMIT = int(os.environ.get("HE_LIMIT", "0"))
START = int(os.environ.get("HE_START", "0"))
PORT = os.environ.get("HE_PORT", "8036")
RETRIES = int(os.environ.get("HE_RETRIES", "2"))
WORK = pathlib.Path("/root/he_struct")
ARCHROOT = WORK / "archive"
RESULTS = WORK / "results.jsonl"
ALLSEAMS = WORK / "all_seams.jsonl"
shutil.rmtree(WORK, ignore_errors=True)
ARCHROOT.mkdir(parents=True)


def extract_code(content):
    if "</think>" in content:
        content = content.split("</think>")[-1]
    content = content.strip()
    m = re.search(r"```(?:python)?\s*(.*?)```", content, re.DOTALL)
    return m.group(1).strip() if m else content


def complete_code(prompt, timeout=150):
    sys_msg = "You are a Python code generator. Output ONLY runnable Python — no prose, no markdown fences."
    user = ("Implement this function completely. Keep the exact signature and include any needed imports. "
            "Output ONLY the Python code:\n\n" + prompt)
    body = json.dumps({"messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}],
                       "max_tokens": 4096, "temperature": 0}).encode()
    req = urllib.request.Request(f"http://localhost:{PORT}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return extract_code(json.loads(r.read())["choices"][0]["message"]["content"])
    except Exception:
        return ""


def master_plan_seam(plan):
    try:
        from lib.hermes_plan import render_master_plan
        return seams.seam_structural("seam.master_plan", render_master_plan(plan), required=("## Tasks",))
    except Exception:
        return seams.SeamResult("seam.master_plan", len(compile_plan(plan).commands) > 0, ())


problems = list(read_problems().items())[START:]
if LIMIT:
    problems = problems[:LIMIT]
total = len(problems)
print(f"=== HumanEval STRUCTURED battle-test: {total} tasks | executor=structured@{PORT} | retries={RETRIES} ===", flush=True)

t0 = time.time(); npass = 0; secs_all = []
for i, (tid, p) in enumerate(problems, 1):
    rid = uuid.uuid4().hex
    entry = p["entry_point"]
    safe = tid.replace("/", "_")
    ARCH = ARCHROOT / safe
    ARCH.mkdir(parents=True, exist_ok=True)
    ws = WORK / "ws"
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir()
    (ws / "test_solution.py").write_text(f"from solution import {entry}\n\n{p['test']}\ncheck({entry})\n")

    recs = []

    def emit(result, src, dst):
        rec = seams.make_record(result, src=src, dst=dst, ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                run_id=rid, ts_ns=time.time_ns(), parent_span_id=recs[-1].span_id if recs else "")
        recs.append(rec)
        seams.record_seam(rec, path=ALLSEAMS)
        seams.record_seam(rec, path=ARCH / "seams.jsonl")
        return rec

    plan = Plan(safe, p["prompt"][:60].replace("\n", " "), (), (
        Phase("phase1", "Implement", "impl " + entry, tasks=(Task("T1.1", f"implement {entry}", "python3 test_solution.py"),)),))
    emit(seams.seam_intent(f"implement {entry}", True), "Hermes", "CRISP")
    emit(seams.seam_ast_wellformed(plan), "front", "AST")
    emit(seams.seam_compile_pure(compile_plan, plan), "AST", "compiler")
    emit(master_plan_seam(plan), "compiler", "PLAN_RUN")

    ts = time.time()
    ok = False
    for attempt in range(RETRIES + 1):
        code = complete_code(p["prompt"])
        (ws / "solution.py").write_text(code)
        g = subprocess.run(["python3", "test_solution.py"], cwd=str(ws), capture_output=True, text=True)
        ok = g.returncode == 0
        if ok:
            break
    nbytes = (ws / "solution.py").stat().st_size
    emit(seams.SeamResult("seam.gate", ok, () if ok else ("test failed",)), f"structured@{PORT}", "gate")

    (ARCH / "solution.py").write_text((ws / "solution.py").read_text())
    (ARCH / "gate.txt").write_text(f"exit={g.returncode}\n--- stderr ---\n{g.stderr[-1500:]}")
    secs = time.time() - ts
    secs_all.append(secs)
    npass += int(ok)
    with RESULTS.open("a") as fh:
        fh.write(json.dumps({"task_id": tid, "entry_point": entry, "passed": ok, "hung": False,
                             "seconds": round(secs, 1), "run_id": rid, "solution_bytes": nbytes,
                             "gate_exit": g.returncode, "archive": str(ARCH)}) + "\n")
    print(f"[{i}/{total}] {tid:14} {'PASS' if ok else 'FAIL'} {secs:5.0f}s {nbytes:4}B | pass={npass}/{i} ({100*npass/i:.0f}%) | {(time.time()-t0)/60:.0f}m", flush=True)

elapsed = time.time() - t0
sm = sorted(secs_all)
p90 = sm[min(len(sm) - 1, int(0.9 * len(sm)))] if sm else 0
print(f"=== DONE: {npass}/{total} passed ({100*npass/max(total,1):.1f}%) | wall={elapsed/60:.1f}m | "
      f"median={st.median(secs_all) if secs_all else 0:.0f}s p90={p90:.0f}s max={max(secs_all) if secs_all else 0:.0f}s ===", flush=True)
