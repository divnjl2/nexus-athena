"""Sealed acceptance tier of the contract layer (C-2.8 of the refinery, C-1.4 and C-1.5 of the foundry): run only
by the refinery's check, never in a packet or a dispatch verdict; an executor that edits this file is
never green. Second readings of clauses the visible specs already cover, phrased independently.
"""
from __future__ import annotations


def test_sealed_ids_survive_rewrapping_and_supersession_is_symmetric():
    """C-1.1 (sealed) — the same clause re-wrapped keeps its id and its version (C-2.2); naming a
    predecessor marks it superseded from the other end (C-1.2, C-1.3); a cycle is a lint finding (C-1.5)."""
    from lib.contract import lint, parse
    one = parse("# X\n\n## C-1 — a\n\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\n  - source: design\n- **C-1.2** — WHEN c THE SYSTEM SHALL d.\n  - supersedes: C-1.1\n")
    two = parse("# X\n\n## C-1 — a\n\n- **C-1.1** — WHEN a THE\n  SYSTEM SHALL b.\n  - source: design\n- **C-1.2** — WHEN c THE SYSTEM SHALL d.\n  - supersedes: C-1.1\n")
    assert [(c.id, c.version) for c in one.clauses] == [(c.id, c.version) for c in two.clauses]
    old, new = one.by_id("C-1.1"), one.by_id("C-1.2")
    assert old.status == "superseded" and old.superseded_by == ("C-1.2",) and old.is_live is False
    assert new.status == "active" and new.supersedes == ("C-1.1",)
    cyc = parse("# X\n\n## C-1 — a\n\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\n  - supersedes: C-1.2\n- **C-1.2** — WHEN c THE SYSTEM SHALL d.\n  - supersedes: C-1.1\n")
    assert any("cycle" in f.lower() for f in lint(cyc))
