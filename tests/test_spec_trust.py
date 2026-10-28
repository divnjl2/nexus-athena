"""Executable obligations for features/spec-trust. No Git, models or live services."""
from __future__ import annotations

import copy
import json
import pathlib

import pytest

from lib.check import build
from lib.contract import parse as parse_contract, pin_scenarios
from lib.mutation import hunt, summarize
from lib.spec_trust import SCHEMA, audit, check_evidence, execute, prepare
from lib.verification import Outcome, junit_outcome, run_command


def test_no_decisions_have_no_score():
    """C-1.1 - the verifier distinguishes observations from absent or invalid evidence."""
    for rows in ((), ({"status": "unowned", "killed": False},),
                 ({"status": "undetermined", "killed": False},),
                 ({"status": "tool_error", "killed": False},)):
        report = summarize(rows)
        assert report["score"] is None and report["evaluated"] == 0
        assert report["state"] == "INCOMPLETE"
    mixed = summarize(({"status": "killed", "killed": True},
                       {"status": "undetermined", "killed": False}))
    assert mixed["score"] == 1.0 and mixed["state"] == "INCOMPLETE"


def test_missing_mutation_evidence_is_incomplete():
    """C-1.2 - the verifier distinguishes observations from absent or invalid evidence."""
    report = build(mutation={**summarize(()), "blocking": True}, allow_partial=True)
    assert not report["passed"] and report["legs"]["code_to_specs"] == "incomplete"
    assert "mutation" not in report["failed"]
    idle = build(mutation={"state": "NOT_REQUIRED", "blocking": True}, allow_partial=True)
    assert idle["passed"]


def _hunt(runner, **kwargs):
    return hunt({"clauses": {"C-1": {"x.py": [2]}}}, {"S1": ("C-1", "check")},
                {"x.py": {"source": "def f(a):\n    return a == 1\n", "lines": [2]}},
                runner=runner, writer=lambda p, s: None, **kwargs)


def test_tool_errors_are_not_kills():
    """C-1.3 - the verifier distinguishes observations from absent or invalid evidence."""
    for code in (2, 5, 124, 127):
        row = _hunt(lambda cmd: Outcome("TOOL_ERROR", code))[0]
        assert not row["killed"] and row["status"] == "tool_error"
    for xml in ("", '<testsuite><testcase><skipped/></testcase></testsuite>',
                '<testsuite><testcase><error/></testcase></testsuite>'):
        assert junit_outcome(1, xml).status == "TOOL_ERROR"
    assert junit_outcome(1, '<testsuite><testcase><failure message="AssertionError"/></testcase></testsuite>').status == "ASSERTION_FAIL"
    assert junit_outcome(1, '<testsuite><testcase><failure message="ImportError"/></testcase></testsuite>').status == "TOOL_ERROR"
    assert junit_outcome(1, '<testsuite><testcase><failure message="Failed: DID NOT RAISE ValueError"/></testcase></testsuite>').status == "ASSERTION_FAIL"
    assert junit_outcome(1, '<testsuite><testcase><failure message="RuntimeError: AssertionError: fake"/></testcase></testsuite>').status == "TOOL_ERROR"


def test_red_baseline_cannot_kill():
    """C-1.4 - the verifier distinguishes observations from absent or invalid evidence."""
    calls = []
    rows = _hunt(lambda cmd: calls.append(cmd) or Outcome("ASSERTION_FAIL", 1), verify_baseline=True)
    assert rows[0]["status"] == "baseline_error" and not rows[0]["killed"]
    assert calls == ["check"]
    sequence = iter((Outcome("PASS", 0), Outcome("ASSERTION_FAIL", 1)))
    assert _hunt(lambda cmd: next(sequence), verify_baseline=True)[0]["killed"]


def test_per_clause_scores_exclude_unknowns():
    """C-1.5 - the verifier distinguishes observations from absent or invalid evidence."""
    from lib.mutgate import clause_scores, mutation_verdict
    rows = [{"path": "x.py", "line": 2, "kind": "flip", "killed": False, "status": "tool_error"}]
    scores = clause_scores(rows, {"C-1": {"x.py": [2]}})
    assert scores["C-1"]["score"] is None and scores["C-1"]["survivors"] == []
    v = mutation_verdict(scores, 0.7, {"x.py": [2]})
    assert not v["ok"] and v["state"] == "INCOMPLETE"


def test_a_shared_line_kill_is_not_evidence_for_every_clause():
    """C-1.6 - the verifier distinguishes observations from absent or invalid evidence."""
    from lib.mutgate import clause_scores
    result = {"path": "x.py", "line": 2, "kind": "flip", "killed": True,
              "status": "killed", "witness_clauses": ["C-1"]}
    scores = clause_scores([result], {"C-1": {"x.py": [2]}, "C-2": {"x.py": [2]}})
    assert scores["C-1"]["score"] == 1.0 and scores["C-2"]["score"] is None
    assert scores["C-2"]["inconclusive"][0]["status"] == "not_witnessed"


