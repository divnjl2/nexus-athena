"""v3.10 the gate — the three questions as the criterion of done, for every contract in reach.

Each test is the executable spec of one C-5.* clause in features/core-layer/contract.md.
`lib.gate` is pure: recognising a contract, folding verdicts and shaping the hook decision
need no filesystem, so the rules are golden-testable; the walk and the check live in the CLI.
"""
from __future__ import annotations

import json
import pathlib

from lib.gate import BYPASS_VAR, find_contracts, fold, hook_decision, is_contract

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _v(path, passed, cause=""):
    return {"contract": path, "report": {"passed": passed, "first_cause": cause,
                                         "failed": [cause] if cause else [], "incomplete": []}}


def test_the_project_settings_register_the_gate_as_a_stop_hook():
    """C-5.1 — a gate script nobody registered enforces nothing; the settings are the proof."""
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [h.get("command", "")
                for group in settings.get("hooks", {}).get("Stop", [])
                for h in group.get("hooks", [])]
    assert any("contract-criterion-gate.sh" in c for c in commands), commands
    shim = ROOT / "hooks" / "contract-criterion-gate.sh"
    assert shim.exists() and "gate --hook" in shim.read_text(encoding="utf-8")


def test_a_contract_is_recognised_by_its_clauses_not_its_name():
    """C-5.2 — commands/contract.md documents a slash command; it has clause bullets only
    inside fenced examples, and a mention is not a contract."""
    real = "# Contract: X\n\n- **C-1.1** — WHEN x THE SYSTEM SHALL y.\n"
    doc = "# /athena.contract\n\nThe three questions...\n- coverage\n"
    fenced = "# About contracts\n\n```markdown\n- **C-1.1** — WHEN x THE SYSTEM SHALL y.\n```\n"
    assert is_contract(real) and not is_contract(doc) and not is_contract(fenced)
    assert find_contracts({"a/contract.md": doc, "b/contract.md": real, "c/notes.md": real}) \
        == ("b/contract.md", "c/notes.md")
    assert not is_contract((ROOT / "commands" / "contract.md").read_text(encoding="utf-8"))
    assert is_contract((ROOT / "features" / "core-layer" / "contract.md").read_text(encoding="utf-8"))


def test_one_failing_contract_fails_the_folded_gate():
    """C-5.3 — three contracts, one red: the gate is red and says which."""
    rep = fold((_v("a/contract.md", True), _v("b/contract.md", False, "todo"),
                _v("c/contract.md", True)))
    assert not rep["passed"] and rep["failing"] == ["b/contract.md"]
    assert rep["reason"] == "contract does not hold"
    assert fold((_v("a/contract.md", True),))["passed"]


def test_no_contract_means_no_opinion():
    """C-5.4 — a repository without a contract is not judged by this gate."""
    rep = fold(())
    assert rep["passed"] and rep["reason"] == "no contract" and hook_decision(rep) is None


def test_the_reason_names_the_contract_and_its_first_cause():
    """C-5.5 — a block that does not say what to fix is a nag."""
    decision = hook_decision(fold((_v("x/contract.md", False, "drift"),
                                   _v("y/contract.md", False, "todo"))))
    assert decision["decision"] == "block"
    assert "x/contract.md" in decision["reason"] and "drift" in decision["reason"]
    assert "y/contract.md" in decision["reason"], "every failing contract is named"


def test_the_bypass_variable_passes_and_says_so():
    """C-5.6 — the operator's word is the only bypass, and it is written in the report."""
    rep = fold((_v("x/contract.md", False, "todo"),), bypassed=True)
    assert rep["passed"] and rep["bypassed"] and rep["reason"] == "bypassed"
    assert hook_decision(rep) is None
    assert BYPASS_VAR == "CONTRACT_CRITERION_BYPASS"


def test_the_nudge_budget_is_spent_after_two_blocks():
    """C-5.7 — a gate that blocks forever gets disabled; two nudges, then it lets go and
    says so."""
    bad = (_v("x/contract.md", False, "todo"),)
    assert not fold(bad, nudges_used=0)["passed"] and not fold(bad, nudges_used=1)["passed"]
    third = fold(bad, nudges_used=2)
    assert third["passed"] and third["reason"] == "nudge budget spent"
    assert hook_decision(third) is None
