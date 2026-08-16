"""v3.8 clause -> DOCUMENT references, with Doorstop's mechanism and Doorstop's words.

A link carries the fingerprint of its target at review time; a link whose target has moved
since is a SUSPECT LINK. Nothing here is new — it is the `pins:` idea pointed at arbitrary
documents, and the vocabulary is borrowed on purpose so a reader who knows Doorstop knows
this too.

Each test is the executable spec of one C-12.* clause in features/contract-layer/contract.md.
"""
from __future__ import annotations

from lib.contract import parse as parse_contract
from lib.contract import render
from lib.docrefs import check, fingerprint, parse_ref, render_ref, repin, targets

ADR = "# ADR 7\n\nBranch evidence is recorded per clause.\n"
RUNBOOK = "# Runbook\n\nRebuild the map nightly.\n"

CONTRACT = parse_contract(f"""# Contract: Refs

- **C-1.1** — WHEN a spec runs THE SYSTEM SHALL record branch evidence.
  - see: docs/adr/0007.md@{fingerprint(ADR)}
  - see: https://coverage.readthedocs.io/branch.html
- **C-1.2** — WHEN the map is rebuilt THE SYSTEM SHALL re-pin it.
  - see: docs/runbook.md@0000000000000000
  - see: docs/gone.md@{fingerprint(RUNBOOK)}
- **C-1.3** — WHEN nothing is referenced THE SYSTEM SHALL still answer.
  - see: docs/adr/0007.md
""")

SOURCES = {"docs/adr/0007.md": ADR, "docs/runbook.md": RUNBOOK, "docs/gone.md": None}


def test_a_reference_carries_the_fingerprint_of_what_was_reviewed():
    """C-12.1 - `path@fingerprint` is the whole syntax, and the fingerprint is optional
    because an unpinned reference is legal exactly as an unpinned spec is."""
    assert parse_ref("docs/adr/0007.md@3f9a1c02b7e3d5a8") == {
        "target": "docs/adr/0007.md", "pin": "3f9a1c02b7e3d5a8", "external": False}
    assert parse_ref("  docs/adr/0007.md  ") == {
        "target": "docs/adr/0007.md", "pin": "", "external": False}
    assert parse_ref("https://example.org/x")["external"] is True
    # the fingerprint is the LAST @-segment, so an @-bearing path still parses
    assert parse_ref("docs/@scope/pkg.md@abcdef0123456789")["target"] == "docs/@scope/pkg.md"
    assert parse_ref("docs/a@b.md")["pin"] == "", "an @ that is not a fingerprint is a path"

    ref = parse_ref("docs/adr/0007.md@3f9a1c02b7e3d5a8")
    assert render_ref(ref) == "docs/adr/0007.md@3f9a1c02b7e3d5a8"
    assert render_ref({**ref, "pin": ""}) == "docs/adr/0007.md"


def test_a_target_that_moved_since_review_is_a_suspect_link():
    """C-12.2 - Doorstop's word for it, and the same mechanism the clause->spec pin uses:
    the reference is not wrong, it is unreviewed against what the document says now."""
    rep = check(CONTRACT, SOURCES)
    assert [r["clause"] for r in rep["ok"]] == ["C-1.1"]
    assert [r["clause"] for r in rep["suspect"]] == ["C-1.2"]
    assert rep["suspect"][0]["now"] == fingerprint(RUNBOOK) != rep["suspect"][0]["pin"]
    assert not rep["passed"]


def test_a_missing_target_is_broken_and_a_url_is_not_checked_at_all():
    """C-12.3 - four outcomes, kept apart: a document that is gone is a mistake, and a URL
    is something this tool will not pretend to have read."""
    rep = check(CONTRACT, SOURCES)
    assert [r["target"] for r in rep["broken"]] == ["docs/gone.md"]
    assert [r["target"] for r in rep["external"]] == ["https://coverage.readthedocs.io/branch.html"]
    assert [r["clause"] for r in rep["unpinned"]] == ["C-1.3"]
    assert rep["refs"] == 5

    clean = check(parse_contract("# Contract: none\n\n- **C-1.1** — WHEN x SHALL y.\n"), {})
    assert clean["passed"] and clean["refs"] == 0


def test_repinning_names_only_the_references_that_moved():
    """C-12.4 - re-pinning is REVIEWING, so it reports the edits rather than agreeing with
    whatever the document happens to say today."""
    edits = repin(CONTRACT, SOURCES)
    assert set(edits) == {"C-1.2", "C-1.3"}, "C-1.1 still matches; the missing file is skipped"
    assert edits["C-1.2"]["docs/runbook.md@0000000000000000"] == (
        f"docs/runbook.md@{fingerprint(RUNBOOK)}")
    assert edits["C-1.3"]["docs/adr/0007.md"] == f"docs/adr/0007.md@{fingerprint(ADR)}"
    assert repin(CONTRACT, {}) == {}, "nothing read, nothing claimed"

    assert targets(CONTRACT) == ("docs/adr/0007.md", "docs/runbook.md", "docs/gone.md")


def test_references_survive_a_render_round_trip():
    """C-12.5 - a render that dropped references would turn the canonicaliser into a
    data-loss step, and the round-trip is the only place that shows it."""
    again = parse_contract(render(CONTRACT))
    assert [c.refs for c in again.clauses] == [c.refs for c in CONTRACT.clauses]
    assert [c.id for c in again.clauses] == [c.id for c in CONTRACT.clauses]
