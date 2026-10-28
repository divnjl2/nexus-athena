"""A separate reading of evidence boundaries; no shared fixtures with the open specs."""


def test_sealed_unexecuted_evidence_cannot_look_perfect():
    """C-1.1, C-1.2 (sealed) — excluding every observation never establishes adequacy."""
    from lib.check import build
    from lib.mutation import summarize
    for state in ("unowned", "undetermined", "tool_error", "baseline_error"):
        summary = summarize(tuple({"status": state, "killed": False} for _ in range(7)))
        assert summary["score"] is None and summary["state"] == "INCOMPLETE"
        report = build(mutation={**summary, "blocking": True}, allow_partial=True)
        assert not report["passed"]


def test_sealed_collection_failure_is_not_requirement_detection():
    """C-1.3 (sealed) — a broken test collection has no assertion witness."""
    from lib.verification import junit_outcome
    xml = '<testsuites><testsuite><testcase><error message="ImportError"/></testcase></testsuite></testsuites>'
    assert junit_outcome(2, xml).status == "TOOL_ERROR"
