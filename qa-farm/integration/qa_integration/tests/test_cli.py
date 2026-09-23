"""Proves the CLI handles work end-to-end (the service 'ручки')."""
import json

from qa_integration.cli import main

BOUNDARY_MAP = {"boundary_a": ["service_a/"]}


def test_gate_blocks_on_low_boundary_coverage(tmp_path, capsys):
    xml = tmp_path / "cov.xml"
    xml.write_text(
        '<coverage><packages><package><classes>'
        '<class filename="service_a/h.py"><lines>'
        '<line number="1" hits="0"/><line number="2" hits="0"/>'
        '</lines></class></classes></package></packages></coverage>', encoding="utf-8")
    bmap = tmp_path / "bmap.json"
    bmap.write_text(json.dumps(BOUNDARY_MAP), encoding="utf-8")
    code = main(["gate", "--coverage", str(xml), "--boundary-map", str(bmap)])
    out = json.loads(capsys.readouterr().out)
    assert code != 0
    assert out["passed"] is False and out["failing_boundary"] == "boundary_a"


def test_gate_passes_on_good_boundary_coverage(tmp_path, capsys):
    xml = tmp_path / "cov.xml"
    xml.write_text(
        '<coverage><packages><package><classes>'
        '<class filename="service_a/h.py"><lines>'
        '<line number="1" hits="1"/><line number="2" hits="1"/>'
        '</lines></class></classes></package></packages></coverage>', encoding="utf-8")
    bmap = tmp_path / "bmap.json"
    bmap.write_text(json.dumps(BOUNDARY_MAP), encoding="utf-8")
    code = main(["gate", "--coverage", str(xml), "--boundary-map", str(bmap)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["passed"] is True


def test_select_reports_no_relevant_change(tmp_path, capsys):
    bmap = tmp_path / "bmap.json"
    bmap.write_text(json.dumps(BOUNDARY_MAP), encoding="utf-8")
    main(["select", "--changed", "README.md", "--boundary-map", str(bmap)])
    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "no_relevant_change" and out["tests"] == []


def test_manifest_lists_hitl_points(capsys):
    main(["manifest"])
    ids = {p["id"] for p in json.loads(capsys.readouterr().out)["hitl"]}
    assert "approve-environment-fix" in ids


def test_version(capsys):
    main(["version"])
    assert "qa_integration" in json.loads(capsys.readouterr().out)


def test_gate_malformed_xml_is_clean_error(tmp_path, capsys):
    xml = tmp_path / "bad.xml"
    xml.write_text("<coverage line-rate=", encoding="utf-8")   # truncated / not well-formed
    code = main(["gate", "--coverage", str(xml)])
    out = json.loads(capsys.readouterr().out)
    assert code == 2 and "error" in out          # clean structured error, not a traceback


def test_gate_missing_file_is_clean_error(tmp_path, capsys):
    code = main(["gate", "--coverage", str(tmp_path / "nope.xml")])
    out = json.loads(capsys.readouterr().out)
    assert code == 2 and "not found" in out["error"]
