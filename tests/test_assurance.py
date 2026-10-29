"""Adversarial controls for evidence accounting; no LLM claims are treated as truth."""
import copy
import json

import pytest

from lib.assurance import SCHEMA, assess, render, sha
from lib.contract import parse


@pytest.fixture
def bundle(tmp_path):
    contract = '# Contract\n\n- **C-1.1** — WHEN a value is doubled THE SYSTEM SHALL return twice its magnitude.\n- **C-1.2** — WHEN input is negative THE SYSTEM SHALL reject it.\n'
    (tmp_path / 'contract.md').write_text(contract, encoding='utf-8')
    (tmp_path / 'code.py').write_text('def twice(x): return x * 2\n')
    (tmp_path / 'checks.py').write_text('assert twice(2) == 4\n')
    (tmp_path / 'observation.txt').write_text('reviewer supplied control observations\n')
    manifest = {'schema': SCHEMA, 'contract': 'contract.md', 'implementation': ['code.py'], 'evidence': []}
    pin = parse(contract).by_id('C-1.1').version
    def evidence(kind, outcome='PASS', **extra):
        ev = {'id': str(len(manifest['evidence'])), 'clause': 'C-1.1', 'pin': pin,
              'kind': kind, 'outcome': outcome, 'scope': 'positive numeric examples',
              'producer': 'fixture reviewer', 'basis': 'declared observations for reducer tests',
              'inputs': {name: sha((tmp_path / name).read_bytes()) for name in ('contract.md', 'code.py', 'checks.py')},
              'checks': ['checks.py'], 'artifact': 'observation.txt',
              'artifact_sha256': sha((tmp_path / 'observation.txt').read_bytes()), **extra}
        manifest['evidence'].append(ev)
        return ev
    def run():
        (tmp_path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return assess(tmp_path, 'manifest.json')
    return tmp_path, manifest, evidence, run


def test_all_live_requirements_remain_in_denominator(bundle):
    """C-1.1 — an unobserved live obligation cannot disappear."""
    _, _, evidence, run = bundle
    evidence('execution')
    report = run()
    assert report['denominator'] == 2
    assert report['requirements'][1]['implementation'] == 'UNKNOWN'


def test_input_and_artifact_drift_remove_support(bundle):
    """C-1.2 — changed source and observation bytes invalidate support."""
    root, _, evidence, run = bundle
    evidence('execution')
    evidence('valid_alternative')
    evidence('violation', activated=True)
    assert run()['requirements'][0]['implementation'] == 'SUPPORTED'
    (root / 'code.py').write_text('def twice(x): return 4\n')
    report = run()
    assert report['requirements'][0]['implementation'] == 'UNKNOWN'
    assert all(not e['current'] for e in report['requirements'][0]['evidence'])
    (root / 'observation.txt').write_text('tampered')
    assert 'changed observation artifact' in run()['requirements'][0]['evidence'][0]['problems']


def test_green_execution_is_not_adequacy(bundle):
    """C-1.3 — green execution without activated controls is insufficient."""
    _, _, evidence, run = bundle
    evidence('execution')
    row = run()['requirements'][0]
    assert row['execution'] == 'SUPPORTED'
    assert row['implementation'] == row['check_adequacy'] == 'UNKNOWN'
    evidence('violation', activated=False)
    evidence('valid_alternative')
    assert run()['requirements'][0]['implementation'] == 'UNKNOWN'


def test_conflicts_are_visible_in_each_dimension(bundle):
    """C-1.4 — contradictory observations remain visible."""
    _, _, evidence, run = bundle
    for kind in ('execution', 'spec_review', 'code_review'):
        evidence(kind)
        evidence(kind, 'FAIL')
    evidence('valid_alternative')
    evidence('violation', activated=True)
    evidence('valid_alternative', 'FAIL')
    row = run()['requirements'][0]
    assert all(row[k] == 'CONFLICT' for k in ('execution', 'specification', 'code_correspondence', 'check_adequacy'))
    assert row['implementation'] == 'UNKNOWN'


def test_failed_unvalidated_check_does_not_refute_implementation(bundle):
    _, _, evidence, run = bundle
    evidence('execution', 'FAIL')
    assert run()['requirements'][0]['implementation'] == 'UNKNOWN'
    evidence('valid_alternative')
    evidence('violation', activated=True)
    assert run()['requirements'][0]['implementation'] == 'CONTRADICTED'
    evidence('execution')
    assert run()['requirements'][0]['implementation'] == 'CONFLICT'


def test_missing_code_review_is_unknown_even_with_green_tests(bundle):
    """C-1.5 — behavioral checks do not substitute for correspondence review."""
    _, _, evidence, run = bundle
    evidence('execution')
    evidence('valid_alternative')
    evidence('violation', activated=True)
    row = run()['requirements'][0]
    assert row['implementation'] == 'SUPPORTED'
    assert row['code_correspondence'] == 'UNKNOWN'


def test_report_is_bounded_and_escapes_authored_content(bundle):
    """C-1.6 — evidence counts are bounded and rendered safely."""
    _, _, evidence, run = bundle
    evidence('spec_review', scope='<script>alert(1)</script>')
    report = run()
    page = render(report)
    assert '<script>' not in page and '&lt;script&gt;' in page
    assert 'not probability' in ' '.join(report['limitations'])
    assert 'release' not in report and 'confidence' not in report


def test_unknown_ids_duplicates_unbound_checks_and_path_escape_rejected(bundle):
    _, manifest, evidence, run = bundle
    ev = evidence('execution')
    original = copy.deepcopy(ev)
    for mutation in ({'clause': 'C-99'}, {'checks': ['unbound.py']}, {'artifact': '../outside'}):
        ev.clear(); ev.update(original); ev.update(mutation)
        with pytest.raises(ValueError):
            run()
    ev.clear(); ev.update(original)
    manifest['evidence'].append(copy.deepcopy(ev))
    with pytest.raises(ValueError, match='unique'):
        run()


def test_contract_drift_and_missing_input_are_unknown(bundle):
    root, _, evidence, run = bundle
    evidence('execution')
    (root / 'contract.md').write_text((root / 'contract.md').read_text() + '\n')
    assert run()['requirements'][0]['execution'] == 'UNKNOWN'
    (root / 'checks.py').unlink()
    assert 'missing input: checks.py' in run()['requirements'][0]['evidence'][0]['problems']


def test_controls_from_different_scope_cannot_support_execution(bundle):
    _, _, evidence, run = bundle
    evidence('execution')
    evidence('valid_alternative', scope='other boundary')
    evidence('violation', activated=True, scope='other boundary')
    row = run()['requirements'][0]
    assert row['check_adequacy'] == 'SUPPORTED'
    assert row['implementation'] == 'UNKNOWN'


def test_missing_implementation_rejected_even_without_evidence(bundle):
    _, manifest, _, run = bundle
    manifest['implementation'] = []
    with pytest.raises(ValueError, match='implementation'):
        run()


def test_cli_reports_unknown_without_claiming_completion(bundle):
    import subprocess
    import sys
    from pathlib import Path
    root, _, _, run = bundle
    run()
    cli = Path(__file__).resolve().parents[1] / 'athena.py'
    result = subprocess.run([sys.executable, str(cli), 'assess', 'manifest.json',
                             '--cwd', str(root), '-o', str(root / 'report.json')],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    report = json.loads((root / 'report.json').read_text(encoding='utf-8'))
    assert report['counts']['implementation']['UNKNOWN'] == 2
    (root / 'manifest.json').write_text('[]')
    invalid = subprocess.run([sys.executable, str(cli), 'assess', 'manifest.json', '--cwd', str(root)],
                             capture_output=True, text=True, timeout=20)
    assert invalid.returncode == 2
