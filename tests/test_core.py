"""v3.10 the semantic core — the top of the pyramid, cited by fingerprint.

Each test is the executable spec of one C-1.* clause in features/core-layer/contract.md.
"""
from __future__ import annotations

import athena
from lib.check import build
from lib.contract import parse
from lib.docrefs import check as refs_check
from lib.docrefs import fingerprint
from lib.scaffold import CORE_TEMPLATE, render_files

GREEN = dict(
    lint_issues=(), critique_warnings=(),
    coverage={"passed": True, "live_clauses": 1, "uncovered": [], "orphan_specs": []},
    ledger_totals={"passed": 1, "total": 1, "failed": 0},
    todo={"remaining": 0, "counts": {"done": 1}, "backlog": 0},
    drift={"in_sync": True, "counts": {}},
    gates={"contract_bound": {"passed": True, "issues": []},
           "map_fresh": {"passed": True, "issues": []}},
)


def test_a_scaffold_writes_a_core_when_none_exists_above(tmp_path):
    """C-1.1 — a project starts with its core; a feature under an existing core cites that one
    instead of growing a second."""
    fresh = tmp_path / "fresh" / "features" / "pay"
    assert athena.main(["init", str(fresh), "--title", "Pay"]) == 0
    core = fresh / "CORE.md"
    assert core.exists()
    text = core.read_text(encoding="utf-8")
    for heading in ("## Goal", "## Language", "## Priorities", "## Constraints"):
        assert heading in text

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "CORE.md").write_text("# CORE: Proj\n\n## Goal\nShip.\n", encoding="utf-8")
    under = proj / "features" / "ship"
    assert athena.main(["init", str(under), "--title", "Ship"]) == 0
    assert not (under / "CORE.md").exists(), "one core per project"
    contract = (under / "contract.md").read_text(encoding="utf-8")
    assert "- see: ../../CORE.md@" in contract


def test_the_first_clause_cites_the_core_with_its_fingerprint():
    """C-1.2 — the citation carries the fingerprint of the text that was written, so the
    reference starts out ok and can only go suspect from there."""
    files = render_files(title="Pay")
    assert "CORE.md" in files
    contract = parse(files["contract.md"])
    assert contract.clauses[0].refs == (f"CORE.md@{fingerprint(files['CORE.md'])}",)
    rep = refs_check(contract, {"CORE.md": files["CORE.md"]})
    assert rep["passed"] and [r["clause"] for r in rep["ok"]] == ["C-1.1"]


def test_the_core_template_fits_in_forty_lines():
    """C-1.3 — past forty lines a core stops being read and starts being skimmed."""
    files = render_files(title="A Rather Long Feature Name For The Header")
    assert len(files["CORE.md"].splitlines()) <= 40
    assert len(CORE_TEMPLATE.splitlines()) <= 40


def test_a_changed_core_makes_the_citing_clause_suspect():
    """C-1.4 — a change to the principles is a list of clauses somebody must re-read."""
    files = render_files(title="Pay")
    contract = parse(files["contract.md"])
    moved = files["CORE.md"].replace("## Goal", "## Goal (revised)")
    rep = refs_check(contract, {"CORE.md": moved})
    assert not rep["passed"]
    assert [r["clause"] for r in rep["suspect"]] == ["C-1.1"]


def test_a_suspect_core_reference_fails_the_contract_leg():
    """C-1.5 — the check fails upstream, on the contract leg, and names the references step
    as the first cause."""
    ok = build(**GREEN, refs={"passed": True, "suspect": [], "broken": [],
                              "unpinned": [], "external": []})
    assert ok["passed"]
    rep = build(**GREEN, refs={"passed": False, "broken": [], "unpinned": [], "external": [],
                               "suspect": [{"clause": "C-1.1", "target": "CORE.md", "pin": "x"}]})
    assert not rep["passed"]
    assert rep["first_cause"] == "contract.refs" and rep["legs"]["contract"] is False


def test_scaffold_guidance_keeps_execution_and_semantic_evidence_distinct():
    """C-1.6 — generated guidance cannot turn an example check into requirement truth."""
    files = render_files(title="Pay")
    for name in ("CORE.md", "scenarios.md"):
        text = files[name]
        assert "success is an observation within its checked scope" in text
        assert "intent fidelity" in text.lower()
        assert "check adequacy" in text.lower()
        assert "code correspondence" in text.lower()
    assert "remaining evidence gaps" in files["plan.md"]
    assert "legacy ownership is not semantic correspondence" in files["CORE.md"]
    assert not any(phrase in text for text in files.values()
                   for phrase in ("exit 0 means the clause holds", "exit 0 means the requirement holds",
                                  "proved by an executable spec"))


def test_covered_success_does_not_promote_a_weak_oracle_to_assurance(tmp_path):
    """C-1.7 — real passing execution and coverage can coexist with a requirement violation."""
    import json
    import os
    import runpy
    import subprocess
    import sys

    from lib.assurance import SCHEMA, assess, sha
    from lib.clause_map import SpecLines, build as build_map, lines_from_json, owners

    contract_text = ("# Contract\n\n- **C-1.1** — WHEN an integer is doubled THE SYSTEM SHALL "
                     "return twice that integer.\n")
    sources = {
        "contract.md": contract_text,
        "implementation.py": "def twice(value):\n    return 4\n",
        "checks.py": "from implementation import twice\nassert twice(2) == 4\n",
    }
    for name, text in sources.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    argv = [sys.executable, "-m", "coverage", "run", "--source=implementation", "checks.py"]
    completed = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    exported = subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "coverage.json"],
                              cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert exported.returncode == 0, exported.stdout + exported.stderr
    reached = lines_from_json((tmp_path / "coverage.json").read_text(encoding="utf-8"))
    assert 2 in reached["implementation.py"]
    cmap = build_map((SpecLines("S1.1", "C-1.1", reached),))
    assert owners(cmap, "implementation.py", 2) == ("C-1.1",)
    (tmp_path / "clause_map.json").write_text(json.dumps(cmap), encoding="utf-8")

    # The untested input disproves the requirement despite the successful, covered check.
    actual = runpy.run_path(str(tmp_path / "implementation.py"))["twice"]
    assert actual(2) == 4
    assert actual(3) != 6
    observation = {"argv": argv, "returncode": completed.returncode,
                   "stdout": completed.stdout, "stderr": completed.stderr,
                   "coverage": "coverage.json", "map": "clause_map.json"}
    (tmp_path / "observation.json").write_text(json.dumps(observation), encoding="utf-8")
    evidence = {"id": "observed-weak-check", "clause": "C-1.1",
                "pin": parse(contract_text).by_id("C-1.1").version,
                "kind": "execution", "outcome": "PASS", "scope": "integer input 2 only",
                "producer": "local Python subprocess", "basis": "retained successful command and executed lines",
                "inputs": {name: sha((tmp_path / name).read_bytes())
                           for name in (*sources, "clause_map.json", "coverage.json")},
                "checks": ["checks.py"], "artifact": "observation.json",
                "artifact_sha256": sha((tmp_path / "observation.json").read_bytes())}
    manifest = {"schema": SCHEMA, "contract": "contract.md",
                "implementation": ["implementation.py"], "evidence": [evidence]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = assess(tmp_path, "manifest.json")
    row, = report["requirements"]
    assert row["execution"] == "SUPPORTED"
    assert row["evidence"][0]["current"]
    assert all(row[dimension] == "UNKNOWN" for dimension in
               ("implementation", "check_adequacy", "specification", "code_correspondence"))
    assert report["denominator"] == 1