def test_a_capped_sweep_has_only_scoped_score():
    """C-1.7 - the verifier distinguishes observations from absent or invalid evidence."""
    source = "def f(x):\n    return x == 1 and x != 2\n"
    rows = hunt({"clauses": {"C-1": {"x.py": [2]}}}, {"S1": ("C-1", "check")},
                {"x.py": {"source": source, "lines": [2]}}, runner=lambda c: 1,
                writer=lambda p, s: None, max_mutants=1, limit_per_line=10)
    report = summarize(rows)
    assert report["score"] == 1.0 and report["state"] == "INCOMPLETE" and report["budget_exhausted"]
    from lib.refinery import mutation_stage
    verdict = mutation_stage({"x.py": [2]}, {"clauses": {"C-1": {"x.py": [2]}}}, list(rows))
    assert not verdict["ok"] and verdict["state"] == "INCOMPLETE"
    empty = mutation_stage({"x.py": [2]}, {"clauses": {"C-1": {"x.py": [2]}}}, [])
    assert not empty["ok"] and empty["state"] == "INCOMPLETE"
    selected = hunt({"clauses": {"C-1": {"x.py": [2]}}}, {"S1": ("C-1", "check")},
                    {"x.py": {"source": source, "lines": [2]}}, runner=lambda c: 1,
                    writer=lambda p, s: None, max_mutants=1, limit_per_line=1)
    assert summarize(selected)["state"] == "PASS", "an explicit selector is not a truncated budget"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "impl.py").write_text("def unique(xs):\n    return list(dict.fromkeys(xs))\n", encoding="utf-8")
    (tmp_path / "test_spec.py").write_text(
        "from impl import unique\ndef test_unique():\n    assert set(unique([1,1,2])) == {1,2}\n"
        "    assert len(unique([1,1,2])) == 2\n", encoding="utf-8")
    (tmp_path / "activation.py").write_text(
        "from impl import unique\ndef test_activation():\n    assert len(unique([1,1,2])) == 3\n", encoding="utf-8")
    contract = "# Contract\n- **C-1.1** — WHEN values repeat THE SYSTEM SHALL return each distinct value once.\n"
    (tmp_path / "contract.md").write_text(contract, encoding="utf-8")
    c = parse_contract(contract)
    scenarios = "### S1.1 — unique\n- **verifies:** C-1.1\n- **run_cmd:** `python -m pytest test_spec.py -q`\n"
    (tmp_path / "scenarios.md").write_text(pin_scenarios(scenarios, c)[0], encoding="utf-8")
    m = {"schema": SCHEMA, "contract": "contract.md", "scenarios": "scenarios.md",
         "inputs": ["impl.py", "test_spec.py", "activation.py"], "implementation": ["impl.py"],
         "passports": [{"clause": "C-1.1", "pin": c.by_id("C-1.1").version,
             "intent_source": "fixture rule", "owner_decision": "fixture: order is unspecified",
             "input_domain": "lists of integers", "observable_outcome": "each value occurs once",
             "oracle_source": "set membership and cardinality", "assumptions": [],
             "undefined_behavior": [], "known_gaps": [], "specs": ["S1.1"], "variants": [
                 {"id": "set", "kind": "valid", "reason": "order is unspecified",
                  "files": {"impl.py": "def unique(xs):\n    return list(set(xs))\n"}},
                 {"id": "duplicate", "kind": "violation", "reason": "retains duplicate values",
                  "activation": "python -m pytest activation.py -q",
                  "files": {"impl.py": "def unique(xs):\n    return xs\n"}}]}]}
    def save(value=m):
        (tmp_path / "trust.json").write_text(json.dumps(value), encoding="utf-8")
    save()
    return tmp_path, m, save


def test_manifest_pins_are_enforced(project):
    """C-2.1 - the verifier distinguishes observations from absent or invalid evidence."""
    root, m, save = project
    assert prepare(str(root), "trust.json")[0] == m
    m["passports"][0]["pin"] = "0" * 16
    save()
    with pytest.raises(ValueError, match="stale"):
        prepare(str(root), "trust.json")


def test_valid_and_violation_controls_run(project):
    """C-2.2 - the verifier distinguishes observations from absent or invalid evidence."""
    root, _, _ = project
    report = audit(str(root), "trust.json")
    assert report["state"] == "PASS"
    row = report["clauses"][0]
    assert row["controls"] == {"valid": 1, "violation": 1}
    assert [v["state"] for v in row["challenges"]] == ["PASS", "PASS"]
    assert row["challenges"][1]["activation"]["status"] == "PASS"
    assert row["challenges"][1]["activation_baseline"]["status"] == "ASSERTION_FAIL"
    assert row["challenges"][1]["checks"][0]["status"] == "ASSERTION_FAIL"
    assert "dict.fromkeys" in (root / "impl.py").read_text()


