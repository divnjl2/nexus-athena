"""v3.11 decisions kept — records in docs/adr, cited by clauses, owned by a human.

Each test is the executable spec of one C-2.* clause in features/team-layer/contract.md.
"""
from __future__ import annotations

import pathlib

from lib.adr import cited_targets, lint_adr, parse_adr, unlinked
from lib.contract import parse as parse_contract

ROOT = pathlib.Path(__file__).resolve().parents[1]

ADR = """# ADR-0007: Branch evidence per clause

- Status: accepted
- Date: 2026-09-23

## Context
Coverage credited everything.

## Decision
Record half-proved lines per clause.

## Consequences
- More than one spec per clause becomes worth writing.
"""


def test_a_decision_record_requires_its_six_parts():
    """C-2.1 — id, status, date, context, decision, consequences: a record missing one is
    reported by name, and the repository's own records pass."""
    rec = parse_adr(ADR)
    assert rec["id"] == "ADR-0007" and rec["status"] == "accepted" and rec["date"] == "2026-09-23"
    assert set(rec["sections"]) >= {"context", "decision", "consequences"}
    assert lint_adr(ADR) == ()
    assert any("status" in i.lower() for i in lint_adr(ADR.replace("- Status: accepted\n", "")))
    assert any("consequences" in i.lower() for i in lint_adr(ADR.split("## Consequences")[0]))
    for path in sorted((ROOT / "docs" / "adr").glob("*.md")):
        assert lint_adr(path.read_text(encoding="utf-8"), name=path.name) == (), path.name


def test_a_decision_nobody_cites_is_unlinked():
    """C-2.2 — a decision no clause rests on is either missing a citation or dead weight;
    either way it is reported."""
    contract = parse_contract("# Contract: X\n\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\n"
                              "  - see: ../../docs/adr/0007-branch.md@abcdef0123456789\n")
    cited = cited_targets("features/x/contract.md", contract)
    assert cited == {"docs/adr/0007-branch.md"}
    report = unlinked(["docs/adr/0007-branch.md", "docs/adr/0008-orphan.md"], cited)
    assert report == ("docs/adr/0008-orphan.md",)


def test_the_ownership_file_names_a_human_for_core_contracts_and_decisions():
    """C-2.3 — an agent proposes; a human's merge is the record of approval."""
    text = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    rules = [ln.split() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    owned = {r[0]: r[1:] for r in rules if len(r) >= 2}
    for pattern in ("CORE.md", "features/*/contract.md", "docs/adr/"):
        assert pattern in owned and any(o.startswith("@") for o in owned[pattern]), pattern


def test_the_design_step_sends_decisions_to_the_records_directory():
    """C-2.4 — the planning pipeline's design step must know where decisions live, or the
    ignored scratch folder wins again."""
    text = (ROOT / "commands" / "crisp" / "3_design.md").read_text(encoding="utf-8")
    assert "docs/adr" in text
    assert "Design Decisions" in text
