"""Generate reviewer-readable semantic variants from exact source anchors, without Git.

The output is derived. Rebuild after source changes; review the manifest before accepting
its results. This engineering pilot is not an independently labelled external benchmark.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lib.contract import parse
from lib.scenario_parser import parse as scenarios
from lib.spec_trust import SCHEMA

ROOT = pathlib.Path(__file__).resolve().parents[1]


def build():
    rules = [
        ("C-1.1", "lib/mutation.py", "if decided else None", "if decided else 1.0"),
        ("C-1.2", "lib/check.py", "evaluated > 0 and not inconclusive and ", ""),
        ("C-1.3", "lib/mutation.py", 'if result.status == "ASSERTION_FAIL":', 'if result.status != "PASS":'),
        ("C-1.4", "lib/mutation.py", "if verify_baseline:", "if False and verify_baseline:"),
        ("C-1.5", "lib/mutgate.py", 'if state not in ("killed", "survived"):', 'if False and state not in ("killed", "survived"):'),
        ("C-1.6", "lib/mutgate.py", 'if mutant["killed"] and "witness_clauses" in mutant and clause_id not in mutant["witness_clauses"]:', 'if False and mutant["killed"] and "witness_clauses" in mutant and clause_id not in mutant["witness_clauses"]:'),
        ("C-1.7", "lib/mutation.py", 'results[0]["budget_exhausted"] = True', 'results[0]["budget_exhausted"] = False'),
        ("C-2.1", "lib/spec_trust.py", 'or p.get("pin") != c.version', 'or False'),
        ("C-2.3", "lib/spec_trust.py", 'row["state"] = "PASS" if all(s == "PASS" for s in states) else "FAIL"', 'row["state"] = "PASS"'),
        ("C-2.4", "lib/spec_trust.py", 'activated = row["activation"]["status"] == "PASS"', 'activated = True'),
        ("C-2.6", "lib/spec_trust.py", 'if changed:', 'if False and changed:'),
        ("C-2.8", "lib/spec_trust.py", 'or not all(controls.values())', 'or False'),
    ]
    alternatives = {
        "lib/mutation.py": ('sum(1 for r in results if status_of(r) == "killed")', 'len([r for r in results if status_of(r) == "killed"])'),
        "lib/check.py": ('"ok": bool(ok)', '"ok": not not ok'),
        "lib/mutgate.py": ('score = killed / total if total else None', 'score = (killed * 1.0) / total if total else None'),
        "lib/spec_trust.py": ('hashlib.sha256(raw).hexdigest()', 'hashlib.new("sha256", raw).hexdigest()'),
    }
    contract_path = "features/spec-trust/contract.md"
    scenario_path = "features/spec-trust/scenarios.md"
    contract = parse((ROOT / contract_path).read_text(encoding="utf-8"))
    spec_by_clause = {s.requirement_key: s.id for s in scenarios((ROOT / scenario_path).read_text(encoding="utf-8"))}
    passports = []
    for cid, path, old, new in rules:
        source = (ROOT / path).read_text(encoding="utf-8")
        a, b = alternatives[path]
        if source.count(old) != 1 or source.count(a) != 1:
            raise ValueError(f"source moved; review pilot anchor for {cid}")
        passports.append({"clause": cid, "pin": contract.by_id(cid).version,
            "intent_source": contract_path + "#" + cid,
            "owner_decision": "Engineering proposal implementing the agreed trust plan; human semantic review remains required.",
            "input_domain": "The deterministic cases of the bound executable spec.",
            "observable_outcome": contract.by_id(cid).text,
            "oracle_source": "The normative clause plus a separately authored activation probe.",
            "assumptions": ["Trusted Python, pytest and reviewer-owned inputs; cooperative code, no hostile-process sandbox."],
            "undefined_behavior": ["Arbitrary malicious native code is outside this pilot."],
            "known_gaps": [], "specs": [spec_by_clause[cid]], "variants": [
                {"id": "equivalent-expression", "kind": "valid", "reason": "Equivalent expression preserves the declared result.",
                 "files": {path: source.replace(a, b)}},
                {"id": "semantic-violation", "kind": "violation", "reason": "Disable the boundary named by the clause.",
                 "activation": f"python -m pytest features/spec-trust/pilot/test_activation.py::test_violation_active[{cid}] -q",
                 "files": {path: source.replace(old, new)}}]})
    m = {"schema": SCHEMA, "contract": contract_path, "scenarios": scenario_path,
         "inputs": ["lib", "athena.py", "tests/test_spec_trust.py", "pytest.ini", "CORE.md",
                    "docs/adr/0010-spec-trust-is-separate-from-execution.md",
                    "features/spec-trust/pilot/activate.py", "features/spec-trust/pilot/test_activation.py", "tools/build_spec_trust_pilot.py"],
         "implementation": sorted(alternatives), "passports": passports}
    output = ROOT / "features/spec-trust/pilot/manifest.json"
    output.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(passports)} clause challenges in {output}")


if __name__ == "__main__":
    build()
