import json
import subprocess
from types import SimpleNamespace

import pytest

from lib.assurance import sha
from lib.contract import parse
from lib.formal_evidence import SCHEMA, classify, collect


@pytest.fixture
def project(tmp_path):
    contract = '- **C-1.1** — WHEN an integer is given THE SYSTEM SHALL double it.\n'
    (tmp_path / 'contract.md').write_text(contract, encoding='utf-8')
    (tmp_path / 'code.py').write_text('def double(x): return 2*x\n')
    task = {'id': 'one', 'clause': 'C-1.1', 'pin': parse(contract).by_id('C-1.1').version,
            'engine': 'crosshair', 'target': 'code.py', 'subject_kind': 'implementation',
            'scope': 'declared integer contract', 'assumptions': ['trusted local tool'],
            'inputs': {p: sha((tmp_path / p).read_bytes()) for p in ('contract.md', 'code.py')}}
    (tmp_path / 'manifest.json').write_text(json.dumps({'schema': SCHEMA, 'contract': 'contract.md', 'tasks': [task]}))
    return tmp_path


def test_search_is_not_a_proof():
    """C-1.1 — neither a successful search nor empty execution is proof."""
    assert classify('crosshair', 0, 'code.py:2: info: Confirmed over all paths.') == 'NO_COUNTEREXAMPLE'
    assert classify('crosshair', 0, '') == 'UNKNOWN'
    assert classify('crosshair', 1, 'code.py:2: error: false when calling double(1)') == 'COUNTEREXAMPLE'
    assert classify('crosshair', 2, 'SyntaxError') == 'UNKNOWN'


def test_dafny_requires_nonempty_successful_verification():
    """C-1.2 — a positive tool summary stays relative to the written property."""
    assert classify('dafny', 0, 'Dafny program verifier finished with 1 verified, 0 errors') == 'VERIFIED_RELATIVE_TO_SPEC'
    assert classify('dafny', 0, 'Dafny program verifier finished with 0 verified, 0 errors') == 'UNKNOWN'
    assert classify('dafny', 0, 'Dafny program verifier finished with 1 verified, 1 errors') == 'UNKNOWN'
    assert classify('dafny', 4, 'Dafny program verifier finished with 0 verified, 1 error') == 'UNPROVEN'
    assert classify('dafny', 4, 'Prover error: Model parsing error\nDafny program verifier finished with 0 verified, 1 error') == 'UNKNOWN'


def test_timeout_and_unknown_output_are_unknown(project, monkeypatch):
    """C-1.3 — infrastructure failure cannot certify or refute a requirement."""
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)
    monkeypatch.setattr('lib.formal_evidence.subprocess.run', timeout)
    report = collect(project, 'manifest.json', python='python', dafny='dafny')
    assert report['results'][0]['state'] == 'UNKNOWN'
    assert report['results'][0]['reason'] == 'process timeout'
    monkeypatch.setattr('lib.formal_evidence.subprocess.run', lambda *a, **k: SimpleNamespace(returncode=0, stdout='unrecognized', stderr=''))
    assert collect(project, 'manifest.json', python='python', dafny='dafny')['results'][0]['state'] == 'UNKNOWN'


def test_mutated_inputs_invalidate_tool_result(project, monkeypatch):
    """C-1.4 — a successful tool cannot certify input bytes changed during its run."""
    def mutate(*args, **kwargs):
        assert kwargs['shell'] is False
        (project / 'code.py').write_text('def double(x): return 0\n')
        return SimpleNamespace(returncode=0, stdout='code.py:2: info: Confirmed over all paths.', stderr='')
    monkeypatch.setattr('lib.formal_evidence.subprocess.run', mutate)
    row = collect(project, 'manifest.json', python='python', dafny='dafny')['results'][0]
    assert row['state'] == 'UNKNOWN' and row['changed_inputs'] == ['code.py']


