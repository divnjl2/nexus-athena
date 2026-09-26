"""Sealed acceptance tier of the executor layer (C-2.8 of the refinery, C-1.4 and C-1.5 of the foundry): run only
by the refinery's check, never in a packet or a dispatch verdict; an executor that edits this file is
never green. Second readings of clauses the visible specs already cover, phrased independently.
"""
from __future__ import annotations


def test_sealed_a_checkpoint_names_what_the_next_iteration_needs_and_nothing_it_does_not():
    """C-5.1, C-5.2 (sealed) — a red iteration's checkpoint carries the files touched, the red
    commands and the executor's last words; rendered into the next packet it sits after the static
    prefix, and a green result yields a checkpoint that says so."""
    from lib.dispatch import checkpoint, packet_with_checkpoint, render_checkpoint
    red = {"green": False, "reason": "x failed", "changed_files": ["lib/a.py"], "red": [{"cmd": "pytest a", "exit": 1}]}
    cp = checkpoint("T1", 2, red, claim="halfway there")
    assert cp["task"] == "T1" and cp["iteration"] == 2 and cp["passed"] is False
    assert cp["files"] == ["lib/a.py"] and cp["red"] and "halfway" in str(cp["last_words"])
    text = render_checkpoint(cp)
    assert "lib/a.py" in text and "pytest a" in text and "iteration 2" in text
    pk = packet_with_checkpoint({"text": "STATIC PREFIX" + chr(10) + "# task" + chr(10) + "body", "checks": ["c"], "budget_chars": 10000}, cp)
    assert pk["text"].startswith("STATIC PREFIX") and "pytest a" in pk["text"] and pk["checks"] == ["c"]
    assert checkpoint("T1", 3, {**red, "passed": True, "green": True, "red": []})["passed"] is True
