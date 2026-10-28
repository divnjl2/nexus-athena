import json
import pytest
from test_tdd_execution import public_runtime
from test_tdd_trust import frozen,review_payload,execution
from evals.tddbench import trust as preview,native

@pytest.mark.parametrize('flag',['--maxfail=1','-k','--ignore=tests/test_value.py'])
def test_unsupported_options_have_actionable_errors(flag):
    """C-8.9 - lossless inputs, budgets and execution guards remain honest."""
    with pytest.raises(ValueError,match='unsupported pytest option.*allowed flags'):
        native.pytest_nodes('python -m pytest tests/test_value.py '+flag,
                            {'tests/test_value.py':'def test_value(): pass\n'})

@pytest.mark.parametrize('flag',['-q','-v','-vv'])
def test_supported_command_selection_is_unchanged(flag):
    assert native.pytest_nodes('python -m pytest tests/test_value.py::test_value '+flag,
                               {'tests/test_value.py':'def test_value(): pass\n'})==['tests/test_value.py::test_value']

def make_review(root,generation,tmp_path):
    class Reviewer:
        source_kind='scripted-control';model='diagnostics-control'
        def __call__(self,messages,budget):
            payload=json.loads(messages[1]['content'])
            assert 'reference_delta' in payload and 'base_files' not in payload
            return {'text':json.dumps(review_payload()),'finish_reason':'stop'}
    destination=tmp_path/'review'
    result=preview.create_review(str(root),str(generation),str(destination),Reviewer())
    assert result['state']=='READY'
    return destination/'review.json'

@pytest.mark.parametrize('malformation',['unsupported-option','wrong-binding'])
def test_invalid_review_preserves_budget_and_diagnostic_without_execution(frozen,tmp_path,monkeypatch,malformation):
    """C-8.8 - lossless inputs, budgets and execution guards remain honest."""
    root,runtime,make=frozen;generation=make()
    review=make_review(root,generation,tmp_path)
    data=json.loads(review.read_text())
    if malformation=='unsupported-option':
        data['passports'][0]['variants'][1]['activation']+=' --maxfail=1'
        expected='unsupported pytest option'
    else:
        data['passports'][0]['specs'].append('S1.2')
        expected='review must challenge every spec bound to its clause'
    review.write_text(json.dumps(data))
    monkeypatch.setattr(preview,'pytest_nodes',native.pytest_nodes)
    def never(*args):pytest.fail('invalid review reached an execution tool')
    out=tmp_path/'audit'
    result=preview.audit_candidate(str(root),str(generation),str(runtime),str(review),str(out),execute=never)
    assert result['state']=='INCOMPLETE' and result['passed'] is False
    assert result['test_runs']==1 and result['model_calls']==2 and result['review_model_calls']==1
    assert result['error_type']=='ValueError' and expected in result['error_message']
    assert expected in result['reason']
    assert not (out/'prediction.json').exists()

def test_valid_review_still_requires_real_native_challenges(frozen,tmp_path,monkeypatch):
    root,runtime,make=frozen;generation=make()
    review=make_review(root,generation,tmp_path)
    monkeypatch.setattr(preview,'pytest_nodes',native.pytest_nodes)
    calls=[]
    def execute(action,reference):
        calls.append(action)
        return execution(action,reference)
    result=preview.audit_candidate(str(root),str(generation),str(runtime),str(review),str(tmp_path/'audit'),execute=execute)
    assert result['state']=='PASS' and result['passed'] is True
    assert result['test_runs']==6 and result['model_calls']==2 and len(calls)==5
    assert result['evidence']['metrics']['activated']==1
