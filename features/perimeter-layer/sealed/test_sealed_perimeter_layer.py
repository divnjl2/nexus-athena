"""Sealed acceptance tier of the perimeter layer (C-2.8 of the refinery, C-1.4 and C-1.5 of the foundry):
run only by the refinery's check, never in a packet or a dispatch verdict; an executor that edits this
file is never green. Second readings of clauses the visible specs already cover, phrased independently.
Until the layer's modules land they skip: a second reading of nothing is nothing.
"""
from __future__ import annotations

import importlib.util

import pytest


def test_sealed_the_threshold_is_inclusive_and_the_worst_wins_whatever_the_order():
    """C-1.2 (sealed) — a finding exactly at the threshold refuses; among several the reason names the
    highest severity even when it comes last; an empty list is green with count zero."""
    if importlib.util.find_spec("lib.findings") is None:
        pytest.skip("lib/findings.py has not landed yet")
    from lib.findings import findings_verdict
    mk = lambda sev, line: {"tool": "t", "path": "p.py", "line": line, "severity": sev, "rule": "R", "message": "m"}   # noqa: E731
    assert findings_verdict([mk("warning", 1)], "warning")["ok"] is False
    assert findings_verdict([mk("info", 1)], "warning")["ok"] is True
    v = findings_verdict([mk("info", 1), mk("warning", 2), mk("error", 3)], "warning")
    assert v["ok"] is False and v["worst"]["line"] == 3 and "p.py:3" in v["reason"]
    z = findings_verdict([], "info")
    assert z["ok"] is True and z["count"] == 0


def test_sealed_the_cusum_needs_a_sustained_fall_not_one_bad_night():
    """C-4.2 (sealed) — one low point in a steady series is not a drop; the same low level held for
    several points is; a series that recovers after a dip is not."""
    if importlib.util.find_spec("lib.drift") is None:
        pytest.skip("lib/drift.py has not landed yet")
    from lib.drift import cusum_drop
    steady = [0.8] * 8
    assert cusum_drop(steady + [0.2] + [0.8] * 3, min_points=6) is None
    assert cusum_drop(steady + [0.3] * 4, min_points=6) is not None
    assert cusum_drop(steady + [0.5, 0.5] + [0.8] * 6, min_points=6) is None
