"""Perimeter layer, C-3: scan and policy as stages of the merge queue. Red until lib/scan.py exists."""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_the_scan_stage_is_planned_from_the_changed_files_and_refuses_on_a_finding():
    """C-3.1 — Bandit for Python files, gitleaks over the diff whenever anything changed, pip-audit
    when a requirements file changed, nothing for nothing; the stage refuses at or above the
    threshold naming the finding and passes below it."""
    from lib.scan import scan_plan, scan_stage
    plan = scan_plan(["lib/a.py", "docs/x.md", "requirements.txt"], diff_ref="master...HEAD")
    tools = [p["tool"] for p in plan]
    assert tools.count("bandit") == 1 and tools.count("gitleaks") == 1 and tools.count("pip-audit") == 1
    bandit = next(p for p in plan if p["tool"] == "bandit")
    assert bandit["files"] == ["lib/a.py"] and "lib/a.py" in bandit["argv"] and "docs/x.md" not in bandit["argv"]
    assert "master...HEAD" in " ".join(next(p for p in plan if p["tool"] == "gitleaks")["argv"])
    assert "requirements.txt" in next(p for p in plan if p["tool"] == "pip-audit")["argv"]
    assert scan_plan([]) == [] and [p["tool"] for p in scan_plan(["docs/x.md"])] == ["gitleaks"]
    # review 29.09 (the first landing planned gitleaks only for Markdown, bandit with `-o json` and a 2,000-entry
    # `-t` list, pip-audit as `pip audit`): the argv must be the tool's own grammar, and gitleaks runs for ANY change
    assert [p["tool"] for p in scan_plan(["lib/a.py"])] == ["bandit", "gitleaks"]
    assert bandit["argv"][0] == "bandit" and "-f" in bandit["argv"] and "json" in bandit["argv"] and len(bandit["argv"]) <= 12
    assert "-t" not in bandit["argv"] and "-o" not in bandit["argv"]
    leaks = next(p for p in scan_plan(["lib/a.py"], diff_ref="master...HEAD") if p["tool"] == "gitleaks")
    assert leaks["argv"][0] == "gitleaks" and "json" in " ".join(leaks["argv"]) and len(leaks["argv"]) <= 12
    assert any(a.startswith("--log-opts") for a in leaks["argv"]) or leaks["argv"][1] == "git"
    audit = next(p for p in scan_plan(["requirements.txt"]) if p["tool"] == "pip-audit")
    assert audit["argv"][0] == "pip-audit" and "-r" in audit["argv"] and "json" in " ".join(audit["argv"])
    high = json.dumps({"results": [{"filename": "lib/a.py", "line_number": 3, "issue_severity": "HIGH", "test_id": "B602", "issue_text": "shell=True"}]})
    low = json.dumps({"results": [{"filename": "lib/a.py", "line_number": 3, "issue_severity": "LOW", "test_id": "B404", "issue_text": "import subprocess"}]})

    def run_high(argv):
        return (1, high) if argv[0] == "bandit" else (0, "[]")

    def run_low(argv):
        return (1, low) if argv[0] == "bandit" else (0, "[]")
    red = scan_stage(["lib/a.py"], run_high, threshold="warning")
    assert red["ok"] is False and "B602" in red["reason"] and "lib/a.py:3" in red["reason"] and red["stage"] == "scan"
    green = scan_stage(["lib/a.py"], run_low, threshold="warning")
    assert green["ok"] is True and green["findings"] and green["stage"] == "scan"
    # a scanner that is missing is not a finding: the stage says so and does not refuse on silence
    missing = scan_stage(["lib/a.py"], lambda argv: (127, "not found"), threshold="warning")
    assert missing["ok"] is True and "unrun" in missing["reason"]
    # review 29.09: the stage runs the plan it was given the diff ref for, and a gitleaks finding is a leak
    # whatever the threshold — the first landing re-planned without the ref and never read gitleaks' output
    seen = []

    def run_leak(argv):
        seen.append(argv[0])
        if argv[0] == "gitleaks":
            return (1, json.dumps([{"RuleID": "generic-api-key", "File": "lib/a.py", "StartLine": 7, "Secret": "sk-…"}]))
        return (0, json.dumps({"results": []}))
    leaked = scan_stage(["lib/a.py"], run_leak, threshold="error", diff_ref="master...HEAD")
    assert leaked["ok"] is False and leaked["stage"] == "scan" and "generic-api-key" in leaked["reason"] and "lib/a.py:7" in leaked["reason"]
    assert "gitleaks" in seen and "bandit" in seen
    clean = scan_stage(["lib/a.py"], lambda argv: (0, "[]" if argv[0] == "gitleaks" else json.dumps({"results": []})), threshold="warning", diff_ref="master...HEAD")
    assert clean["ok"] is True and clean["stage"] == "scan" and clean.get("findings") == []


