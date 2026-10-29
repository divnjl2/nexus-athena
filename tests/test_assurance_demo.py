from examples.assurance_demo import build


def test_executed_controls_distinguish_defects_from_bad_checks(tmp_path):
    """C-1.3 — actual oracle controls distinguish bad code from bad checks."""
    report = build(tmp_path)
    rows = report['requirements']
    assert [r['implementation'] for r in rows] == ['SUPPORTED', 'CONTRADICTED', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN']
    assert [r['check_adequacy'] for r in rows] == ['SUPPORTED', 'SUPPORTED', 'CONTRADICTED', 'CONTRADICTED', 'UNKNOWN']
    assert rows[2]['execution'] == 'CONTRADICTED'
    assert rows[3]['execution'] == 'SUPPORTED'
    assert all(r['code_correspondence'] == r['specification'] == 'UNKNOWN' for r in rows)
    assert all(e['current'] for r in rows for e in r['evidence'])
