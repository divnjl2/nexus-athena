"""Reviewer receives contrastive instructions; execution still decides outcomes."""
import json
import pytest
from test_tdd_execution import public_runtime
from test_tdd_trust import frozen, review_payload, execution
from evals.tddbench.trust import create_review, audit_candidate


@pytest.mark.parametrize('kind,expected,rejected', [('normal','PASS',0),('overspecific','FAIL',1)])
def test_contrastive_policy_reaches_reviewer_without_changing_native_outcomes(frozen,tmp_path,kind,expected,rejected):
    """C-8.10 - native execution still accepts the valid control and rejects the overspecific one within the same budget."""
    root,runtime,make=frozen
    generation=make(test_kind=kind)
    class Reviewer:
        source_kind='scripted-control'
        model='contrastive-protocol-control'
        def __call__(self,messages,budget):
            policy=messages[0]['content']
            assert 'materially different implementation' in policy
            assert 'different valid representation' in policy
            assert 'justify them from the\npublic issue, not from the proposed reference' in policy
            assert 'Retain real known_gaps' in policy
            assert 'do not attest semantic validity' in policy
            assert 'reference_delta' in json.loads(messages[1]['content'])
            assert budget.max_calls==2 and budget.max_test_runs==8
            return {'text':json.dumps(review_payload()),'finish_reason':'stop'}
    review=create_review(str(root),str(generation),str(tmp_path/'review'),Reviewer())
    assert review['state']=='READY' and review['calls']==1
    result=audit_candidate(str(root),str(generation),str(runtime),str(tmp_path/'review/review.json'),
                           str(tmp_path/'audit'),execute=execution)
    assert result['state']==expected and result['model_calls']==2
    assert result['test_runs']<=8 and result['evidence']['metrics']['false_rejects']==rejected
    assert (tmp_path/'audit/prediction.json').exists()==(expected=='PASS')
