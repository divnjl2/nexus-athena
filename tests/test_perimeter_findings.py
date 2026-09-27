"""Perimeter layer, C-1: findings from outside oracles become verdicts. Red until lib/findings.py exists."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

VALE = json.dumps({"features/x/README.md": [
    {"Check": "Athena.NoEmoji", "Line": 3, "Message": "no emoji in the frame's documents", "Severity": "error", "Span": [1, 2], "Match": "x"},
    {"Check": "Athena.NoDoubleSpace", "Line": 9, "Message": "double space", "Severity": "warning", "Span": [4, 5], "Match": "  "},
    {"Check": "Vale.Spelling", "Line": 11, "Message": "spelling", "Severity": "suggestion", "Span": [1, 3], "Match": "teh"}]})
# review 27.09: the first landing keyed on the sample's file name; a second file with another name is the cure
VALE_TWO = json.dumps({"docs/research/a.md": [{"Check": "Athena.NoPlaceholder", "Line": 2, "Message": "TBD", "Severity": "error", "Span": [1, 3], "Match": "TBD"}],
                       "notes/b.md": [{"Check": "Athena.NoDoubleSpace", "Line": 5, "Message": "double space", "Severity": "warning", "Span": [1, 2], "Match": "  "}]})
BANDIT = json.dumps({"results": [
    {"filename": "lib/a.py", "line_number": 10, "issue_severity": "HIGH", "test_id": "B602", "issue_text": "subprocess call with shell=True"},
    {"filename": "lib/b.py", "line_number": 2, "issue_severity": "LOW", "test_id": "B404", "issue_text": "import subprocess"}]})
GITLEAKS = json.dumps([{"RuleID": "generic-api-key", "File": "cfg.py", "StartLine": 4, "Description": "Generic API Key", "Secret": "sk-…"}])
SEMGREP = json.dumps({"results": [{"check_id": "python.lang.security.audit.eval", "path": "lib/c.py", "start": {"line": 7},
                                    "extra": {"severity": "WARNING", "message": "eval used"}}]})


def _vale_binary() -> str:
    for c in (shutil.which("vale"), os.environ.get("ATHENA_VALE", ""), r"C:\ProgramData\athena\bin\vale.exe"):
        if c and pathlib.Path(c).exists():
            return c
    return ""


def test_findings_from_four_tools_are_read_into_one_shape():
    """C-1.1 — four JSON dialects, one shape: tool, path, line, severity in {info, warning, error},
    rule, message; malformed text yields nothing, never an exception."""
    from lib.findings import findings_from
    keys = {"tool", "path", "line", "severity", "rule", "message"}
    v = findings_from("vale", VALE)
    assert len(v) == 3 and all(keys <= set(f) for f in v)
    assert [f["severity"] for f in v] == ["error", "warning", "info"]
    assert v[0]["path"] == "features/x/README.md" and v[0]["line"] == 3 and v[0]["rule"] == "Athena.NoEmoji" and v[0]["tool"] == "vale"
    b = findings_from("bandit", BANDIT)
    assert [(f["path"], f["line"], f["severity"], f["rule"]) for f in b] == [("lib/a.py", 10, "error", "B602"), ("lib/b.py", 2, "info", "B404")]
    g = findings_from("gitleaks", GITLEAKS)
    assert g == [{"tool": "gitleaks", "path": "cfg.py", "line": 4, "severity": "error", "rule": "generic-api-key", "message": "Generic API Key"}]
    s = findings_from("semgrep", SEMGREP)
    assert s[0]["severity"] == "warning" and s[0]["line"] == 7 and s[0]["rule"].endswith("eval") and "eval" in s[0]["message"]
    two = findings_from("vale", VALE_TWO)
    assert sorted((f["path"], f["line"], f["severity"]) for f in two) == [("docs/research/a.md", 2, "error"), ("notes/b.md", 5, "warning")]
    assert findings_from("vale", "not json") == [] and findings_from("bandit", "") == [] and findings_from("unknown", VALE) == []
    # a finding the reader cannot place gets line 0
    assert findings_from("semgrep", json.dumps({"results": [{"check_id": "x", "path": "p", "extra": {"severity": "ERROR", "message": "m"}}]}))[0]["line"] == 0


def test_findings_are_judged_against_a_severity_threshold():
    """C-1.2 — red when any finding is at or above the threshold, the reason naming the worst with
    file and line; green below it with the count."""
    from lib.findings import findings_from, findings_verdict
    fs = findings_from("bandit", BANDIT)
    red = findings_verdict(fs, "warning")
    assert red["ok"] is False and red["worst"]["rule"] == "B602" and "lib/a.py:10" in red["reason"] and "B602" in red["reason"]
    green = findings_verdict(findings_from("vale", VALE)[2:], "warning")
    assert green["ok"] is True and green["count"] == 1 and "below warning" in green["reason"]
    assert findings_verdict([], "info")["ok"] is True and findings_verdict([], "info")["count"] == 0
    # at the threshold counts as red; the worst is the highest severity, not the first
    at = findings_verdict(findings_from("vale", VALE)[1:2], "warning")
    assert at["ok"] is False
    mixed = findings_verdict(list(reversed(findings_from("vale", VALE))), "error")
    assert mixed["ok"] is False and mixed["worst"]["severity"] == "error"


def test_a_missing_tool_leaves_the_clause_unrun_and_named():
    """C-1.3 — no binary: the clause is unrun (neither green nor red), the tool and an install hint
    are named; with the binary the oracle's command is rendered."""
    from lib.findings import oracle_status
    missing = oracle_status("vale", which=lambda name: None)
    assert missing["state"] == "unrun" and missing["ok"] is None and "vale" in missing["reason"] and "install" in missing["reason"].lower()
    for tool in ("vale", "bandit", "gitleaks", "semgrep", "conftest", "pip-audit"):
        assert oracle_status(tool, which=lambda name: None)["state"] == "unrun"
    ready = oracle_status("vale", which=lambda name: "C:/tools/vale.exe", target="docs", config="features/perimeter-layer/vale/.vale.ini")
    assert ready["state"] == "ready" and ready["command"][0] == "C:/tools/vale.exe" and "docs" in ready["command"]
    assert any(str(x).endswith(".vale.ini") for x in ready["command"]) and any("JSON" in str(x) for x in ready["command"])


