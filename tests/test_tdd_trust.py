"""Real native trust policy with an injected offline execution boundary."""
import json

import pytest

from test_tdd_execution import public_runtime
from test_tdd_native import proposal
from evals.tddbench.generator import Budget, generate_direct
from evals.tddbench.trust import audit_candidate, create_review, load_candidate


def review_payload():
    return {'activation_files': {'tests/test_independent_activation.py':
            'from api import value\ndef test_activation():\n    assert value() == 0\n'},
            'passports': [{'clause': 'C-1.1', 'intent_source': 'public expected value one',
                           'owner_decision': 'scripted engineering review, not an inference result',
                           'input_domain': 'value()', 'observable_outcome': 'one',
                           'oracle_source': 'separately authored activation assertion',
                           'assumptions': [], 'undefined_behavior': [], 'known_gaps': [], 'specs': ['S1.1'],
                           'variants': [
                               {'id': 'valid', 'kind': 'valid', 'reason': 'same returned value',
                                'files': [{'path': 'api.py', 'old': 'return 1', 'new': 'return (1)'}]},
                               {'id': 'zero', 'kind': 'violation', 'reason': 'wrong returned value',
                                'files': [{'path': 'api.py', 'old': 'return 1', 'new': 'return 0'}],
                                'activation': 'python -m pytest tests/test_independent_activation.py -q'}]}]}


@pytest.fixture
def frozen(public_runtime, tmp_path, monkeypatch):
    import evals.tddbench.execution as execution
    monkeypatch.setattr(execution, 'run_tests', lambda *a, **k: {'status': 'PASS'})
    root, runtime = public_runtime
    def make(name='generation', *, test_kind='normal', max_runs=8, extra_scenario=False):
        p = proposal()
        if test_kind == 'vacuous':
            p['files'] = {'tests/test_value.py': 'def test_value():\n    assert True\n'}
        elif test_kind == 'overspecific':
            p['files'] = {'tests/test_value.py': 'import inspect\nfrom api import value\ndef test_value():\n    assert "return 1" in inspect.getsource(value)\n'}
        if extra_scenario:
            p['scenarios'] += '\n### S1.2 - Another spec\n- **verifies:** C-1.1\n- **run_cmd:** `python -m pytest tests/test_value.py -q`\n- **Given** value\n- **When** requested\n- **Then** one.\n'
        class Model:
            source_kind = 'scripted-control'
            model = 'candidate-control'
            def __call__(self, messages, budget):
                return {'text': json.dumps({'action': 'finish', 'proposal': p}), 'finish_reason': 'stop'}
        out = tmp_path / name
        result = generate_direct(str(root), str(out), Model(), mode='athena-trust', runtime_receipt=str(runtime),
                                 budget=Budget(max_calls=2, max_test_runs=max_runs))
        assert result['status'] == 'AWAITING_REVIEW' and not (out / 'prediction.json').exists()
        return out
    return root, runtime, make


def reviewed(root, generation, tmp_path, name='review'):
    class Reviewer:
        model = 'independent-scripted-review-control'
        source_kind = 'scripted-control'
        def __call__(self, messages, budget):
            assert 'Review a frozen' in messages[0]['content']
            assert 'reference_delta' in messages[1]['content']
            return {'text': json.dumps(review_payload()), 'finish_reason': 'stop'}
    out = tmp_path / name
    result = create_review(str(root), str(generation), str(out), Reviewer())
    assert result['state'] == 'READY' and result['calls'] == 1
    return out / 'review.json'


def execution(action, reference):
    assert not ('tests/test_value.py' in action['files'] and 'tests/test_independent_activation.py' in action['files'])
    zero = 'return 0' in reference['api.py']
    if 'tests/test_independent_activation.py' in action['files']:
        return {'status': 'PASS' if zero else 'ASSERTION_FAIL', 'tests': 1}
    source = action['files']['tests/test_value.py']
    if 'assert True' in source:
        return {'status': 'PASS', 'tests': 1}
    if 'inspect.getsource' in source:
        return {'status': 'PASS' if 'return 1' in reference['api.py'] else 'ASSERTION_FAIL', 'tests': 1}
    return {'status': 'ASSERTION_FAIL' if zero else 'PASS', 'tests': 1}


def _contract_case_frozen_candidate_needs_separate_review_and_native_audit(frozen, tmp_path):
    root, runtime, make = frozen
    generation = make()
    missing = audit_candidate(str(root), str(generation), str(runtime), str(tmp_path / 'missing.json'),
                              str(tmp_path / 'missing-review'), execute=execution)
    assert missing['state'] == 'INCOMPLETE' and not (tmp_path / 'missing-review/prediction.json').exists()
    review = reviewed(root, generation, tmp_path)
    result = audit_candidate(str(root), str(generation), str(runtime), str(review), str(tmp_path / 'audit'), execute=execution)
    assert result['state'] == 'PASS' and result['passed'] is True
    assert result['test_runs'] == 6 and result['model_calls'] == 2
    assert result['evidence']['metrics']['activated'] == 1
    assert result['evidence']['metrics']['evaluated'] == 2
    assert (tmp_path / 'audit/prediction.json').read_bytes() == (generation / 'candidate.json').read_bytes()


