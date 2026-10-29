"""Second reading of evidence boundaries; does not certify reviewer independence."""
import json

from examples.assurance_demo import build
from lib.assurance import assess


def test_sealed_relabelled_scope_cannot_borrow_other_check_controls(tmp_path):
    """C-1.3 (sealed) — a vacuous execution cannot borrow a sound check's controls."""
    build(tmp_path)
    path = tmp_path / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    # Make the defective vacuous case appear to have sound controls, with the
    # same clause, scope, pins and source bytes. The actual check must still match.
    bad = next(e for e in manifest['evidence'] if e['id'] == '4-execution')
    copied = []
    for ev in manifest['evidence']:
        if ev['id'] in ('1-valid_alternative', '1-violation'):
            copied.append({**ev, 'id': 'copied-' + ev['id'], 'clause': bad['clause'], 'pin': bad['pin']})
    manifest['evidence'] = [bad, *copied]
    path.write_text(json.dumps(manifest), encoding='utf-8')
    row = assess(tmp_path, 'manifest.json')['requirements'][3]
    assert row['execution'] == 'SUPPORTED'
    assert row['check_adequacy'] == 'SUPPORTED'
    assert row['implementation'] == 'UNKNOWN'