def test_the_frames_documents_pass_the_prose_style_at_severity_error():
    """C-1.4 — Vale with the frame's style (the config names this clause) finds no error on the
    feature READMEs and the research digests; without vale the spec is skipped, never green."""
    from lib.findings import findings_from, findings_verdict
    cfg = ROOT / "features" / "perimeter-layer" / "vale" / ".vale.ini"
    assert cfg.exists() and "C-1.4" in cfg.read_text(encoding="utf-8")
    vale = _vale_binary()
    if not vale:
        pytest.skip("vale is not installed: winget install vale.vale (or set ATHENA_VALE)")
    import tempfile
    # review 27.09: the first landing was an invalid config that vale rejected with an empty output, and an
    # empty output read as "no findings"; the control document must trip all three rules first
    with tempfile.TemporaryDirectory() as td:
        control = pathlib.Path(td) / "control.md"
        control.write_text("# Control" + chr(10) + chr(10) + "A line with an emoji 😀 here." + chr(10)
                           + "This is TBD and a TODO." + chr(10) + "Two  spaces here." + chr(10), encoding="utf-8")
        c = subprocess.run([vale, "--config", str(cfg), "--output=JSON", "--minAlertLevel=suggestion", str(control)],
                           cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        assert c.stdout.strip().startswith("{"), "vale did not run the config: " + (c.stderr or c.stdout)[-300:]
        tripped = {f["rule"] for f in findings_from("vale", c.stdout)}
        assert {"Athena.NoEmoji", "Athena.NoPlaceholder", "Athena.NoDoubleSpace"} <= tripped, tripped
        assert all(f["severity"] == "error" for f in findings_from("vale", c.stdout) if f["rule"].startswith("Athena.")), "the frame's rules are errors"
    targets = [str(p) for p in sorted(ROOT.glob("features/*/README.md"))] + [str(p) for p in sorted((ROOT / "docs" / "research").glob("*.md"))]
    assert targets
    p = subprocess.run([vale, "--config", str(cfg), "--output=JSON", "--minAlertLevel=suggestion", *targets],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert p.stdout.strip().startswith("{"), "vale did not run the config on the documents: " + (p.stderr or p.stdout)[-300:]
    fs = findings_from("vale", p.stdout)
    v = findings_verdict(fs, "error")
    assert v["ok"] is True, v["reason"]


def test_a_judges_score_is_advisory_until_calibrated():
    """C-1.5 — the judge's record carries score and provenance and is advisory; only an agreement
    on at least twenty samples at or above the named level lets it refuse."""
    from lib.findings import judge_record
    prov = {"model": {"id": "omnicoder-9b"}, "runtime": {"name": "vllm", "version": "0.21.0"}}
    r = judge_record(0.4, prov)
    assert r["score"] == 0.4 and r["provenance"] == prov and r["advisory"] is True and r["can_refuse"] is False
    assert judge_record(0.4, prov, agreement=0.9, samples=12, required=0.8)["can_refuse"] is False
    assert judge_record(0.4, prov, agreement=0.7, samples=40, required=0.8)["can_refuse"] is False
    ok = judge_record(0.4, prov, agreement=0.85, samples=25, required=0.8)
    assert ok["can_refuse"] is True and ok["advisory"] is False and "25" in ok["reason"]
