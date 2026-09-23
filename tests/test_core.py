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
