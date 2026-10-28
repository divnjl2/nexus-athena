"""Run the real Athena check modules with an isolated execution seam."""
import json

import pytest

from test_tdd_execution import public_runtime
from evals.tddbench.execution import validate_reference
from evals.tddbench.generator import Budget, generate_direct
from evals.tddbench.native import check_proposal

CONTRACT = '# Contract: Behavior\n\n- **C-1.1** — WHEN value is requested THE SYSTEM SHALL return one.\n'
SCENARIOS = '''# Scenarios
### S1.1 - Value
- **verifies:** C-1.1
- **run_cmd:** `python -m pytest tests/test_value.py -q`
- **Given** a value request
- **When** the value is read
- **Then** it equals one.
'''


def proposal():
    return {'contract': CONTRACT, 'scenarios': SCENARIOS,
            'files': {'tests/test_value.py': 'from api import value\ndef test_value():\n    assert value() == 1\n'},
            'reference': [{'path': 'api.py', 'old': 'pass\n', 'new': 'def value():\n    return 1\n'}]}


def _contract_case_native_check_runs_contract_ledger_and_exports_only_tests(public_runtime, tmp_path):
    root, _ = public_runtime
    calls = []
    def execute(action, reference):
        calls.append((action, reference))
        assert reference == {'api.py': 'def value():\n    return 1\n'}
        return {'status': 'PASS'}
    result = check_proposal(str(root), str(tmp_path / 'native'), proposal(), execute)
    assert result['passed'] is True and result['state'] == 'PASS'
    assert result['baseline_origin'] == 'model-proposed-public-reference' and result['gold_used'] is False
    assert result['ledger']['results'][0]['clause_version']
    assert result['check']['passed'] is True and len(calls) == 1
    assert 'lib/check.py' in result['framework_files'] and not result['method_changed']
    assert 'b/tests/test_value.py' in result['patch'] and 'diff --git a/api.py' not in result['patch']
    assert (root / 'source/api.py').read_text() == 'pass\n'


def test_reference_and_native_commands_cannot_escape_public_inputs(public_runtime, tmp_path):
    """C-7.3 - no unsafe execution occurs."""
    root, _ = public_runtime
    for reference in ({'../secret.py': 'x'}, {'conftest.py': 'x'},
                      [{'path': 'api.py', 'old': 'missing', 'new': 'fix'}]):
        with pytest.raises(ValueError):
            validate_reference(str(root), reference)
    p = proposal()
    p['scenarios'] = p['scenarios'].replace('python -m pytest tests/test_value.py -q', 'python -c dangerous')
    def never(*args):
        pytest.fail('invalid command reached execution')
    with pytest.raises(ValueError):
        check_proposal(str(root), str(tmp_path / 'refused'), p, never)
    p = proposal()
    p.pop('reference')
    with pytest.raises(ValueError, match='reference'):
        check_proposal(str(root), str(tmp_path / 'missing'), p, never)


def test_native_gate_keeps_failed_and_inconclusive_baselines_distinct(public_runtime, tmp_path):
    """C-7.4 - FAIL differs from INCOMPLETE and no extra execution budget appears."""
    root, _ = public_runtime
    failed = check_proposal(str(root), str(tmp_path / 'failed'), proposal(),
                            lambda *a: {'status': 'ASSERTION_FAIL', 'tail': 'AssertionError'})
    incomplete = check_proposal(str(root), str(tmp_path / 'incomplete'), proposal(),
                                lambda *a: {'status': 'BUDGET_EXHAUSTED'})
    assert failed['state'] == 'FAIL' and not failed['passed']
    assert incomplete['state'] == 'INCOMPLETE' and not incomplete['passed']
    p = proposal()
    p['contract'] += '- **C-1.2** — WHEN another request occurs THE SYSTEM SHALL answer it.\n'
    uncovered = check_proposal(str(root), str(tmp_path / 'uncovered'), p, lambda *a: {'status': 'PASS'})
    assert not uncovered['passed'] and 'coverage' in uncovered['check']['failed']


def test_athena_generation_really_checks_reference_and_uses_shared_budget(public_runtime, tmp_path, monkeypatch):
    import evals.tddbench.execution as execution
    root, runtime = public_runtime
    calls = []
    def tool(*args, **kwargs):
        calls.append(kwargs)
        assert kwargs['implementation']['api.py'].startswith('def value')
        return {'status': 'PASS', 'diagnostic_only': True}
    monkeypatch.setattr(execution, 'run_tests', tool)
    def model(*args):
        return {'text': json.dumps({'action': 'finish', 'proposal': proposal()}), 'finish_reason': 'stop'}
    out = tmp_path / 'generated'
    result = generate_direct(str(root), str(out), model, runtime_receipt=str(runtime),
                             mode='athena', budget=Budget(max_calls=1, max_test_runs=1))
    assert result['status'] == 'GENERATED' and result['mode'] == 'athena'
    assert result['test_runs'] == 1 and len(calls) == 1
    assert result['native_check']['gold_used'] is False
    patch = json.loads((out / 'prediction.json').read_text())[0]['model_patch']
    assert 'diff --git a/api.py' not in patch
    exhausted = generate_direct(str(root), str(tmp_path / 'exhausted'), model,
                                runtime_receipt=str(runtime), mode='athena', budget=Budget(max_calls=1, max_test_runs=1))
    assert exhausted['status'] == 'GENERATED'  # budget is per invocation, never global
    with pytest.raises(ValueError, match='runtime'):
        generate_direct(str(root), str(tmp_path / 'no-runtime'), model, mode='athena')


def test_native_check_cannot_spend_an_extra_test_budget(public_runtime, tmp_path, monkeypatch):
    import evals.tddbench.execution as execution
    root, runtime = public_runtime
    calls = []
    def tool(*args, **kwargs):
        calls.append(args)
        return {'status': 'PASS', 'diagnostic_only': True}
    monkeypatch.setattr(execution, 'run_tests', tool)
    actions = [{'action': 'run', 'files': proposal()['files'], 'tests': ['tests/test_value.py']},
               {'action': 'finish', 'proposal': proposal()}]
    def model(*args):
        return {'text': json.dumps(actions.pop(0)), 'finish_reason': 'stop'}
    out = tmp_path / 'budgeted'
    result = generate_direct(str(root), str(out), model, mode='athena', runtime_receipt=str(runtime),
                             budget=Budget(max_calls=2, max_test_runs=1))
    assert result['status'] == 'INCOMPLETE' and result['test_runs'] == 1 and len(calls) == 1
    assert not (out / 'prediction.json').exists()
    native = json.loads((out / 'native/attempt-001/check.json').read_text())
    assert native['state'] == 'INCOMPLETE'


def test_native_check_runs_contract_ledger_and_exports_only_tests_C_7_1(public_runtime, tmp_path):
    """C-7.1 - real Athena modules produce a pinned ledger and scoped check with source fingerprints."""
    _contract_case_native_check_runs_contract_ledger_and_exports_only_tests(public_runtime, tmp_path)


def test_native_check_runs_contract_ledger_and_exports_only_tests_C_7_2(public_runtime, tmp_path):
    """C-7.2 - only tests are exported and original public source remains unchanged."""
    _contract_case_native_check_runs_contract_ledger_and_exports_only_tests(public_runtime, tmp_path)
