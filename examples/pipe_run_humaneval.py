"""
Reference orchestrator: thread ONE run_id through the whole Athena pipe on a real task,
so every seam lands in ONE OpenTelemetry trace (the cross-cut thread no framework gives).

Proven live on HumanEval/0 (has_close_elements) -> gate PASS @ iter 1:
    run_id=50507aee... -> 5 seams (intent->ast->compile->master_plan->gate), all OK,
    replayed via seams.emit_otel into a single trace_id (chained waterfall).

Stages emit a SeamRecord at each boundary, all sharing `run_id`, chained via parent_span_id
and ordered by injected `ts_ns`. The durable seams.jsonl is the solo trace; replay it with
`seams.load_seams(path)` + `seams.emit_otel(recs, span_processor=seams.otlp_processor())`
to ship the same trace to Jaeger/Tempo for the fleet view.

Paths assume the WSL OpenHands workspace from the executor shakedown
(/root/he_eval with lib + the HumanEval front, /root/oh_venv with OpenHands V1).
The CRISP/Spec-Kit LLM-alignment front is skipped for an atomic HumanEval task (by design:
alignment is for complex multi-step work); the pipe still enters THROUGH Athena
(front -> compile -> master-plan -> executor -> gate).
"""
import os
import pathlib
import subprocess
import sys
import time
import uuid

W = pathlib.Path("/root/he_eval")
sys.path.insert(0, str(W))
from lib import seams
from lib.plan_parser import parse
from lib.plan2beads import compile as compile_plan

RUN_ID = uuid.uuid4().hex                       # one run_id -> one OTel trace
SEAMS = W / ".athena" / "seams.jsonl"
SEAMS.parent.mkdir(parents=True, exist_ok=True)
if SEAMS.exists():
    SEAMS.unlink()
recs = []


def emit(result, src, dst, **ctx):
    rec = seams.make_record(
        result, src=src, dst=dst,
        ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        run_id=RUN_ID, ts_ns=time.time_ns(),
        parent_span_id=recs[-1].span_id if recs else "",   # chain under prev seam
        context=ctx)
    recs.append(rec)
    seams.record_seam(rec, path=SEAMS)
    print(f"  seam {result.name:26} {'OK' if result.passed else 'FAIL':4} {src}->{dst}")
    return rec


print(f"=== PIPE run_id={RUN_ID} (HumanEval through Athena -> one trace) ===")
(W / "solution.py").write_text("")
task = "implement has_close_elements in solution.py per spec.txt"
front = (W / "front.plan.md").read_text()

emit(seams.seam_intent(task, True), "Hermes", "CRISP")                                          # 1
plan = parse(front)
emit(seams.seam_ast_wellformed(plan), "front", "AST")                                           # 2
emit(seams.seam_compile_pure(compile_plan, plan), "AST", "compiler")                            # 3
master = (W / "he0.master.md").read_text()
emit(seams.seam_structural("seam.master_plan", master, required=("## Tasks", "plan_id:")),
     "compiler", "PLAN_RUN")                                                                    # 4

env = {**os.environ, "OPENHANDS_SUPPRESS_BANNER": "1", "LLM_MODEL": "openai/qwopus35b",
       "LLM_BASE_URL": "http://localhost:8035/v1", "LLM_API_KEY": "sk-noauth"}
gate_ok, it = False, 0
for it in (1, 2, 3):                                                                            # Ralph retry
    subprocess.run(
        ["/root/oh_venv/bin/openhands", "--headless", "--always-approve", "--override-with-envs",
         "-t", "Implement the function in solution.py so the gate passes. Spec in spec.txt. "
               "Gate: python3 test_solution.py must print ALL HUMANEVAL CHECKS PASS and exit 0. "
               "Edit solution.py only."],
        cwd=str(W), env=env, capture_output=True, text=True, timeout=600)
    g = subprocess.run(["python3", "test_solution.py"], cwd=str(W), capture_output=True, text=True)
    if g.returncode == 0:
        gate_ok = True
        break
emit(seams.SeamResult("seam.gate", gate_ok, () if gate_ok else ("HumanEval test failed",)),
     "OpenHands@35B", "gate", iters=str(it))                                                     # 5 authoritative gate

print(f"=== gate {'PASS' if gate_ok else 'FAIL'} @ iter {it}; {len(recs)} seams, all run_id={RUN_ID} ===")
print("RUN_ID=" + RUN_ID)
