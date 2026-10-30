"""Native adversarial controls for inputs changing during coverage collection.

The fixture mutates only its own temporary files and uses explicit subject identity;
neither collection nor freshness checking may invoke Git. These controls do not
detect an adversary that restores identical bytes between the two snapshots.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.clause_map import digests, spec_digests, staleness
from lib.contract import parse as parse_contract
from lib.scenario_parser import parse as parse_scenarios
from lib.seams import seam_map_fresh
from lib.versioning import hash_text


@pytest.mark.parametrize("changed_input", ("verifier", "measured_source"))
@pytest.mark.parametrize("mutation_phase", ("collection", "pinning"))
def test_inputs_changed_during_collection_stay_stale_until_stable_rerun(
        tmp_path, monkeypatch, changed_input, mutation_phase):
    """C-9.35 — observations cannot acquire post-edit input pins without a new run."""
    import athena

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    def no_git(*args, **kwargs):
        raise AssertionError("Git subject inference is forbidden in this test")

    monkeypatch.setattr(athena, "_git_purl", no_git)
    contract_path = tmp_path / "contract.md"
    scenario_path = tmp_path / "scenarios.md"
    test_path = tmp_path / "test_observe.py"
    app_path = tmp_path / "app.py"
    map_path = tmp_path / "map.json"
    contract_path.write_text(
        "# Contract\n\n- **C-1.1** — WHEN requested THE SYSTEM SHALL return an allowed value.\n",
        encoding="utf-8")
    scenario_path.write_text(
        "# Scenarios\n\n### S1.1 — Observe an allowed value\n"
        "- **verifies:** C-1.1\n"
        "- **run_cmd:** `python -m pytest test_observe.py::test_observe -q`\n",
        encoding="utf-8")
    app_path.write_text("def answer():\n    return 1\n", encoding="utf-8")
    modification = (
        "        target = Path(__file__)\n"
        "        target.write_text(target.read_text(encoding='utf-8') + '# changed during collection\\n', encoding='utf-8')\n"
        if changed_input == "verifier" else
        "        target = Path('app.py')\n"
        "        target.write_text(target.read_text(encoding='utf-8').replace('return 1', 'return 22'), encoding='utf-8')\n")
    run_source = (
        "from pathlib import Path\nimport app\n\n"
        "def test_observe():\n"
        "    observed = app.answer()\n"
        "    assert observed in (1, 22)\n"
        "    with Path('executed.log').open('a', encoding='utf-8') as out:\n"
        "        out.write(str(observed) + '\\n')\n")
    if mutation_phase == "collection":
        run_source += ("    marker = Path('modified-once.txt')\n"
                       "    if not marker.exists():\n" + modification +
                       "        marker.write_text('changed', encoding='utf-8')\n")
    test_path.write_text(run_source, encoding="utf-8")

    if mutation_phase == "pinning":
        finish = athena._finish_map

        def edit_before_pinning(*args, **kwargs):
            # Force the otherwise timing-dependent gap between coverage completion
            # and fingerprint construction, while retaining real native execution.
            marker = tmp_path / "modified-once.txt"
            if not marker.exists():
                target = test_path if changed_input == "verifier" else app_path
                content = target.read_text(encoding="utf-8")
                changed = (content + "# changed before pinning\n" if changed_input == "verifier"
                           else content.replace("return 1", "return 22"))
                target.write_text(changed, encoding="utf-8")
                marker.write_text("changed", encoding="utf-8")
            return finish(*args, **kwargs)

        monkeypatch.setattr(athena, "_finish_map", edit_before_pinning)

    args = athena.build_parser().parse_args([
        "contract", "map", str(contract_path), "--out", str(map_path),
        "--cwd", str(tmp_path), "--workdir", str(tmp_path / "coverage-work"),
        "--incremental", "--jobs", "1", "--purl", "pkg:generic/input-stability"])
    args.source = ["app"]
    contract = parse_contract(contract_path.read_text(encoding="utf-8"))
    scenarios = parse_scenarios(scenario_path.read_text(encoding="utf-8"))
    before = {name: (tmp_path / name).read_bytes() for name in ("app.py", "test_observe.py")}

    def fresh(cmap):
        current_lines = digests(cmap, athena._sources_of(cmap, cwd=str(tmp_path)))
        report = staleness(cmap, contract, scenarios,
                           scenario_version=hash_text(scenario_path.read_text(encoding="utf-8")),
                           clause_digests=current_lines, subject=args.purl)
        seam = seam_map_fresh(
            cmap, contract, scenarios,
            scenario_version=hash_text(scenario_path.read_text(encoding="utf-8")),
            clause_digests=current_lines, subject=args.purl,
            spec_digests=spec_digests(scenarios, athena._test_sources(scenarios, cwd=str(tmp_path))),
            execution_cwd=str(tmp_path.resolve()))
        return report["is_fresh"], seam.passed

    assert athena.cmd_contract_map(args) == 0
    first = json.loads(map_path.read_text(encoding="utf-8"))
    assert (tmp_path / "executed.log").read_text(encoding="utf-8").splitlines() == ["1"]
    changed_file = "test_observe.py" if changed_input == "verifier" else "app.py"
    assert (tmp_path / changed_file).read_bytes() != before[changed_file]
    assert fresh(first) == (False, False), "post-run hashes cannot make pre-edit observations current"

    # The next command observes the new stable bytes; reuse of the prior observation
    # would leave only one marker line and cannot satisfy this control.
    assert athena.cmd_contract_map(args) == 0
    second = json.loads(map_path.read_text(encoding="utf-8"))
    expected = ["1", "1" if changed_input == "verifier" else "22"]
    assert (tmp_path / "executed.log").read_text(encoding="utf-8").splitlines() == expected
    assert fresh(second) == (True, True)

    # With all inputs stable, the already observed result may now be reused.
    assert athena.cmd_contract_map(args) == 0
    assert (tmp_path / "executed.log").read_text(encoding="utf-8").splitlines() == expected
