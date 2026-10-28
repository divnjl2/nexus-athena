"""Cost disclosure follows actual scenario bindings and leaves budgets unchanged."""
import json
import pytest
from test_tdd_execution import public_runtime
from test_tdd_trust import frozen,review_payload
from evals.tddbench.trust import create_review


@pytest.mark.parametrize('extra,bound,available,minimum,requested',[(False,1,7,5,6),(True,2,6,8,10)])
def test_review_receives_shared_budget_and_bound_command_costs(frozen,tmp_path,extra,bound,available,minimum,requested):
    """C-8.11 - accurate remaining limits and execution estimates reach the reviewer and transcript without extra budget."""
    root,runtime,make=frozen
    generation=make(extra_scenario=extra)
    captured=[]
    class Reviewer:
        source_kind='scripted-control'
        model='review-cost-control'
        def __call__(self,messages,budget):
            payload=json.loads(messages[1]['content']);current=payload['execution_budget']
            captured.append(current)
            assert current['model_calls_available_including_this_review']==1
            assert current['this_review_max_calls']==1 and current['test_runs_available']==available
            assert current['bound_commands_per_clause']=={'C-1.1':bound}
            assert current['runs_for_one_valid_one_violation_per_clause']==minimum
            assert current['runs_for_two_valid_one_violation_per_clause']==requested
            assert current['output_tokens_acceptance_limit']==4096
            assert current['execution_phase']=='review_precedes_native_control_execution'
            assert 'pending execution is a phase status' in messages[0]['content']
            assert budget.max_calls==2 and budget.max_test_runs==8
            return {'text':json.dumps(review_payload()),'finish_reason':'stop'}
    out=tmp_path/'review'
    review=create_review(str(root),str(generation),str(out),Reviewer())
    assert review['state']=='READY' and review['calls']==1 and len(captured)==1
    saved=json.loads((out/'transcript.json').read_text())
    assert json.loads(saved[1]['content'])['execution_budget']==captured[0]
