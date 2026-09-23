"""v3.11 the harness — the agent gets its blast radius before the edit; derived files and
effect boundaries are enforced, not hoped for.

Each test is the executable spec of one C-5.* clause in features/team-layer/contract.md.
"""
from __future__ import annotations

import json
import pathlib

from lib.archlint import EFFECT_ALLOWED, lint_sources
from lib.hooks import is_derived, owners_for, pre_edit_decision

ROOT = pathlib.Path(__file__).resolve().parents[1]

MAPS = {
    "features/a/contract.md": {"clauses": {"C-1.1": {"lib/contract.py": [1, 2, 3]},
                                           "C-1.2": {"lib/other.py": [9]}}},
    "features/b/contract.md": {"clauses": {"C-7.3": {"lib/contract.py": [40, 41]}}},
}


def test_a_pending_edit_names_the_clauses_it_touches_across_contracts():
    """C-5.1 — `contract owners` existed; nobody told the agent. Now the answer arrives with
    the edit, from every contract that has a map."""
    owners = owners_for("C:/repo/lib/contract.py", MAPS)
    assert owners == {"features/a/contract.md": [("C-1.1", 3)],
                      "features/b/contract.md": [("C-7.3", 2)]}
    assert owners_for("lib/nobody.py", MAPS) == {}
    decision = pre_edit_decision("lib/contract.py", MAPS)
    ctx = decision["hookSpecificOutput"]["additionalContext"]
    assert decision["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "C-1.1" in ctx and "C-7.3" in ctx and "features/b/contract.md" in ctx
    assert pre_edit_decision("lib/nobody.py", MAPS) is None, "nothing to say, say nothing"


def test_an_edit_of_a_derived_artifact_is_refused_with_the_rebuild_command():
    """C-5.2 — a derived file cannot be hand-patched into agreement with a claim."""
    assert "spec run" in is_derived("features/x/spec_ledger.json")
    assert "contract map" in is_derived("C:\\r\\features\\x\\clause_map.json")
    assert "contract export" in is_derived("features/x/clauses.needs.json")
    assert is_derived("features/x/contract.md") == ""
    decision = pre_edit_decision("features/x/clause_map.json", MAPS)
    out = decision["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "contract map" in out["permissionDecisionReason"]
    assert "clause_map.json" in out["permissionDecisionReason"]


def test_the_bypass_allows_the_derived_edit_and_says_so():
    """C-5.3 — the operator's word is the only way past, and it is written in the context."""
    decision = pre_edit_decision("features/x/spec_ledger.json", MAPS, bypassed=True)
    out = decision["hookSpecificOutput"]
    assert out["permissionDecision"] == "allow"
    assert "bypass" in out["additionalContext"].lower()


def test_a_pure_module_importing_an_effect_module_is_reported():
    """C-5.4 — the effect seams are a list; anything else that spawns or dials out is a
    finding with the file and the line."""
    files = {"lib/pure.py": "import json\n\ndef f():\n    import subprocess\n    return 1\n",
             "lib/seam.py": "import subprocess\n"}
    issues = lint_sources(files, allowed=frozenset({"lib/seam.py"}))
    assert [(i["path"], i["line"], i["module"]) for i in issues] == [("lib/pure.py", 4, "subprocess")]
    assert lint_sources({"lib/net.py": "from urllib import request\n"}, allowed=frozenset()) != ()
    assert lint_sources({"lib/ok.py": "import os, re\n"}, allowed=frozenset()) == ()


def test_this_repository_passes_its_own_architecture_lint():
    """C-5.5 — the allowlist names the seams; everything else in lib/ spawns nothing."""
    files = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8")
             for p in sorted((ROOT / "lib").glob("*.py"))}
    assert lint_sources(files) == ()
    assert EFFECT_ALLOWED <= set(files), "an allowlisted seam that does not exist is rot"


def test_the_project_settings_register_the_pre_edit_hook():
    """C-5.6 — a hook nobody registered hands nobody anything."""
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    groups = settings.get("hooks", {}).get("PreToolUse", [])
    hits = [(g.get("matcher", ""), h.get("command", ""))
            for g in groups for h in g.get("hooks", []) if "pre-edit" in h.get("command", "")]
    assert hits, "no PreToolUse hook runs the pre-edit shim"
    matcher, _ = hits[0]
    for tool in ("Edit", "Write"):
        assert tool in matcher, matcher
    assert (ROOT / "hooks" / "pre-edit.sh").exists()
