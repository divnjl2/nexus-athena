"""Map freshness checks read verifier inputs without running the verifier.

The native collection is limited to a temporary pytest module. Subject inference is
forbidden and third-party pytest plugin discovery is disabled in its child process.
"""
from __future__ import annotations

import json
from pathlib import Path

from lib.ast import Scenario
from lib.clause_map import SpecLines, build, spec_digests
from lib.contract import parse as parse_contract
from lib.seams import seam_map_fresh


def test_check_rejects_changed_explicit_inputs_without_executing_and_refresh_repairs(
        tmp_path, monkeypatch, capsys):
    """C-9.34 — changed named bodies and config files require new observations."""
    import athena

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    def no_git(*args, **kwargs):
        raise AssertionError("Git subject inference is forbidden in this test")

    monkeypatch.setattr(athena, "_git_purl", no_git)
    contract_path = tmp_path / "contract.md"
    front = tmp_path / "plan.md"
    map_path = tmp_path / "map.json"
    config = tmp_path / "local.ini"
    test_file = tmp_path / "test_probe.py"
    contract_path.write_text(
        "# Contract: Map input freshness\n\n"
        "- **C-1.1** — WHEN requested THE SYSTEM SHALL return one.\n", encoding="utf-8")
    command = "python -m pytest test_probe.py::test_selected -c local.ini -q"
    (tmp_path / "scenarios.md").write_text(
        "# Scenarios\n\n### S1.1 — observe one\n"
        "- **verifies:** C-1.1\n"
        f"- **run_cmd:** `{command}`\n"
        "- **Given** an answer\n- **When** called\n- **Then** it is one\n",
        encoding="utf-8")
    front.write_text(
        "# Plan: Map input freshness\n\n## Phase 1: Observe\n"
        "**Goal:** Observe the answer.\n**Depends on:** none\n### Tasks\n"
        "- [ ] T1.1 Observe one\n"
        f"  - success_check: `{command}`\n"
        "  - files: `app.py`\n  - verifies: S1.1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("def answer():\n    return 1\n", encoding="utf-8")
    config.write_text("[pytest]\n", encoding="utf-8")
    original = (
        "from pathlib import Path\nimport app\n\n"
        "def test_selected():\n"
        "    with Path('executed.log').open('a') as log:\n"
        "        log.write('ran\\n')\n"
        "    assert app.answer() == 1\n")
    test_file.write_text(original, encoding="utf-8")
    parser = athena.build_parser()
    map_args = parser.parse_args([
        "contract", "map", str(contract_path), "--out", str(map_path),
        "--cwd", str(tmp_path), "--workdir", str(tmp_path / "coverage-work"),
        "--source", "app", "--jobs", "1", "--incremental",
        "--purl", "pkg:generic/map-input-check"])
    # argparse's default roots describe this repository; the fixture measures app only.
    map_args.source = ["app"]
    check_args = parser.parse_args([
        "--speckit", "off", "check", str(contract_path), "--front", str(front),
        "--map", str(map_path), "--cwd", str(tmp_path),
        "--purl", "pkg:generic/map-input-check"])
    seam_args = parser.parse_args([
        "--speckit", "off", "seam", "map_fresh", str(front), "--map", str(map_path),
        "--cwd", str(tmp_path)])

    def executions():
        return (tmp_path / "executed.log").read_text(encoding="utf-8").splitlines()

    def check_map(expected, issue="executable inputs"):
        before = executions()
        report = athena._check_report(check_args)
        step = next(row for row in report["steps"] if row["step"] == "seam.map_fresh")
        assert step["ok"] is expected, step
        capsys.readouterr()
        assert athena.cmd_seam(seam_args) == (0 if expected else 1)
        output = json.loads(capsys.readouterr().out)
        assert output["passed"] is expected
        if not expected:
            assert any(issue in text for text in step["detail"]["issues"])
            if issue == "executable inputs":
                assert any("S1.1" in text for text in step["detail"]["issues"])
        assert executions() == before, "freshness checking must not execute scenarios"

    assert athena.cmd_contract_map(map_args) == 0
    assert executions() == ["ran"]
    before_map = json.loads(map_path.read_text(encoding="utf-8"))
    assert before_map["spec_collected"] == {"S1.1": True}
    assert set(before_map["clauses"]["C-1.1"]) == {"app.py"}
    invoker = tmp_path / "invoker"
    invoker.mkdir()
    monkeypatch.chdir(invoker)
    check_map(True)

    # The verifier is not part of the measured app source. Only its explicit input
    # fingerprint can detect this change; contract/scenario/source-line pins stay put.
    test_file.write_text(original.replace("== 1", ">= 1"), encoding="utf-8")
    check_map(False)
    assert athena.cmd_contract_map(map_args) == 0
    assert executions() == ["ran", "ran"]
    check_map(True)

    config.write_text("[pytest]\naddopts = --strict-markers\n", encoding="utf-8")
    check_map(False)
    assert athena.cmd_contract_map(map_args) == 0
    assert executions() == ["ran", "ran", "ran"]
    check_map(True)

    # A named file disappearing must not be silently omitted from the current inputs.
    config.unlink()
    check_map(False)
    config.write_text("[pytest]\naddopts = --strict-markers\n", encoding="utf-8")
    check_map(True)

    # Identical files in another execution directory do not attest a run there.
    replica = tmp_path / "replica"
    replica.mkdir()
    for source in (test_file, config, tmp_path / "app.py"):
        (replica / source.name).write_bytes(source.read_bytes())
    check_args.cwd = seam_args.cwd = str(replica)
    check_map(False, issue="execution directory")
    assert not (replica / "executed.log").exists()
    map_args.cwd = str(replica)
    assert athena.cmd_contract_map(map_args) == 0
    assert (replica / "executed.log").read_text(encoding="utf-8").splitlines() == ["ran"]
    assert executions() == ["ran", "ran", "ran"]
    check_map(True)


def test_map_freshness_rejects_missing_legacy_input_pins_and_hashes_current_inputs():
    """A caller supplying current inputs cannot accept a legacy map without their pins."""
    contract = parse_contract(
        "# Contract: Input pins\n\n"
        "- **C-1.1** — WHEN requested THE SYSTEM SHALL return one.\n")
    scenario = Scenario("S1.1", "C-1.1", "", "python -m probe")
    before = spec_digests((scenario,), {"probe.py": "assert True\n"})
    changed = spec_digests((scenario,), {"probe.py": "assert False\n"})
    cmap = build((SpecLines("S1.1", "C-1.1", {}),),
                 contract_version=contract.version, spec_digests=before)
    good = seam_map_fresh(cmap, contract, (scenario,), spec_digests=before)
    stale = seam_map_fresh(cmap, contract, (scenario,), spec_digests=changed)
    assert good.passed and not stale.passed
    assert good.artifact_hash != stale.artifact_hash
    legacy = {key: value for key, value in cmap.items() if key != "spec_digests"}
    assert not seam_map_fresh(legacy, contract, (scenario,), spec_digests=before).passed
    assert not seam_map_fresh(cmap, contract, (scenario,), spec_digests=before,
                              execution_cwd="/recorded/project").passed
