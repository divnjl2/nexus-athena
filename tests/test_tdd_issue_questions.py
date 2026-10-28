import copy,json
import pytest
from test_tdd_execution import public_runtime
from test_tdd_native import proposal
from test_tdd_semantic_controls import semantic_payload
from test_tdd_cycle import CycleModel
from test_tdd_trust import execution
from evals.tddbench.intent import prepare_intent,check_support,digest
from evals.tddbench.trust import candidate_digest
from evals.tddbench.cycle import run_cycle
from evals.tddbench.generator import Budget


def evidence(issue):
    p=proposal();p['intent_bindings']={'C-1.1':['I1']}
    profile=prepare_intent(issue,{'requirements':[{'id':'I1','obligation':'Return the expected value',
        'quotes':[issue['problem_statement']],'representation':'specified'}],
        'assumptions':[],'unresolved':['No example input provided.']})
    review=semantic_payload(issue,p)
    review.update(issue_sha256=digest(issue),intent_sha256=profile['sha256'],candidate_sha256=candidate_digest(p))
    review['uncertainty_reviews']=[{'question':'U1','status':'NONBLOCKING',
        'reason':'The observable expected result permits a concrete input in the test.',
        'quotes':[issue['problem_statement']],'source_quotes':[]}]
    return profile,p,review


def test_nonblocking_question_requires_specific_public_evidence_without_erasing_history(public_runtime):
    """C-1.3 - Open issue questions require source-checked resolution before release."""
    root,_=public_runtime;issue=json.loads((root/'issue.json').read_bytes());profile,p,review=evidence(issue)
    assert check_support(issue,profile,p,{},review)['state']=='PASS'
    assert profile['unresolved']==['No example input provided.']
    review['uncertainty_reviews'][0].update(quotes=[],source_quotes=[{'path':'api.py','quote':'pass'}])
    assert check_support(issue,profile,p,{'api.py':'pass\n'},review)['state']=='PASS'
    assert check_support(issue,profile,p,{'api.py':'different public code\n'},review)['state']=='INCOMPLETE'


@pytest.mark.parametrize('change',['missing','unknown','duplicate','unsupported','unresolved'])
def test_unanswered_or_unjustified_question_cannot_release(public_runtime,change):
    root,_=public_runtime;issue=json.loads((root/'issue.json').read_bytes());profile,p,review=evidence(issue)
    rows=review['uncertainty_reviews']
    if change=='missing':rows.clear()
    elif change=='unknown':rows[0]['question']='U2'
    elif change=='duplicate':rows.append(copy.deepcopy(rows[0]))
    elif change=='unsupported':rows[0]['quotes']=[]
    else:rows[0]['status']='UNRESOLVED'
    assert check_support(issue,profile,p,{},review)['state']=='INCOMPLETE'


def test_question_can_be_reviewed_after_public_generation_without_early_abandonment(public_runtime,tmp_path):
    root,runtime=public_runtime;issue=json.loads((root/'issue.json').read_bytes())
    class Questions(CycleModel):
        def __call__(self,messages,budget):
            reply=super().__call__(messages,budget);payload=json.loads(reply['text'])
            if 'Derive an intent passport' in messages[0]['content']:payload['unresolved']=['No example input provided.']
            elif 'Review a frozen' in messages[0]['content']:
                payload['uncertainty_reviews']=evidence(issue)[2]['uncertainty_reviews']
            reply['text']=json.dumps(payload);return reply
    model=Questions(issue)
    r=run_cycle(str(root),str(runtime),str(tmp_path/'cycle'),model,budget=Budget(max_calls=12,max_test_runs=24),execute=execution)
    assert r['intent']['state']=='INCOMPLETE' and r['released'] and model.reviews==2
    first=json.loads((tmp_path/'cycle/attempt-001/review/review.json').read_bytes())
    assert first['support']['uncertainty_reviews'][0]['status']=='NONBLOCKING'