@pytest.mark.parametrize('kind,metric', [('vacuous', 'false_accepts'), ('overspecific', 'false_rejects')])
def test_real_native_policy_rejects_vacuous_and_overspecific_specs(frozen, tmp_path, kind, metric):
    """C-8.5 - it records a false accept or false reject and rejects the spec."""
    root, runtime, make = frozen
    generation = make(test_kind=kind)
    review = reviewed(root, generation, tmp_path)
    result = audit_candidate(str(root), str(generation), str(runtime), str(review), str(tmp_path / 'audit'), execute=execution)
    assert result['state'] == 'FAIL' and result['evidence']['metrics'][metric] == 1
    assert not (tmp_path / 'audit/prediction.json').exists()


def test_incomplete_scope_and_exhausted_shared_budget_never_publish(frozen, tmp_path):
    """C-8.4 - no prediction is published and evidence remains incomplete."""
    root, runtime, make = frozen
    generation = make(max_runs=1)
    review = reviewed(root, generation, tmp_path)
    def never(*args):
        pytest.fail('exhausted shared budget launched execution')
    result = audit_candidate(str(root), str(generation), str(runtime), str(review), str(tmp_path / 'budget'), execute=never)
    assert result['state'] == 'INCOMPLETE' and result['test_runs'] == 1
    data = json.loads(review.read_text())
    data['passports'] = []
    review.write_text(json.dumps(data))
    scoped = audit_candidate(str(root), str(generation), str(runtime), str(review), str(tmp_path / 'scope'), execute=never)
    assert scoped['state'] == 'INCOMPLETE'


def test_changed_candidate_native_artifact_or_review_is_rejected(frozen, tmp_path):
    root, runtime, make = frozen
    generation = make()
    review = reviewed(root, generation, tmp_path)
    data = json.loads(review.read_text())
    data['candidate_sha256'] = 'wrong'
    review.write_text(json.dumps(data))
    result = audit_candidate(str(root), str(generation), str(runtime), str(review), str(tmp_path / 'stale'), execute=execution)
    assert result['state'] == 'INCOMPLETE'
    scenarios = generation / 'native/attempt-001/scenarios.md'
    scenarios.write_text('changed')
    with pytest.raises(ValueError, match='artifacts'):
        load_candidate(str(root), str(generation))


def test_review_and_trust_cli_are_dry_by_default(frozen, tmp_path, capsys):
    """C-8.6 - no model calls, execution or output artifacts occur."""
    from evals.tddbench.__main__ import main
    root, runtime, make = frozen
    generation = make()
    review_out, audit_out = tmp_path / 'review-cli', tmp_path / 'audit-cli'
    assert main(['review', '--workspace', str(root), '--generation', str(generation), '--out', str(review_out),
                 '--endpoint', 'http://localhost:8000/v1', '--model', 'model']) == 0
    assert json.loads(capsys.readouterr().out)['executed'] is False
    assert main(['trust', '--workspace', str(root), '--generation', str(generation), '--runtime', str(runtime),
                 '--review', str(tmp_path / 'missing.json'), '--out', str(audit_out)]) == 0
    assert json.loads(capsys.readouterr().out)['executed'] is False
    assert not review_out.exists() and not audit_out.exists()


def test_review_cannot_omit_bound_specs_or_add_free_model_calls(frozen, tmp_path):
    root, runtime, make = frozen
    generation = make(extra_scenario=True)
    review = reviewed(root, generation, tmp_path)
    def never(*args):
        pytest.fail('invalid review reached execution')
    omitted = audit_candidate(str(root), str(generation), str(runtime), str(review), str(tmp_path / 'omitted'), execute=never)
    assert omitted['state'] == 'INCOMPLETE'
    data = json.loads(review.read_text())
    data['calls'] = 2
    review.write_text(json.dumps(data))
    over = audit_candidate(str(root), str(generation), str(runtime), str(review), str(tmp_path / 'over-budget'), execute=never)
    assert over['state'] == 'INCOMPLETE' and over['model_calls'] == 3


def test_truncated_review_is_charged_and_never_publishes(frozen, tmp_path):
    root, runtime, make = frozen
    generation = make()
    class Reviewer:
        model = 'scripted-review'
        source_kind = 'scripted-control'
        def __call__(self, *args):
            return {'text': json.dumps(review_payload()), 'finish_reason': 'length'}
    out = tmp_path / 'truncated-review'
    reviewed_result = create_review(str(root), str(generation), str(out), Reviewer())
    assert reviewed_result['state'] == 'INCOMPLETE' and reviewed_result['calls'] == 1
    result = audit_candidate(str(root), str(generation), str(runtime), str(out / 'review.json'), str(tmp_path / 'audit'))
    assert result['state'] == 'INCOMPLETE' and result['model_calls'] == 2
    assert not (tmp_path / 'audit/prediction.json').exists()


def test_frozen_candidate_needs_separate_review_and_native_audit_C_8_1(frozen, tmp_path):
    """C-8.1 - it awaits review and no prediction exists until a successful native audit."""
    _contract_case_frozen_candidate_needs_separate_review_and_native_audit(frozen, tmp_path)


def test_frozen_candidate_needs_separate_review_and_native_audit_C_8_2(frozen, tmp_path):
    """C-8.2 - the review is candidate-bound, uses its own context and consumes the original total budget."""
    _contract_case_frozen_candidate_needs_separate_review_and_native_audit(frozen, tmp_path)


def test_frozen_candidate_needs_separate_review_and_native_audit_C_8_3(frozen, tmp_path):
    """C-8.3 - activation and candidate tests never share their submitted test files and the native evidence is retained."""
    _contract_case_frozen_candidate_needs_separate_review_and_native_audit(frozen, tmp_path)
