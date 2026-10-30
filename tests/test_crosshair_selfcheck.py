import ast
import json
from pathlib import Path

from tools.run_crosshair_selfcheck import describe_snapshot, prepare


def test_selfcheck_preserves_source_and_seeds_real_state_errors(tmp_path):
    """C-1.6 — source snapshots and seeded errors concern the real evidence reducer."""
    source = Path(__file__).resolve().parents[1]
    before = (source / 'lib/assurance.py').read_bytes()
    provenance = prepare(source, tmp_path)
    assert (source / 'lib/assurance.py').read_bytes() == before
    assert (tmp_path / 'production/lib/assurance.py').read_bytes() == before
    assert provenance['production_source_sha256'] == provenance['production_snapshot_sha256']
    expected = {(False, False): 'UNKNOWN', (True, False): 'SUPPORTED',
                (False, True): 'CONTRADICTED', (True, True): 'CONFLICT'}
    for name, wanted_state in provenance['expected'].items():
        tree = ast.parse((tmp_path / name / 'lib/assurance.py').read_text(encoding='utf-8'))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'combine')
        namespace = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<frozen reducer>', 'exec'), namespace)
        observed = {args: namespace['combine'](*args) for args in expected}
        if wanted_state == 'COUNTEREXAMPLE':
            assert observed != expected, name
        else:
            assert observed == expected, name
        if name == 'missing-contract':
            assert ast.get_docstring(fn) is None
        manifest = json.loads((tmp_path / name / 'manifest.json').read_text(encoding='utf-8'))
        assert manifest['tasks'][0]['target'] == 'lib/assurance.py'
        assert 'lib/contract.py' in manifest['tasks'][0]['inputs']


def test_replay_distinguishes_executed_state_table_from_tool_claims(tmp_path):
    """C-1.7 — replay computes real outputs without inventing tool observations."""
    from lib.formal_review import render
    prepare(Path(__file__).resolve().parents[1], tmp_path)
    baseline = describe_snapshot(tmp_path / 'production')
    bad = describe_snapshot(tmp_path / 'silence-is-support')
    assert len(baseline['matrix']) == 4
    assert all(r['expected'] == r['actual'] for r in baseline['matrix'])
    assert bad['matrix'][0] == {'support': False, 'contradiction': False, 'expected': 'UNKNOWN', 'actual': 'SUPPORTED'}
    assert 'state' not in bad and 'stdout' not in bad
    report = {'results': [{'id': 'silence-is-support', 'engine': 'crosshair', 'subject_kind': 'implementation',
                          'state': 'UNKNOWN', 'scope': 'one frozen function', 'elapsed_seconds': 0, 'replay': bad}], 'limitations': []}
    page = render(report)
    assert 'id="replay-table"' in page and 'id="case-output"' in page
    assert 'id="case-choice"' in page
