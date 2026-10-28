import copy
import json
import pytest
from test_tdd_execution import public_runtime
from test_tdd_native import proposal
from test_tdd_trust import review_payload, execution
from evals.tddbench.intent import prepare_intent, digest, new_assertions
from evals.tddbench.semantic import check_controls, create_semantic_review, check_protocol
from evals.tddbench.trust import review_scope
from evals.tddbench.native import pytest_nodes
from evals.tddbench.generator import Budget, generate_direct
from evals.tddbench.lineage import Journal, Limits
from evals.tddbench.trust import audit_candidate


def profile(issue, representation='specified'):
    return prepare_intent(issue, {'requirements': [{'id': 'I1', 'obligation': 'Return the expected value',
        'quotes': [issue['problem_statement']], 'representation': representation}], 'assumptions': [], 'unresolved': []})


def semantic_payload(issue, proposal, *, unsupported=False):
    payload = review_payload()
    valid = payload['passports'][0]['variants'][0]
    valid.update(files=[{'path': 'api.py', 'old': 'return 1', 'new': 'return sum([1])'}],
        distinction='mechanism', distinction_reason='aggregate instead of literal return',
        source_quotes=[issue['problem_statement']])
    payload['intent_reviews'] = [{'intent': 'I1', 'status': 'SUPPORTED', 'reason': 'public task'}]
    payload['assertion_reviews'] = [{'assertion': a['id'], 'status': 'UNJUSTIFIED' if unsupported else 'SUPPORTED',
        'reason': 'literal is unsupported' if unsupported else 'observable value required',
        'intents': ['I1'], 'quotes': [issue['problem_statement']]} for a in new_assertions(proposal['files'], {})]
    return payload


def test_structurally_unchanged_and_duplicate_controls_cannot_supply_diversity(public_runtime):
    """C-3.1 - Identical and duplicate controls cannot establish declared diversity."""
    root, _ = public_runtime
    issue = json.loads((root/'issue.json').read_bytes()); intent = profile(issue, 'open')
    p = proposal(); p['intent_bindings'] = {'C-1.1': ['I1']}
    payload = semantic_payload(issue, p)
    assert check_controls(str(root), issue, intent, p, payload)['state'] == 'INCOMPLETE'
    alternative = copy.deepcopy(payload['passports'][0]['variants'][0])
    alternative.update(id='representation', distinction='representation',
        files=[{'path': 'api.py', 'old': 'return 1', 'new': 'return float(1)'}])
    payload['passports'][0]['variants'].append(alternative)
    assert check_controls(str(root), issue, intent, p, payload)['state'] == 'PASS'
    alternative['files'] = copy.deepcopy(payload['passports'][0]['variants'][0]['files'])
    assert check_controls(str(root), issue, intent, p, payload)['state'] == 'INCOMPLETE'
    payload['passports'][0]['variants'][0]['files'][0]['new'] = 'return (1)'
    assert check_controls(str(root), issue, profile(issue), p, payload)['state'] == 'INCOMPLETE'


def test_fresh_review_binds_pre_generation_intent_and_does_not_publish_native_alone(public_runtime, tmp_path, monkeypatch):
    import evals.tddbench.execution as tools
    monkeypatch.setattr(tools, 'run_tests', lambda *a, **k: {'status': 'PASS', 'tests': 1})
    root, runtime = public_runtime; issue = json.loads((root/'issue.json').read_bytes())
    p = proposal(); p['intent_bindings'] = {'C-1.1': ['I1']}
    class Model:
        source_kind = 'scripted-control'; model = 'control'
        def __call__(self, messages, budget):
            if 'Derive an intent' in messages[0]['content']: raise AssertionError('intent already derived')
            return {'text': json.dumps({'action': 'finish', 'proposal': p}), 'finish_reason': 'stop'}
    gen = tmp_path/'generation'; intent = profile(issue)
    generate_direct(str(root), str(gen), Model(), mode='athena-trust', runtime_receipt=str(runtime),
        budget=Budget(max_calls=3, max_test_runs=12), guidance={'intent': intent})
    journal = Journal.create(tmp_path/'journal', Limits(3,12), digest(issue))
    class Reviewer:
        source_kind = 'scripted-control'; model = 'control'
        def __call__(self, messages, budget):
            context = json.loads(messages[1]['content'])
            assert context['intent'] == intent and context['assertion_manifest']
            assert 'previous_public_feedback' not in context
            return {'text': json.dumps(semantic_payload(issue,p)), 'finish_reason':'stop'}
    review = tmp_path/'review'
    r = create_semantic_review(str(root),str(gen),str(review),Reviewer(),journal,budget=Budget(),phase='review:1')
    assert r['state']=='READY' and r['support']['state']=='PASS' and r['diversity']['state']=='PASS'
    assert r['protocol']['state']=='PASS'
    assert journal.snapshot()['spent']['model_calls']==1
    a = audit_candidate(str(root),str(gen),str(runtime),str(review/'review.json'),str(tmp_path/'audit'),execute=execution,publish=False)
    assert a['state']=='PASS' and not (tmp_path/'audit/prediction.json').exists()
    (gen/'semantic-guidance.json').write_text('{}')
    with pytest.raises(ValueError,match='guidance'):
        create_semantic_review(str(root),str(gen),str(tmp_path/'stale'),Reviewer(),journal,budget=Budget(),phase='review:2')


