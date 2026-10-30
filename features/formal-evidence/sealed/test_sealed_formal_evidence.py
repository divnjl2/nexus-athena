from lib.formal_evidence import classify


def test_sealed_failure_cannot_borrow_a_success_summary():
    """C-1.2 (sealed) — a summary cannot hide a nonzero process failure."""
    summary = 'Dafny program verifier finished with 1 verified, 0 errors'
    assert classify('dafny', 1, summary) != 'VERIFIED_RELATIVE_TO_SPEC'
    assert classify('dafny', 0, summary + '\n' + summary) == 'UNKNOWN'
