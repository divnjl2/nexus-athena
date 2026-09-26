"""Gap 4 measurement: how many tests a small model drafts for a clause are admissible (C-2.1 of the
foundry): a drafted test must pass at HEAD, fail on a forged break of a line the clause owns
(the forge as the "base", SWE-smith's fail-to-pass rule) and cover an owned line. Records one
row per draft; the acceptance table per model comes from lib.drafts.acceptance.

usage: python tools/draft_acceptance.py <feature-dir> <module> <executor> [clause-prefix] [drafts-per-clause]
       e.g. python tools/draft_acceptance.py features/refinery-layer lib/refinery.py pi-9b C-2 2
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.drafts import acceptance, admit_draft, render_acceptance  # noqa: E402
from lib.executors import pi_binary, pi_command  # noqa: E402
from lib.forge import pick_targets  # noqa: E402

def _ask(argv, prompt, cwd):
    """one headless pi call; a stall (measured: 20 min with the lane idle) returns "" instead of killing the run"""
    try:
        p = subprocess.run(argv, input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=True, timeout=600, cwd=str(cwd))
    except subprocess.TimeoutExpired:
        subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process -Filter \"name='node.exe'\" | Where-Object { $_.CommandLine -match 'pi-coding-agent' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)
        return ""
    text = ""
    for line in (p.stdout or "").splitlines():
        if line.startswith("{"):
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "message_end" and (ev.get("message") or {}).get("role") == "assistant":
                text = "".join(b.get("text", "") for b in ev["message"].get("content") or [] if b.get("type") == "text")
    return text


feature = (ROOT / sys.argv[1]).resolve()
module = sys.argv[2]
executor = sys.argv[3]
prefix = sys.argv[4] if len(sys.argv) > 4 else ""
per_clause = int(sys.argv[5]) if len(sys.argv) > 5 else 2

import athena  # noqa: E402
import types  # noqa: E402

contract_md = feature / "contract.md"
ns = types.SimpleNamespace(scenarios="", speckit="auto", contract=str(contract_md))
contract = athena._load_contract(ns)
scenarios = athena._load_scenarios(ns, anchor=str(contract_md))
clause_map = json.loads((feature / "clause_map.json").read_text(encoding="utf-8"))
sources = {module: (ROOT / module).read_text(encoding="utf-8")}
clause_text = {c.id: c.text for c in getattr(contract, "clauses", [])} if hasattr(contract, "clauses") else {}
if not clause_text:
    for m in re.finditer(r"- \*\*(C-\d+\.\d+)\*\* — (.+?)(?=\n- \*\*C-|\n## |\Z)", contract_md.read_text(encoding="utf-8"), re.S):
        clause_text[m.group(1)] = " ".join(m.group(2).split())

tree = ast.parse(sources[module])
rich = len(sys.argv) > 6 and sys.argv[6] == "rich"   # arm 2: docstrings and one example spec ride along
rounds = int(sys.argv[7]) if len(sys.argv) > 7 else 1   # arm 4: repair rounds with the failure in hand (1 = arm 3)
sigs = []
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"):
        line = f"def {n.name}({ast.unparse(n.args)})" + (f" -> {ast.unparse(n.returns)}" if n.returns else "")
        doc = (ast.get_docstring(n) or "").strip()
        if rich and doc:
            line += "\n        \"\"\"" + " ".join(doc.split())[:400] + "\"\"\""
        sigs.append(line)
modname = module[:-3].replace("/", ".")
example = ""
if rich:
    # one existing spec of a DIFFERENT clause as the example of the house style and the shapes
    src = (ROOT / "tests" / f"test_{pathlib.Path(module).stem}.py")
    if src.exists():
        m = re.search(r"\ndef (test_\w+)\(\):\n(?:.*\n)*?(?=\ndef |\Z)", src.read_text(encoding="utf-8"))
        example = m.group(0).strip() if m else ""

targets = pick_targets(clause_map, scenarios, sources, n=50, mutants_per_task=1, seed=11, clause_prefix=prefix)
by_clause = {}
for t in targets:
    by_clause.setdefault(t["clause"], t)
print(f"# clauses with a forgeable line in {module}: {sorted(by_clause)}", flush=True)

events = []
# the executor's working directory is a scratch worktree: what it writes on its own stays out of the repository
SCRATCH = pathlib.Path(tempfile.mkdtemp(prefix='drafts-')) / 'ws'
subprocess.run(['git', 'worktree', 'add', '--detach', str(SCRATCH), 'HEAD'], cwd=str(ROOT), capture_output=True)
import atexit
atexit.register(lambda: subprocess.run(['git', 'worktree', 'remove', '--force', str(SCRATCH)], cwd=str(ROOT), capture_output=True))
out_dir = feature / ".athena" / "drafts"
out_dir.mkdir(parents=True, exist_ok=True)
for cid in sorted(by_clause):
    task = by_clause[cid]
    mutant = task["_mutants"][0]
    owned_lines = {module: sorted({m["line"] for m in task["mutants"]} | set(clause_map["clauses"].get(cid, {}).get(module, [])))}
    for k in range(per_clause):
        prompt = "\n".join([
            f"# Draft ONE pytest test for clause {cid} of `{modname}`",
            "",
            "The clause (EARS):", "", clause_text.get(cid, "(see contract)"), "",
            f"Public signatures of `{modname}` (import from it; do not read the module's body, it is not the spec):", "",
            *[f"    {s}" for s in sigs], "",
            *(["One existing spec of another clause, for the house style and the shapes the functions return:", "",
               "```python", example, "```", ""] if example else []),
            "Rules: write exactly one function `def test_...():` with a docstring that starts with the clause id",
            f"(`\"\"\"{cid} — ...\"\"\"`), pure, no files, no network, deterministic. Build the inputs from the",
            "clause's own words. Reply with the Python code of the test function ONLY, in one ```python block.",
        ])
        spec = pi_command(executor, prompt, pi_bin=pi_binary(), thinking="low", strict=False)
        argv = [x for x in spec["argv"]]
        # a text answer, no tools: drop the tool list and the order, keep provider/model/thinking
        cleaned = []
        skip = False
        for x in argv:
            if skip:
                skip = False; continue
            if x == "--tools":
                skip = True; continue
            cleaned.append(x)
        cleaned = cleaned[:-1] + ["Answer with the test code only."]
        t0 = time.time()
        text = _ask(cleaned, prompt, SCRATCH)
        m = re.search(r"```python\s*(.*?)```", text, re.S)
        code = (m.group(1) if m else text).strip()
        fn = re.search(r"def (test_\w+)\s*\(", code)
        row = {"model": executor, "clause": cid, "draft": k + 1, "seconds": int(time.time() - t0), "admitted": False, "accepted": False, "reason": ""}
        if not fn or "import" not in code and modname not in code:
            row["reason"] = "no test function" if not fn else "does not touch the module"
            events.append(row); print(json.dumps(row), flush=True); continue
        test_path = out_dir / f"draft_{cid.replace('.', '_').replace('-', '_')}_{k + 1}.py"
        header = f"from {modname} import *  # noqa\n" if f"from {modname}" not in code and f"import {modname}" not in code else ""
        test_path.write_text(header + code + "\n", encoding="utf-8")
        node = f"{test_path.as_posix()}::{fn.group(1)}"
        def run_pytest(cwd):
            r = subprocess.run([sys.executable, "-m", "pytest", node, "-q", "-p", "no:cacheprovider", "--rootdir", str(ROOT)], cwd=str(cwd), capture_output=True, text=True, timeout=300)
            return r.returncode
        head_exit = run_pytest(ROOT)
        repaired = False
        repairs = 0
        for _round in range(rounds if rich else 0):
            if head_exit == 0:
                break
            # arm 3 (Otter++'s move): one repair round with the failure in hand, then re-run at HEAD
            r0 = subprocess.run([sys.executable, "-m", "pytest", node, "-q", "-p", "no:cacheprovider", "--rootdir", str(ROOT), "--tb=short"],
                                cwd=str(ROOT), capture_output=True, text=True, timeout=300)
            tail = (r0.stdout or "")[-1500:]
            fix_prompt = "\n".join([f"# Repair this pytest test for clause {cid} of `{modname}`", "",
                                    "It fails at HEAD with:", "```", tail, "```", "",
                                    "The test, as written:", "```python", code, "```", "",
                                    "Fix ONLY the test so it passes against the real module (keep the clause's intent, one function,",
                                    "same name). Reply with the Python code of the test function ONLY, in one ```python block."])
            text2 = _ask(cleaned, fix_prompt, SCRATCH)
            m2 = re.search(r"```python\s*(.*?)```", text2, re.S)
            code2 = (m2.group(1) if m2 else "").strip()
            fn2 = re.search(r"def (test_\w+)\s*\(", code2)
            if not fn2:
                # arm 5: the reply carried no test function — ask once more for the function itself
                text3 = _ask(cleaned, 'Your previous answer had no test function. Reply with the COMPLETE pytest test function for clause ' + cid + ' of `' + modname + '` in one ```python block, nothing else.', SCRATCH)
                m3 = re.search(r'```python\s*(.*?)```', text3, re.S)
                code2 = (m3.group(1) if m3 else '').strip()
                fn2 = re.search(r'def (test_\w+)\s*\(', code2)
                if not fn2:
                    break
            code = code2
            fn = fn2
            test_path.write_text(header + code + "\n", encoding="utf-8")
            node = f"{test_path.as_posix()}::{fn.group(1)}"
            head_exit = run_pytest(ROOT)
            repaired = True
            repairs += 1
        row["repaired"] = repaired
        row["repairs"] = repairs
        with tempfile.TemporaryDirectory() as td:
            mirror = pathlib.Path(td) / "m"
            subprocess.run(["git", "worktree", "add", "--detach", str(mirror), "HEAD"], cwd=str(ROOT), capture_output=True)
            try:
                (mirror / module).write_text(mutant.source, encoding="utf-8")
                (mirror / test_path.relative_to(ROOT)).parent.mkdir(parents=True, exist_ok=True)
                (mirror / test_path.relative_to(ROOT)).write_text(test_path.read_text(encoding="utf-8"), encoding="utf-8")
                r = subprocess.run([sys.executable, "-m", "pytest", f"{test_path.relative_to(ROOT).as_posix()}::{fn.group(1)}", "-q", "-p", "no:cacheprovider"], cwd=str(mirror), capture_output=True, text=True, timeout=300)
                base_exit = r.returncode
            finally:
                subprocess.run(["git", "worktree", "remove", "--force", str(mirror)], cwd=str(ROOT), capture_output=True)
        ok, why = admit_draft(base_exit=base_exit, head_exit=head_exit, covered=owned_lines, owned=owned_lines)
        row.update({"admitted": ok, "reason": why, "head_exit": head_exit, "base_exit": base_exit, "test": node,
                    "mutant": f"{mutant.path}:{mutant.line} ({mutant.kind})"})
        events.append(row); print(json.dumps(row), flush=True)
table = acceptance([{"model": e["model"], "admitted": e["admitted"], "accepted": e["accepted"]} for e in events])
print(render_acceptance(table))
(out_dir / "acceptance.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
