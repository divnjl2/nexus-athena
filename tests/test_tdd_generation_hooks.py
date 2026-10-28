"""Optional coordinator hooks retain legacy behavior and cannot enlarge local limits."""
import json
from test_tdd_execution import public_runtime
from test_tdd_native import proposal
from evals.tddbench.generator import Budget,generate_direct


def test_shared_reservations_stop_before_model_contact(public_runtime,tmp_path):
    root,runtime=public_runtime;calls=[]
    def model(*args):calls.append(1)
    result=generate_direct(str(root),str(tmp_path/'generation'),model,mode='athena-trust',
        runtime_receipt=str(runtime),budget_view=lambda:{'model_calls_available':0,'test_runs_available':2})
    assert result['status']=='INCOMPLETE' and result['calls']==0 and not calls
    assert result['reason']=='shared generation budget exhausted or reserved'


def test_shared_view_cannot_grant_more_calls_than_the_local_cap(public_runtime,tmp_path):
    root,runtime=public_runtime;seen=[]
    def model(messages,budget):
        seen.append(json.loads(messages[-1]['content'])['execution_budget'])
        return {'text':json.dumps({'action':'read','path':'api.py'}),'finish_reason':'stop'}
    result=generate_direct(str(root),str(tmp_path/'generation'),model,mode='athena-trust',
        runtime_receipt=str(runtime),budget=Budget(max_calls=2),
        budget_view=lambda:{'model_calls_available':999,'test_runs_available':999})
    assert result['calls']==len(seen)==1
    assert seen[0]['generation_calls_available_including_current']==1


def test_hook_rejection_returns_feedback_before_execution_and_observer_cannot_rewrite_candidate(public_runtime,tmp_path):
    root,runtime=public_runtime;inputs=[];hooks=[];executed=[];candidate=proposal()
    guidance={'intent':{'id':'I1','obligation':'public value one'},'feedback':[]}
    def model(messages,budget):
        inputs.append(messages)
        assert 'semantic_cycle' in json.loads(messages[1]['content'])
        return {'text':json.dumps({'action':'finish','proposal':candidate}),'finish_reason':'stop'}
    def observe(value,index):
        hooks.append(index)
        if index==1:raise ValueError('intent binding needs repair')
        value['files']['tests/test_value.py']='def test_value():\n    assert True\n'
    def execute(directory,receipt,destination,action,*,timeout,implementation,purpose):
        executed.append(purpose)
        assert action['files']==candidate['files']
        assert implementation=={'api.py':'def value():\n    return 1\n'}
        return {'status':'PASS','tests':1}
    out=tmp_path/'generation'
    result=generate_direct(str(root),str(out),model,mode='athena-trust',runtime_receipt=str(runtime),
        budget=Budget(max_calls=3),guidance=guidance,proposal_hook=observe,test_executor=execute)
    assert result['status']=='AWAITING_REVIEW' and result['calls']==2
    assert hooks==[1,2] and executed==['native-baseline']
    assert 'intent binding needs repair' in inputs[1][-1]['content']
    assert json.loads((out/'candidate-proposal.json').read_text())['files']==candidate['files']
    assert guidance=={'intent':{'id':'I1','obligation':'public value one'},'feedback':[]}


def test_manual_test_action_is_distinguished_from_native_baseline(public_runtime,tmp_path):
    root,runtime=public_runtime;purposes=[]
    def model(*args):
        return {'text':json.dumps({'action':'run','files':{'tests/test_x.py':'assert True\n'},
                                  'tests':['tests/test_x.py']}),'finish_reason':'stop'}
    def execute(*args,**kwargs):
        purposes.append(kwargs['purpose']);return {'status':'PASS','tests':1}
    result=generate_direct(str(root),str(tmp_path/'generation'),model,mode='athena-trust',
                           runtime_receipt=str(runtime),budget=Budget(max_calls=2),test_executor=execute)
    assert result['test_runs']==1 and purposes==['exploration']
