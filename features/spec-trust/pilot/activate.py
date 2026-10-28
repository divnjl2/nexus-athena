"""Independent activation probes: succeed ONLY when the named violation is observable.

These are not the executable specs. They must fail on the clean implementation.
"""
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from lib.check import build
from lib.contract import parse, pin_scenarios
from lib.mutation import hunt, summarize
from lib.mutgate import clause_scores
from lib.spec_trust import SCHEMA, audit, execute, prepare
from lib.verification import Outcome


def mutant(runner, **kw):
    return hunt({"clauses": {"C-1": {"x.py": [2]}}}, {"S1": ("C-1", "check")},
                {"x.py": {"source": "def f(x):\n    return x == 1 and x != 2\n", "lines": [2]}},
                runner=runner, writer=lambda *a: None, limit_per_line=10, **kw)


def fixture(root):
    text = "- **C-1.1** — WHEN a value repeats THE SYSTEM SHALL retain it once.\n"
    contract = parse(text)
    (root / "contract.md").write_text(text, encoding="utf-8")
    s = "### S1.1 — retain\n- **verifies:** C-1.1\n- **run_cmd:** `python check.py`\n"
    (root / "scenarios.md").write_text(pin_scenarios(s, contract)[0], encoding="utf-8")
    (root / "impl.py").write_text("baseline", encoding="utf-8")
    (root / "check.py").write_text("pass", encoding="utf-8")
    manifest = {"schema": SCHEMA, "contract": "contract.md", "scenarios": "scenarios.md",
        "inputs": ["impl.py", "check.py"], "implementation": ["impl.py"], "passports": [{
        "clause": "C-1.1", "pin": contract.by_id("C-1.1").version, "specs": ["S1.1"],
        "intent_source": "activation fixture", "owner_decision": "engineering control",
        "input_domain": "integers", "observable_outcome": "one copy", "oracle_source": "cardinality",
        "assumptions": [], "undefined_behavior": [], "known_gaps": [], "variants": [
        {"id": "alternative", "kind": "valid", "reason": "accepted alternative", "files": {"impl.py": "valid"}},
        {"id": "duplicate", "kind": "violation", "reason": "retains duplicates",
         "files": {"impl.py": "violation"}, "activation": "python activation.py"}]}]}
    def save():
        (root / "trust.json").write_text(json.dumps(manifest), encoding="utf-8")
    save()
    return manifest, save


def activated(cid):
    if cid == "C-1.1":
        return summarize(())["score"] is not None
    if cid == "C-1.2":
        return build(mutation={**summarize(()), "blocking": True}, allow_partial=True)["passed"]
    if cid == "C-1.3":
        return mutant(lambda cmd: Outcome("TOOL_ERROR", 124))[0]["killed"]
    if cid == "C-1.4":
        return mutant(lambda cmd: Outcome("ASSERTION_FAIL", 1), verify_baseline=True)[0]["killed"]
    if cid == "C-1.5":
        rows = [{"path": "x.py", "line": 2, "kind": "flip", "status": "tool_error", "killed": False}]
        return clause_scores(rows, {"C-1": {"x.py": [2]}})["C-1"]["score"] is not None
    if cid == "C-1.6":
        rows = [{"path": "x.py", "line": 2, "kind": "flip", "status": "killed",
                 "killed": True, "witness_clauses": ["C-1"]}]
        return clause_scores(rows, {"C-2": {"x.py": [2]}})["C-2"]["score"] is not None
    if cid == "C-1.7":
        return summarize(mutant(lambda cmd: 1, max_mutants=1))["state"] == "PASS"
    if cid == "C-2.6":
        def tamper(cmd, cwd, **kw):
            (pathlib.Path(cwd) / "check.py").write_text("changed", encoding="utf-8")
            return Outcome("PASS", 0)
        return execute({"check.py": b"original"}, {}, "check", timeout=1, runner=tamper)["status"] == "PASS"
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        m, save = fixture(root)
        if cid == "C-2.1":
            m["passports"][0]["pin"] = "0" * 16
            save()
            try:
                prepare(tmp, "trust.json")
            except ValueError:
                return False
            return True
        def runner(cmd, cwd, **kw):
            source = (pathlib.Path(cwd) / "impl.py").read_text()
            if cmd == "python activation.py":
                if source != 'violation':
                    return Outcome('ASSERTION_FAIL', 1)
                return Outcome("TOOL_ERROR", 127) if cid == "C-2.4" else Outcome("PASS", 0)
            return Outcome("ASSERTION_FAIL", 1) if source == "violation" or cid == "C-2.3" and source == "valid" else Outcome("PASS", 0)
        if cid == "C-2.8":
            m["passports"][0]["variants"] = m["passports"][0]["variants"][:1]
            save()
        r = audit(tmp, "trust.json", runner=runner)
        if cid in ("C-2.3", "C-2.8"):
            return r["state"] == "PASS"
        if cid == "C-2.4":
            return r["clauses"][0]["challenges"][1]["state"] == "PASS"
    raise ValueError(f"unknown probe {cid}")


if __name__ == "__main__":
    found = activated(sys.argv[1])
    print("violation activated" if found else "violation not observed")
    raise SystemExit(0 if found else 1)