def test_bad_oracles_fail_in_both_directions(project):
    """C-2.3 - the verifier distinguishes observations from absent or invalid evidence."""
    root, _, _ = project
    def weak(cmd, **kw):
        return Outcome("PASS", 0)
    assert audit(str(root), "trust.json", runner=weak)["state"] == "FAIL"
    def too_strict(cmd, cwd, **kw):
        source = (pathlib.Path(cwd) / "impl.py").read_text()
        return Outcome("ASSERTION_FAIL", 1) if "list(set" in source else Outcome("PASS", 0)
    rep = audit(str(root), "trust.json", runner=too_strict)
    assert rep["clauses"][0]["challenges"][0]["state"] == "FAIL"


def test_activation_and_tool_errors_are_inconclusive(project):
    """C-2.4 - the verifier distinguishes observations from absent or invalid evidence."""
    root, _, _ = project
    def inactive(cmd, cwd, **kw):
        if cmd == "python -m pytest activation.py -q":
            source = (pathlib.Path(cwd) / 'impl.py').read_text()
            return Outcome('TOOL_ERROR', 127) if 'return xs' in source else Outcome('ASSERTION_FAIL', 1)
        return Outcome('PASS', 0)
    rep = audit(str(root), "trust.json", runner=inactive)
    assert rep["state"] == "INCOMPLETE"
    assert rep["clauses"][0]["challenges"][1]["checks"] == []
    def broken_baseline(cmd, **kw):
        return Outcome('TOOL_ERROR', 127) if cmd == 'python -m pytest activation.py -q' else Outcome('PASS', 0)
    assert audit(str(root), 'trust.json', runner=broken_baseline)['state'] == 'INCOMPLETE'


def test_only_implementation_overlays_are_admitted(project):
    """C-2.5 - the verifier distinguishes observations from absent or invalid evidence."""
    root, m, save = project
    for path in ("test_spec.py", "../escape.py", "/absolute.py", "C:/escape.py", "x\\y.py"):
        changed = copy.deepcopy(m)
        changed["passports"][0]["variants"][0]["files"] = {path: "pass"}
        save(changed)
        with pytest.raises(ValueError):
            prepare(str(root), "trust.json")


def test_protected_input_changes_reject_evidence():
    """C-2.6 - the verifier distinguishes observations from absent or invalid evidence."""
    def tamper(cmd, cwd, **kw):
        (pathlib.Path(cwd) / "test_spec.py").write_text("pass")
        return Outcome("PASS", 0)
    result = execute({"test_spec.py": b"assert False"}, {}, "check", timeout=1, runner=tamper)
    assert result["status"] == "INTEGRITY_FAIL"


def test_context_covers_inputs_manifest_and_environment(project):
    """C-2.7 - the verifier distinguishes observations from absent or invalid evidence."""
    root, m, save = project
    context = prepare(str(root), "trust.json")[2]
    assert context["inputs"]["impl.py"] and context["environment"]["interpreter_digest"]
    assert "environment_digest" in context["environment"] and "PATH" not in context["environment"]
    (root / "impl.py").write_text("changed")
    assert prepare(str(root), "trust.json")[2] != context
    m["passports"][0]["variants"][0]["reason"] = "changed rationale"
    save()
    assert prepare(str(root), "trust.json")[2]["manifest"] != context["manifest"]


def test_missing_controls_and_gaps_remain_incomplete(project):
    """C-2.8 - the verifier distinguishes observations from absent or invalid evidence."""
    root, m, save = project
    m["passports"][0]["variants"] = m["passports"][0]["variants"][:1]
    save()
    assert audit(str(root), "trust.json", runner=lambda *a, **k: Outcome("PASS", 0))["state"] == "INCOMPLETE"
    m["passports"][0]["known_gaps"] = ["concurrent callers not evaluated"]
    save()
    rep = audit(str(root), "trust.json", runner=lambda *a, **k: Outcome("PASS", 0))
    assert rep["clauses"][0]["known_gaps"]


def test_requested_receipt_must_be_current_and_for_this_contract(project):
    """C-2.9 - the verifier distinguishes observations from absent or invalid evidence."""
    root, _, _ = project
    report = audit(str(root), "trust.json")
    assert check_evidence(str(root), "trust.json", report)["state"] == "PASS"
    assert check_evidence(str(root), "trust.json", report, contract_path=str(root / "other.md"))["state"] == "FAIL"
    inconsistent = {**report, "clauses": [{"clause": "C-1.1", "state": "FAIL"}]}
    assert check_evidence(str(root), "trust.json", inconsistent)["state"] == "FAIL"
    (root / "test_spec.py").write_text("# changed verifier")
    assert check_evidence(str(root), "trust.json", report)["state"] == "FAIL"


