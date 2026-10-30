"""Real coverage processes prove incremental selection by observable executions.

The temporary module never invokes Git; subject inference is explicitly forbidden by
the fixture. These tests do not rebuild the repository's derived artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lib.ast import Scenario
from lib.clause_map import build, collect, spec_digests, stale_specs, staleness
from lib.contract import parse as parse_contract
from lib.scenario_parser import parse as parse_scenarios


CONTRACT = """# Contract: Incremental evidence

- **C-1.1** — WHEN requested THE SYSTEM SHALL record the first observation.
- **C-1.2** — WHEN requested THE SYSTEM SHALL record the second observation.
- **C-1.3** — WHEN requested THE SYSTEM SHALL retain the third observation.
"""


@pytest.fixture
def native_map(tmp_path, monkeypatch):
    import athena

    monkeypatch.chdir(tmp_path)
    def no_git(*args, **kwargs):
        raise AssertionError("Git subject inference is forbidden in this test")
    monkeypatch.setattr(athena, "_git_purl", no_git)
    (tmp_path / "probe.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "name = sys.argv[1]\n"
        "with Path('executed.log').open('a', encoding='utf-8') as log:\n"
        "    log.write(name + '\\n')\n"
        "if name == 'left':\n"
        "    value = 1\n"
        "elif name == 'right':\n"
        "    value = 2\n"
        "else:\n"
        "    value = 3\n"
        "if name == 'retry' and Path('fail.txt').exists():\n"
        "    raise SystemExit(1)\n", encoding="utf-8")
    args = SimpleNamespace(contract=str(tmp_path / "contract.md"), scenarios="",
                           clause="", skip_tag=[], purl="pkg:generic/incremental-test",
                           incremental=True, out=str(tmp_path / "map.json"),
                           cwd=str(tmp_path), source=["probe"],
                           workdir=str(tmp_path / "coverage-work"), jobs=1)

    def run(specs, *, contract=CONTRACT, note="", clause="", commands=None, sources=None,
            subject=None):
        Path(args.contract).write_text(contract, encoding="utf-8")
        text = "# Scenarios\n\n" + note + "\n" + "\n".join(
            f"### {sid} — observe {name}\n"
            f"- **verifies:** {cid}\n"
            f"- **run_cmd:** `{(commands or {}).get(sid, 'python -m probe ' + name)}`\n"
            f"- **Given** a temporary module\n- **When** requested\n- **Then** record a run\n"
            for sid, cid, name in specs)
        (tmp_path / "scenarios.md").write_text(text, encoding="utf-8")
        args.clause = clause
        if sources is not None:
            args.source = list(sources)
        if subject is not None:
            args.purl = subject
        assert athena.cmd_contract_map(args) == 0
        return json.loads(Path(args.out).read_text(encoding="utf-8"))

    def executions():
        return (tmp_path / "executed.log").read_text(encoding="utf-8").splitlines()

    return run, executions


def test_incremental_executes_added_and_changed_commands_but_reuses_unchanged(native_map):
    """C-9.26 — new sibling and no-node command changes cause real executions."""
    run, executions = native_map
    original = (("S1.1", "C-1.1", "left"), ("S1.2", "C-1.2", "old"),
                ("S1.3", "C-1.3", "kept"))
    before = run(original)
    assert executions() == ["left", "old", "kept"]
    current = (original[0], ("S1.2", "C-1.2", "right"), original[2],
               ("S1.4", "C-1.1", "added"))
    after = run(current)
    assert executions() == ["left", "old", "kept", "left", "right", "added"]
    assert after["specs"]["S1.4"] == "C-1.1"
    for key in ("clauses", "clause_digests", "clause_versions"):
        assert after[key]["C-1.3"] == before[key]["C-1.3"]
    assert after["partial"].get("C-1.3") == before["partial"].get("C-1.3")
    repinned = run(current, note="Prose changed; executable obligations did not.")
    assert executions() == ["left", "old", "kept", "left", "right", "added"]
    assert repinned["scenario_version"] != after["scenario_version"]
    assert repinned["clauses"] == after["clauses"]
    # Whitespace and quoting do not change the argv; no-node commands still carry a pin.
    plain = Scenario("S1.1", "C-1.1", "", "python -m probe left")
    spaced = Scenario("S1.1", "C-1.1", "different prose", 'python  -m probe "left"')
    assert spec_digests((plain,), {}) == spec_digests((spaced,), {})
    assert stale_specs({}, spec_digests((plain,), {})) == ("S1.1",)


def test_incremental_retries_a_failed_sibling_even_when_its_clause_has_lines(native_map):
    """C-9.27 — a successful sibling and failed-run coverage cannot hide a retry."""
    run, executions = native_map
    specs = (("S1.1", "C-1.1", "left"), ("S1.2", "C-1.1", "retry"),
             ("S1.3", "C-1.2", "other"), ("S1.4", "C-1.3", "kept"))
    Path("fail.txt").write_text("fail", encoding="utf-8")
    failed = run(specs)
    assert failed["clauses"]["C-1.1"], "failed-run reachability remains observable"
    assert failed["spec_collected"] == {"S1.1": True, "S1.2": False, "S1.3": True, "S1.4": True}
    assert "C-1.1" not in failed["collected"]
    scenarios = parse_scenarios(Path("scenarios.md").read_text(encoding="utf-8"))
    report = staleness(failed, parse_contract(CONTRACT), scenarios)
    assert report["unmapped"] == ["C-1.1"] and not report["is_fresh"]
    Path("fail.txt").unlink()
    repaired = run(specs)
    assert executions() == ["left", "retry", "other", "kept", "left", "retry"]
    assert all(repaired["spec_collected"].values())
    assert staleness(repaired, parse_contract(CONTRACT), scenarios)["is_fresh"]
    run(specs)
    assert executions() == ["left", "retry", "other", "kept", "left", "retry"]


@pytest.mark.parametrize("exit_code,write_report", [(0, False), (1, False), (1, True)])
def test_collection_cannot_reuse_stale_output_or_accept_a_failed_process(
        tmp_path, exit_code, write_report):
    """C-9.28 — only fresh output plus successful processes is reusable evidence."""
    work = tmp_path / "work"
    work.mkdir()
    old = json.dumps({"files": {"old.py": {"executed_lines": [99]}}})
    (work / "S1_1.coverage").write_text("old data", encoding="utf-8")
    (work / "S1_1.json").write_text(old, encoding="utf-8")
    calls = []
    def runner(argv, cwd):
        calls.append(argv[3])
        assert not (work / "S1_1.coverage").exists()
        assert not (work / "S1_1.json").exists()
        if argv[3] == "json" and write_report:
            Path(argv[argv.index("-o") + 1]).write_text(old, encoding="utf-8")
        return exit_code
    result, = collect((Scenario("S1.1", "C-1.1", "", "python -m probe"),),
                      sources=(), workdir=str(work), runner=runner, jobs=1)
    assert calls == ["run", "json"]
    assert not result.collected and result.files == {}


def test_incremental_removes_obsolete_bindings_and_recollects_their_siblings(native_map):
    """C-9.29 — removed or rebound specs cannot leave obsolete attribution behind."""
    run, executions = native_map
    original = (("S1.1", "C-1.1", "left"), ("S1.2", "C-1.1", "right"),
                ("S1.3", "C-1.2", "other"), ("S1.4", "C-1.3", "kept"))
    run(original)
    removed = (original[0], original[2], original[3])
    after = run(removed)
    assert executions() == ["left", "right", "other", "kept", "left"]
    for key in ("specs", "spec_digests", "spec_collected"):
        assert "S1.2" not in after[key]
    assert 9 not in after["clauses"]["C-1.1"]["probe.py"], "removed right arm is gone"
    rebound = (("S1.1", "C-1.2", "left"), original[2], original[3])
    after = run(rebound)
    assert executions()[-2:] == ["left", "other"]
    assert "C-1.1" not in after["clauses"]
    assert after["specs"]["S1.1"] == "C-1.2"
    shrunk = CONTRACT.replace(
        "- **C-1.3** — WHEN requested THE SYSTEM SHALL retain the third observation.\n", "")
    after = run(rebound, contract=shrunk)
    assert executions() == ["left", "right", "other", "kept", "left", "left", "other"]
    for key in ("clauses", "clause_digests", "clause_versions", "partial"):
        assert "C-1.3" not in after[key]
    assert "S1.4" not in after["specs"]


def test_incremental_recollects_only_the_clause_whose_requirement_version_changed(native_map):
    """C-9.30 — a changed clause cannot acquire a new version without recollection."""
    run, executions = native_map
    specs = (("S1.1", "C-1.1", "left"), ("S1.2", "C-1.2", "other"),
             ("S1.3", "C-1.3", "kept"))
    before = run(specs)
    changed = CONTRACT.replace("record the first observation", "record two observations")
    after = run(specs, contract=changed)
    assert executions() == ["left", "other", "kept", "left"]
    assert before["clause_versions"]["C-1.1"] != after["clause_versions"]["C-1.1"]
    assert before["clauses"]["C-1.2"] == after["clauses"]["C-1.2"]


def test_filtered_incremental_work_keeps_unexecuted_changes_stale(native_map):
    """C-9.26 — a filter cannot refresh observations for changed inputs it did not execute."""
    run, executions = native_map
    specs = (("S1.1", "C-1.1", "left"), ("S1.2", "C-1.2", "other"),
             ("S1.3", "C-1.3", "kept"))
    before = run(specs)
    changed = (specs[0], ("S1.2", "C-1.2", "right"), specs[2])
    deferred = run(changed, clause="C-1.1")
    assert executions() == ["left", "other", "kept"]
    assert deferred["scenario_version"] == before["scenario_version"]
    assert deferred["spec_digests"]["S1.2"] == before["spec_digests"]["S1.2"]
    run(changed)
    assert executions() == ["left", "other", "kept", "right"]


def test_legacy_map_without_complete_outcomes_is_recollected(native_map):
    """C-9.27 — unknown legacy outcomes require actual recollection before reuse."""
    run, executions = native_map
    specs = (("S1.1", "C-1.1", "left"), ("S1.2", "C-1.2", "other"),
             ("S1.3", "C-1.3", "kept"))
    legacy = run(specs)
    legacy.pop("spec_collected")
    legacy.pop("clause_versions")
    Path("map.json").write_text(json.dumps(legacy), encoding="utf-8")
    run(specs)
    assert executions() == ["left", "other", "kept", "left", "other", "kept"]


def test_incremental_executes_changed_second_node_and_explicit_config(native_map):
    """C-9.26 — all explicit nodes and file inputs matter, not only the first node."""
    run, executions = native_map
    Path("test_observe.py").write_text(
        "from pathlib import Path\n"
        "def test_first():\n"
        "    with Path('executed.log').open('a') as log:\n"
        "        log.write('first\\n')\n"
        "def test_second():\n"
        "    with Path('executed.log').open('a') as log:\n"
        "        log.write('second-old\\n')\n", encoding="utf-8")
    Path("configured.py").write_text(
        "from pathlib import Path\nimport sys\n"
        "with Path('executed.log').open('a') as log:\n"
        "    log.write(Path(sys.argv[1]).read_text() + '\\n')\n", encoding="utf-8")
    Path("settings.txt").write_text("config-old", encoding="utf-8")
    specs = (("S1.1", "C-1.1", "nodes"), ("S1.2", "C-1.2", "config"),
             ("S1.3", "C-1.3", "kept"))
    commands = {"S1.1": "python -m pytest test_observe.py::test_first test_observe.py::test_second -q",
                "S1.2": "python -m configured settings.txt"}
    run(specs, commands=commands, sources=("probe", "test_observe", "configured"))
    assert executions() == ["first", "second-old", "config-old", "kept"]
    Path("test_observe.py").write_text(
        Path("test_observe.py").read_text(encoding="utf-8").replace("second-old", "second-new"),
        encoding="utf-8")
    Path("settings.txt").write_text("config-new", encoding="utf-8")
    run(specs, commands=commands)
    assert executions() == ["first", "second-old", "config-old", "kept",
                            "first", "second-new", "config-new"]
    run(specs, commands=commands)
    assert executions() == ["first", "second-old", "config-old", "kept",
                            "first", "second-new", "config-new"]


def test_explicit_test_files_include_decorators_and_other_test_helpers():
    """C-9.26 — complete explicit files include decorators and callable test helpers."""
    source = ("def helper():\n    return 1\n\n"
              "class TestGroup:\n"
              "    @mark(1)\n"
              "    def test_first(self):\n        assert helper() == 1\n"
              "    def test_second(self):\n        assert helper() == 2\n")
    spec = Scenario("S1.1", "C-1.1", "",
                    'python -m pytest "test group.py::TestGroup::test_first[1]" -q')
    original = spec_digests((spec,), {"test group.py": source})
    for changed in (source.replace("mark(1)", "mark(2)"),
                    source.replace("return 1", "return 2"),
                    source.replace("helper() == 1", "helper() == 3")):
        assert spec_digests((spec,), {"test group.py": changed}) != original
    assert spec_digests((spec,), {"test group.py": source.replace("helper() == 2", "helper() == 4")}) != original
    helper = "def test_helper():\n    return 0\ndef test_target():\n    assert test_helper() == 0\n"
    target = Scenario("S1.1", "C-1.1", "", "python -m pytest test_demo.py::test_target -q")
    assert spec_digests((target,), {"test_demo.py": helper}) != spec_digests(
        (target,), {"test_demo.py": helper.replace("return 0", "return 1")})


def test_incremental_pins_the_execution_cwd_source_roots_and_subject(native_map, monkeypatch):
    """C-9.26 — execution context changes require observations from that context."""
    run, executions = native_map
    target = Path.cwd()
    specs = (("S1.1", "C-1.1", "left"), ("S1.2", "C-1.2", "other"),
             ("S1.3", "C-1.3", "kept"))
    before = run(specs)
    launcher = target / "launcher"
    launcher.mkdir()
    monkeypatch.chdir(launcher)
    run(specs)
    assert executions() == ["left", "other", "kept"], "launcher cwd is not execution cwd"
    script = target / "probe.py"
    script.write_text(script.read_text(encoding="utf-8") + "UNRELATED_CONSTANT = 1\n",
                      encoding="utf-8")
    after = run(specs)
    assert executions() == ["left", "other", "kept"] * 2
    assert after["spec_digests"] != before["spec_digests"]
    run(specs, sources=("probe", "configured"), clause="C-1.1")
    assert executions() == ["left", "other", "kept"] * 2 + ["left"]
    partial = json.loads((target / "map.json").read_text(encoding="utf-8"))
    assert partial["pending_clauses"] == ["C-1.2", "C-1.3"]
    assert not staleness(partial, parse_contract(CONTRACT), ())["is_fresh"]
    run(specs)
    assert executions()[-3:] == ["left", "other", "kept"]
    count = len(executions())
    run(specs, subject="pkg:generic/another-project")
    assert len(executions()) == count + 3
    run(specs)
    assert len(executions()) == count + 3


def test_explicit_input_paths_preserve_parent_and_absolute_locations(tmp_path):
    """C-9.26 — fingerprints resolve explicit input paths in the actual execution directory."""
    import athena
    from lib.clause_map import input_paths

    work = tmp_path / "work"
    work.mkdir()
    config = tmp_path / "settings.txt"
    config.write_text("first", encoding="utf-8")
    relative = Scenario("S1.1", "C-1.1", "", "python -m probe ../settings.txt")
    absolute = Scenario("S1.2", "C-1.1", "", f'python -m probe "{config.as_posix()}"')
    assert "../settings.txt" in input_paths(relative.run_cmd)
    first = spec_digests((relative, absolute), athena._test_sources((relative, absolute), cwd=str(work)))
    config.write_text("second", encoding="utf-8")
    second = spec_digests((relative, absolute), athena._test_sources((relative, absolute), cwd=str(work)))
    assert first[relative.id] != second[relative.id]
    assert first[absolute.id] != second[absolute.id]


@pytest.fixture
def observed_branch_inputs(tmp_path, monkeypatch):
    """Observe both paths of a function without asserting the return-one obligation."""
    import runpy

    monkeypatch.chdir(tmp_path)
    Path("choice.py").write_text(
        "def choose(flag):\n    if flag:\n        return 0\n    return 0\n",
        encoding="utf-8")
    # Deliberately no value assertion: these commands observe both paths while the
    # hypothetical obligation "return one for either input" remains false.
    Path("observe.py").write_text(
        "import sys\nfrom choice import choose\nchoose(sys.argv[1] == 'yes')\n",
        encoding="utf-8")
    specs = (Scenario("S1.1", "C-1.1", "", "python -m observe yes"),
             Scenario("S1.2", "C-1.1", "", "python -m observe no"))
    evidence = collect(specs, sources=("choice",), workdir=str(tmp_path / "coverage"),
                       cwd=str(tmp_path), jobs=1)
    choose = runpy.run_path("choice.py")["choose"]
    return evidence, choose


def test_executed_lines_are_attributed_without_claiming_semantic_truth(observed_branch_inputs):
    """C-9.31 — declared bindings attribute observed lines without establishing requirement truth."""
    evidence, choose = observed_branch_inputs
    assert all(s.collected for s in evidence)
    attributed = build(evidence)
    assert attributed["specs"] == {"S1.1": "C-1.1", "S1.2": "C-1.1"}
    assert attributed["clauses"] == {"C-1.1": {"choice.py": [1, 2, 3, 4]}}
    assert choose(True) == choose(False) == 0, "execution did not establish return value one"
    assert "proved" not in attributed and "semantic_correspondence" not in attributed


def test_partial_branches_report_unobserved_arms(observed_branch_inputs):
    """C-9.32 — partial coverage identifies an unobserved arm of an attributed line."""
    evidence, _ = observed_branch_inputs
    assert evidence[0].collected
    one_arm = build(evidence[:1])
    assert one_arm["clauses"] == {"C-1.1": {"choice.py": [1, 2, 3]}}
    assert one_arm["partial"] == {"C-1.1": {"choice.py": [2]}}
    assert (2, 3) in evidence[0].branches["choice.py"]["executed"]
    assert (2, 4) in evidence[0].branches["choice.py"]["missing"]


def test_complementary_branches_do_not_establish_return_values(observed_branch_inputs):
    """C-9.33 — combining observed arms clears partial coverage without proving return values."""
    evidence, choose = observed_branch_inputs
    assert all(s.collected for s in evidence)
    assert build(evidence[:1])["partial"] == {"C-1.1": {"choice.py": [2]}}
    assert build(evidence[1:])["partial"] == {"C-1.1": {"choice.py": [2]}}
    both_arms = build(evidence)
    assert both_arms["partial"] == {}
    assert both_arms["clauses"] == {"C-1.1": {"choice.py": [1, 2, 3, 4]}}
    assert choose(True) == choose(False) == 0, "branch coverage did not establish value one"
    assert "proved" not in both_arms and "semantic_correspondence" not in both_arms
