"""Separate reading of the benchmark evidence boundary."""


def test_sealed_infrastructure_failure_is_not_bug_detection():
    """C-2.2, C-2.3 (sealed) — import/collection failure cannot establish a bug witness."""
    from evals.tddbench.adapter import classify
    r = {"test_before_patch": {"test_feature": "ERROR"},
         "test_after_patch": {"test_feature": "PASSED"}, "resolved": True, "final_score": 1.0}
    assert classify(r)["state"] == "INCOMPLETE"
