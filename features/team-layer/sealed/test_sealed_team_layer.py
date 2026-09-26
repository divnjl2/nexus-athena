"""Sealed acceptance tier of the team layer (C-2.8 of the refinery, C-1.4 and C-1.5 of the foundry): run only
by the refinery's check, never in a packet or a dispatch verdict; an executor that edits this file is
never green. Second readings of clauses the visible specs already cover, phrased independently.
"""
from __future__ import annotations


def test_sealed_derived_artifacts_are_refused_unless_bypassed_and_effects_stay_on_the_allowlist():
    """C-5.2, C-5.3, C-5.4 (sealed) — an edit to a derived artifact is refused and named, the
    bypass lets it through and says so, a source file is nobody's business here; a module outside
    the effect allowlist that imports a process module is a finding, one inside is not."""
    import json
    from lib.archlint import EFFECT_ALLOWED, lint_sources
    from lib.hooks import is_derived, pre_edit_decision
    assert is_derived("features/x/clause_map.json") and not is_derived("lib/a.py")
    refused = pre_edit_decision("features/x/clause_map.json", {})
    assert refused and "derived" in json.dumps(refused).lower()
    assert pre_edit_decision("lib/a.py", {}) is None
    allowed = pre_edit_decision("features/x/clause_map.json", {}, bypassed=True)
    assert (allowed is None) or ("bypass" in json.dumps(allowed).lower())
    src = "import subprocess" + chr(10) + chr(10) + "def f():" + chr(10) + "    return subprocess.run" + chr(10)
    assert lint_sources({"lib/nowhere_pure.py": src})
    inside = sorted(EFFECT_ALLOWED)[0]
    assert lint_sources({inside: src}) == ()
