"""The foundry's sealed acceptance tier (C-2.8 of the refinery, C-1.4 of the foundry): run only by
the refinery's check, never in a packet or a dispatch verdict; an executor that edits this file
is never green. These are the second readings of the gate the visible specs already cover.
"""
from __future__ import annotations


def test_sealed_the_mutation_gate_holds_at_its_boundaries():
    """C-1.3 (sealed) — a score exactly at the threshold passes; a survivor on an untouched line
    is advisory even when the score is low; an empty score table refuses nothing."""
    from lib.mutgate import mutation_verdict
    at = {"C-1.1": {"score": 0.7, "killed": 7, "total": 10, "survivors": []}}
    assert mutation_verdict(at, threshold=0.7, added={"lib/x.py": [1]})["ok"] is True
    low_untouched = {"C-1.1": {"score": 0.1, "killed": 1, "total": 10,
                               "survivors": [{"path": "lib/x.py", "line": 99, "kind": "constant"}]}}
    v = mutation_verdict(low_untouched, threshold=0.7, added={"lib/x.py": [1]})
    assert v["ok"] is True and v["advisory"] == ["C-1.1"]
    assert mutation_verdict({}, threshold=0.7, added={})["ok"] is True


def test_sealed_the_ears_validator_refuses_two_responses_in_one_sentence():
    """C-2.2 (sealed) — two SHALLs joined by 'and' are two clauses; a lower-case shall is not a
    SHALL; a WHEN without a THE SYSTEM is no shape."""
    from lib.drafts import ears_shape, validate_clause
    assert "more than one SHALL" in validate_clause("WHEN a verdict is red THE SYSTEM SHALL log it and THE SYSTEM SHALL stop.")
    assert ears_shape("WHEN a verdict is red the system shall log it.") in (None, "event")
    assert validate_clause("WHEN a verdict is red, log it.") != ()


def test_sealed_a_regression_never_restores_a_worse_iteration():
    """C-11.6 (sealed) — with several earlier iterations the restore point is the best of them,
    not merely the previous one."""
    from lib.dispatch import regression
    g = lambda n: [{"cmd": str(i), "exit": 0 if i < n else 1} for i in range(5)]  # noqa: E731
    assert regression([g(3), g(1), g(2), g(0)]) == {"restore": 1, "from": 4, "green_before": 3, "green_after": 0}