def test_runner_detects_real_collection_skips_and_timeout(tmp_path):
    (tmp_path / "test_case.py").write_text("import pytest\ndef test_it():\n    pytest.skip('no evidence')\n")
    assert run_command("python -m pytest test_case.py -q", cwd=str(tmp_path)).status == "TOOL_ERROR"
    (tmp_path / "test_case.py").write_text("invalid python syntax !!!")
    assert run_command("python -m pytest test_case.py -q", cwd=str(tmp_path)).status == "TOOL_ERROR"
    (tmp_path / "wait.py").write_text("import time\ntime.sleep(10)")
    result = run_command("python wait.py", cwd=str(tmp_path), timeout=1)
    assert result.status == "TOOL_ERROR" and result.exit_code == 124


def test_cli_and_check_integration(project, capsys):
    import athena
    root, _, _ = project
    receipt = root / "receipt.json"
    args = athena.build_parser().parse_args(["trust", "trust.json", "--cwd", str(root), "-o", str(receipt)])
    assert args.fn(args) == 0 and json.loads(receipt.read_text())["passed"]
    capsys.readouterr()
    args = athena.build_parser().parse_args(["check", str(root / "contract.md"), "--cwd", str(root),
        "--trust", "trust.json", "--trust-evidence", str(receipt), "--allow-partial", "--purl", ""])
    rep = athena._check_report(args)
    assert next(s for s in rep["steps"] if s["step"] == "spec.trust")["ok"]
    receipt.unlink()
    rep = athena._check_report(args)
    assert "spec.trust" in rep["failed"]


def test_pilot_probes_do_not_activate_clean_code():
    import runpy
    path = pathlib.Path(__file__).resolve().parents[1] / "features/spec-trust/pilot/activate.py"
    probe = runpy.run_path(str(path))["activated"]
    ids = [f"C-1.{i}" for i in range(1, 8)] + ["C-2.1", "C-2.3", "C-2.4", "C-2.6", "C-2.8"]
    assert all(probe(cid) is False for cid in ids)


def test_activation_probe_must_discriminate_clean_baseline(project):
    """C-2.11 - the constant probe fails and the real predicate has typed negative and positive evidence."""
    root, _, _ = project
    (root / 'activation.py').write_text('def test_activation():\n    assert True\n', encoding='utf-8')
    result = audit(str(root), 'trust.json')
    challenge = result['clauses'][0]['challenges'][1]
    assert result['state'] == 'FAIL'
    assert challenge['activation_baseline']['status'] == 'PASS'
    assert challenge['state'] == 'FAIL' and challenge['checks'] == []
    assert 'activation' not in challenge


def test_receipt_ignores_tool_trace_but_tracks_runtime_settings(project, monkeypatch):
    """C-2.12 - the receipt remains current, but changing a runtime setting changes its fingerprint."""
    from lib.verification import execution_environment
    root, _, _ = project
    monkeypatch.setenv('CODEX_TOOL_CALL_ID', 'first-call')
    first = prepare(str(root), 'trust.json')[2]
    monkeypatch.setenv('CODEX_TOOL_CALL_ID', 'next-call')
    assert prepare(str(root), 'trust.json')[2] == first
    assert 'CODEX_TOOL_CALL_ID' not in execution_environment()
    monkeypatch.setenv('ATHENA_TEST_RUNTIME_SETTING', 'changed')
    assert prepare(str(root), 'trust.json')[2] != first


def test_mutate_cli_does_not_succeed_on_empty_evidence(project, monkeypatch, capsys):
    import athena
    root, _, _ = project
    monkeypatch.chdir(root)
    (root / "map.json").write_text(json.dumps({"clauses": {"C-1.1": {"impl.py": [2]}}}))
    args = athena.build_parser().parse_args(["mutate", "contract.md", "--map", "map.json",
        "--source", "impl.py", "--mirror", str(root.parent / "mutate-mirror")])
    assert args.fn(args) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["score"] is None and output["state"] == "INCOMPLETE"


def test_spec_runner_uses_the_verifier_interpreter(monkeypatch):
    """C-2.10 - the process boundary chooses the verifier's current interpreter."""
    import sys
    from types import SimpleNamespace
    from lib.spec_runner import _spawn
    seen = []
    def process(argv, **kwargs):
        seen.append(argv)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")
    monkeypatch.setattr("lib.spec_runner.subprocess.run", process)
    for binary in ("python", "python3", "python.exe", "pytest"):
        assert _spawn([binary, "test.py"], cwd=".", timeout=1)[0] == 0
        assert seen[-1][0] == sys.executable
    assert seen[-1][1:3] == ["-m", "pytest"]