@pytest.mark.parametrize('status', ['TOOL_ERROR','TIMEOUT','SKIP','COLLECTION_ERROR'])
def test_controls_never_promote_inconclusive_native_execution(public_runtime,tmp_path,monkeypatch,status):
    # Reuse real native policy; typed execution uncertainty is independent of declarations.
    import evals.tddbench.execution as tools
    monkeypatch.setattr(tools,'run_tests',lambda *a,**k:{'status':'PASS','tests':1})
    root,runtime=public_runtime;issue=json.loads((root/'issue.json').read_bytes());p=proposal()
    class Model:
        source_kind='scripted-control'
        def __call__(self,*args):return {'text':json.dumps({'action':'finish','proposal':p}),'finish_reason':'stop'}
    gen=tmp_path/'g';generate_direct(str(root),str(gen),Model(),mode='athena-trust',runtime_receipt=str(runtime))
    review=review_payload();review.update(schema='athena.tdd_review/1',state='READY',calls=0,
        reviewer_id='control',origin='scripted-control',
        candidate_sha256=json.loads((gen/'receipt.json').read_bytes())['candidate_sha256'],
        snapshot_sha256=json.loads((gen/'receipt.json').read_bytes())['snapshot_sha256'])
    path=tmp_path/'r.json';path.write_text(json.dumps(review))
    a=audit_candidate(str(root),str(gen),str(runtime),str(path),str(tmp_path/'a'),execute=lambda *args:{'status':status})
    assert a['state']=='INCOMPLETE' and not a['passed']


@pytest.mark.parametrize('field',['activation_object','intent_source_list','missing_clause','wrong_specs'])
def test_protocol_diagnostics_reject_calibration_schema_failures_before_execution(field):
    p=proposal();payload=review_payload()
    if field=='activation_object':
        v=payload['passports'][0]['variants'][1];v['activation']={'run_cmd':v['activation']}
    elif field=='intent_source_list':payload['passports'][0]['intent_source']=['I1']
    elif field=='missing_clause':payload['passports']=[]
    else:payload['passports'][0]['specs']=['unbound']
    result=check_protocol(p,payload)
    assert result['state']=='INCOMPLETE' and result['problems']
    if field=='activation_object':assert 'string' in result['problems'][0]


def test_controller_live_scope_resolves_supersession_and_retains_other_live_obligations():
    p=proposal()
    p['contract']+='\n- **C-1.2** — WHEN requested THE SYSTEM SHALL preserve its numeric meaning.\n'
    p['contract']+='\n- **C-2.1** *(supersedes C-1.1)* — WHEN requested THE SYSTEM SHALL return the expected value.\n'
    p['scenarios']+=p['scenarios'][p['scenarios'].index('### S1.1'):].replace('S1.1','S2.1').replace('C-1.1','C-2.1')
    scope=review_scope(p)
    assert [r['clause'] for r in scope]==['C-1.2','C-2.1']
    assert scope[0]['specs']==[] and scope[1]['specs']==['S2.1']
    with pytest.raises(ValueError,match='string'):
        pytest_nodes({'run_cmd':'python -m pytest tests/test_value.py -q'},p['files'])