def test_all_inputs_validated_before_any_execution(project, monkeypatch):
    manifest = json.loads((project / 'manifest.json').read_text())
    manifest['tasks'].append({**manifest['tasks'][0], 'id': 'two', 'pin': 'stale'})
    (project / 'manifest.json').write_text(json.dumps(manifest))
    def forbidden(*args, **kwargs):
        pytest.fail('must validate the entire plan before execution')
    monkeypatch.setattr('lib.formal_evidence.subprocess.run', forbidden)
    with pytest.raises(ValueError, match='stale'):
        collect(project, 'manifest.json', python='python', dafny='dafny')


def test_dafny_uses_invariant_numeric_culture(project, monkeypatch):
    manifest = json.loads((project / 'manifest.json').read_text())
    (project / 'code.dfy').write_text('method M() { }')
    task = manifest['tasks'][0]
    task.update(engine='dafny', target='code.dfy', subject_kind='model')
    task['inputs']['code.dfy'] = sha((project / 'code.dfy').read_bytes())
    (project / 'manifest.json').write_text(json.dumps(manifest))
    def run(*args, **kwargs):
        assert kwargs['env']['DOTNET_SYSTEM_GLOBALIZATION_INVARIANT'] == '1'
        return SimpleNamespace(returncode=0, stdout='Dafny program verifier finished with 1 verified, 0 errors', stderr='')
    monkeypatch.setattr('lib.formal_evidence.subprocess.run', run)
    row = collect(project, 'manifest.json', python='python', dafny='dafny')['results'][0]
    assert row['state'] == 'VERIFIED_RELATIVE_TO_SPEC'
    assert row['subject_kind'] == 'model'
    assert row['environment_overrides']['DOTNET_SYSTEM_GLOBALIZATION_INVARIANT'] == '1'


def test_view_preserves_model_and_intent_boundaries():
    """C-1.5 — verified models are visibly distinct from user intent."""
    from lib.formal_review import render
    report = {'results': [{'id': '<script>', 'engine': 'dafny', 'state': 'VERIFIED_RELATIVE_TO_SPEC',
                          'subject_kind': 'model', 'scope': 'written contract', 'elapsed_seconds': 1}], 'limitations': []}
    page = render(report)
    assert '&lt;script&gt;' in page
    assert 'Замысел пользователя' in page and 'не доказывает' in page
    assert 'implementation' not in report


def test_later_job_does_not_execute_shared_inputs_changed_by_earlier_job(project, monkeypatch):
    """C-1.4 — a stale later job is excluded before launching its tool."""
    manifest = json.loads((project / 'manifest.json').read_text())
    manifest['tasks'].append({**manifest['tasks'][0], 'id': 'two'})
    (project / 'manifest.json').write_text(json.dumps(manifest))
    calls = []
    def mutate(argv, **kwargs):
        calls.append(argv)
        (project / 'code.py').write_text('def double(x): return 0\n')
        return SimpleNamespace(returncode=0, stdout='code.py:2: info: Confirmed over all paths.', stderr='')
    monkeypatch.setattr('lib.formal_evidence.subprocess.run', mutate)
    rows = collect(project, 'manifest.json', python='python', dafny='dafny')['results']
    assert len(calls) == 1
    assert [r['state'] for r in rows] == ['UNKNOWN', 'UNKNOWN']
    assert rows[1]['exit_code'] is None and rows[1]['stdout'] == ''
    assert 'tool not run' in rows[1]['reason']


@pytest.mark.parametrize('bad_task', [None, [], {'id': []}, {'id': 42}])
def test_malformed_task_is_rejected_before_execution(project, monkeypatch, bad_task):
    manifest = json.loads((project / 'manifest.json').read_text())
    manifest['tasks'].append(bad_task)
    (project / 'manifest.json').write_text(json.dumps(manifest))
    def forbidden(*args, **kwargs):
        pytest.fail('invalid manifest must not execute a tool')
    monkeypatch.setattr('lib.formal_evidence.subprocess.run', forbidden)
    with pytest.raises(ValueError):
        collect(project, 'manifest.json', python='python', dafny='dafny')
