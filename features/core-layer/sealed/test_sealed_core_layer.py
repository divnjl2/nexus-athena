"""Sealed acceptance tier of the core layer (C-2.8 of the refinery, C-1.4 and C-1.5 of the foundry): run only
by the refinery's check, never in a packet or a dispatch verdict; an executor that edits this file is
never green. Second readings of clauses the visible specs already cover, phrased independently.
"""
from __future__ import annotations


def test_sealed_a_source_attribute_is_read_from_either_shape_and_absent_is_not_invented():
    """C-2.1 (sealed) — the source attribute comes through as written, from the sub-bullet or the
    inline marker, and a clause without one carries none rather than a default the parser made up."""
    from lib.contract import parse
    c = parse("# X\n\n## C-1 — a\n\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\n  - source: incident\n"
              "- **C-1.2** — WHEN c THE SYSTEM SHALL d.\n- **C-1.3** — WHEN e THE SYSTEM SHALL f.\n  - source: review\n")
    assert c.by_id("C-1.1").source == "incident" and c.by_id("C-1.3").source == "review"
    assert not c.by_id("C-1.2").source
    assert [x.id for x in c.clauses] == ["C-1.1", "C-1.2", "C-1.3"]