def test_the_policy_input_is_rendered_and_conftest_evaluates_the_rego_policies():
    """C-3.2 — the input carries the record, the changed paths and the stages seen; conftest over the
    layer's policies (which name this clause) passes a complete input and denies the three
    incomplete ones by message; without conftest the spec is skipped. conftest 0.70 runs OPA 1.x, so
    the policy is Rego v1: `package main`, `deny contains msg if { ... }`, helper rules with `if`;
    the v0 form `deny[msg] { ... }` is a parse error there."""
    from lib.scan import conftest_command, policy_input
    policy_dir = ROOT / "features" / "perimeter-layer" / "policy"
    rego = policy_dir / "merge.rego"
    assert rego.exists() and "C-3.2" in rego.read_text(encoding="utf-8")
    rec = {"schema": "athena.merge/1", "task": "T1", "executor": "pi-omni9", "stage": "policy", "ok": True, "reason": ""}
    good = policy_input(rec, changed=["lib/a.py"], stages=["admit", "rebase", "check", "scan", "mutation"], last_dispatch={"provenance": {"model": {"id": "x"}}})
    assert good["record"] == rec and good["changed"] == ["lib/a.py"] and "mutation" in good["stages"] and good["provenance_present"] is True
    assert policy_input(rec, changed=[], stages=[], last_dispatch=None)["provenance_present"] is False
    conftest = shutil.which("conftest")
    if not conftest:
        pytest.skip("conftest is not installed: winget install OpenPolicyAgent.Conftest")
    cases = {
        "good": (good, True, ""),
        "no_provenance": (policy_input(rec, changed=["lib/a.py"], stages=["check", "mutation"], last_dispatch=None), False, "provenance"),
        "sealed": (policy_input(rec, changed=["features/x/sealed/test_s.py"], stages=["check", "mutation"], last_dispatch={"provenance": {"a": 1}}), False, "sealed"),
        "no_mutation": (policy_input(rec, changed=["lib/a.py"], stages=["check"], last_dispatch={"provenance": {"a": 1}}), False, "mutation"),
    }
    with tempfile.TemporaryDirectory() as td:
        for name, (inp, expect_ok, word) in cases.items():
            path = pathlib.Path(td) / f"{name}.json"
            path.write_text(json.dumps(inp), encoding="utf-8")
            argv = conftest_command(str(path), str(policy_dir), conftest=conftest)
            p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(ROOT))
            out = (p.stdout or "") + (p.stderr or "")
            assert (p.returncode == 0) is expect_ok, f"{name}: exit {p.returncode}: {out[-400:]}"
            if not expect_ok:
                assert word in out.lower(), f"{name}: the denial does not name {word}: {out[-400:]}"


def test_the_queue_runs_scan_after_check_and_policy_before_fast_forward():
    """C-3.3 — the stages in order, and the flags that skip scan and policy are explicit on
    `athena merge`."""
    from lib.refinery import STAGES
    assert STAGES == ("admit", "rebase", "check", "scan", "mutation", "policy", "fast-forward")
    p = subprocess.run([sys.executable, str(ROOT / "athena.py"), "merge", "-h"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    assert "--no-scan" in p.stdout and "--no-policy" in p.stdout and "--scan-threshold" in p.stdout


def test_a_models_review_rides_in_the_merge_record_and_never_refuses():
    """C-3.4 — a review attached to a merge record leaves ok as it was, adds the text and the
    reviewer's provenance under review, and is advisory."""
    from lib.scan import attach_review
    rec = {"schema": "athena.merge/1", "task": "T1", "executor": "pi-omni9", "stage": "fast-forward", "ok": True, "reason": ""}
    prov = {"model": {"id": "omnicoder-9b"}, "runtime": {"name": "vllm", "version": "0.21.0"}}
    out = attach_review(rec, "the reason string is long; consider a constant", prov)
    assert out["ok"] is True and out["review"]["text"].startswith("the reason") and out["review"]["provenance"] == prov and out["review"]["advisory"] is True
    # review 29.09 (the first landing returned a fresh dict with stage "merge" and an empty reason): the review
    # RIDES IN the record — every field of the record survives, only `review` is added
    assert all(out.get(k) == v for k, v in rec.items()) and set(out) == set(rec) | {"review"}
    refused = attach_review({**rec, "ok": False, "reason": "check red"}, "looks fine to me", prov)
    assert refused["ok"] is False and refused["reason"] == "check red"
    assert rec.get("review") is None   # the input is not mutated
