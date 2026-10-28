import copy
import json
import pytest
from test_tdd_execution import public_runtime
from test_tdd_native import proposal
from test_tdd_trust import execution
from test_tdd_semantic_controls import profile, semantic_payload
from evals.tddbench.cycle import run_cycle, preserve_requirements
from evals.tddbench.generator import Budget


class CycleModel:
    source_kind='scripted-control'; model='scripted-cycle'
    def __init__(self,issue,*,never_support=False):
        self.issue=issue;self.reviews=0;self.generations=0;self.inputs=[];self.never_support=never_support
    def __call__(self,messages,budget):
        self.inputs.append(copy.deepcopy(messages))
        system=messages[0]['content'];context=json.loads(messages[1]['content'])
        if 'Derive an intent passport' in system:
            raw=profile(self.issue)
            declaration={'requirements':[{k:r[k] for k in ('id','obligation','quotes','representation','supersedes','revision_reason')}
                for r in raw['requirements']], 'assumptions':[],'unresolved':[]}
            return {'text':json.dumps(declaration),'finish_reason':'stop'}
        if 'Review a frozen' in system:
            self.reviews+=1
            return {'text':json.dumps(semantic_payload(self.issue,self.last,unsupported=self.reviews==1 or self.never_support)),
                'finish_reason':'stop','usage':{'output_tokens':10}}
        self.generations+=1
        if self.generations==2:
            assert context['semantic_cycle']['previous_public_feedback']['review']['support']['state']=='FAIL'
        p=proposal();p['intent_bindings']={'C-1.1':['I1']}
        if self.generations>1:p['files']['tests/test_value.py']=p['files']['tests/test_value.py'].replace('value() == 1','1 == value()')
        self.last=p
        return {'text':json.dumps({'action':'finish','proposal':p}),'finish_reason':'stop'}


def test_cycle_repairs_with_fresh_review_preserves_history_and_releases_exact_patch(public_runtime,tmp_path):
    """C-2.1 - Repair receives a fresh review and preserves the exact immutable candidate history."""
    root,runtime=public_runtime;issue=json.loads((root/'issue.json').read_bytes());model=CycleModel(issue)
    out=tmp_path/'cycle'
    r=run_cycle(str(root),str(runtime),str(out),model,budget=Budget(max_calls=12,max_test_runs=24),execute=execution)
    assert r['state']=='PASS' and r['released'] and model.reviews==2 and model.generations==2, r
    assert [a['native_state'] for a in r['attempts']]==['PASS','PASS']
    assert [a['state'] for a in r['attempts']]==['INCOMPLETE','PASS']
    assert r['resources']['spent']=={'model_calls':5,'test_runs':12}
    assert r['resources']['observed_usage']['output_tokens']==20
    assert r['resources']['missing_usage_fields']['output_tokens']==3
    assert (out/'prediction.json').read_bytes()==(out/'attempt-002/generation/candidate.json').read_bytes()
    assert not (out/'attempt-001/audit/prediction.json').exists()
    one=json.loads((out/'attempt-001/review/review.json').read_bytes());two=json.loads((out/'attempt-002/review/review.json').read_bytes())
    assert one['candidate_sha256']!=two['candidate_sha256']
    assert (out/'attempt-001/proposals/001/prediction.json').exists()
    assert (out/'attempt-001-manifest.json').exists()
    with pytest.raises(FileExistsError):run_cycle(str(root),str(runtime),str(out),model,execute=execution)


def test_advisory_negative_never_becomes_native_failure_and_no_release_on_exhaustion(public_runtime,tmp_path):
    root,runtime=public_runtime;issue=json.loads((root/'issue.json').read_bytes())
    r=run_cycle(str(root),str(runtime),str(tmp_path/'cycle'),CycleModel(issue,never_support=True),
        budget=Budget(max_calls=12,max_test_runs=24),execute=execution)
    assert r['state']=='INCOMPLETE' and not r['released'] and len(r['attempts'])==2
    assert all(a['native_state']=='PASS' for a in r['attempts'])
    r=run_cycle(str(root),str(runtime),str(tmp_path/'small'),CycleModel(issue),
        budget=Budget(max_calls=12,max_test_runs=13),execute=execution)
    assert r['state']=='INCOMPLETE' and r['resources']['spent']=={'model_calls':0,'test_runs':0}
    assert not (tmp_path/'small/prediction.json').exists()


def test_requirement_repairs_must_preserve_ids_and_supersede():
    p=proposal();q=copy.deepcopy(p)
    q['contract']=q['contract'].replace('return one','return a number')
    with pytest.raises(ValueError,match='rewrote'):preserve_requirements(p,q)
    q['contract']=p['contract']+'\n- **C-1.2** *(supersedes C-1.1)* — WHEN value is requested THE SYSTEM SHALL return the expected value.\n'
    preserve_requirements(p,q)
    q['contract']=p['contract'].replace('**C-1.1**','**C-1.1** *(withdrawn)*')
    with pytest.raises(ValueError,match='dropped'):preserve_requirements(p,q)


def test_draft_promotion_preserves_identity_but_retired_requirements_cannot_revive():
    p=proposal();p['contract']=p['contract'].replace('**C-1.1**','**C-1.1** *(draft)*')
    q=copy.deepcopy(p);q['contract']=q['contract'].replace(' *(draft)*','')
    preserve_requirements(p,q)
    withdrawn=copy.deepcopy(p);withdrawn['contract']=withdrawn['contract'].replace('*(draft)*','*(withdrawn)*')
    preserve_requirements(p,withdrawn)
    with pytest.raises(ValueError,match='revived'):preserve_requirements(withdrawn,q)


def test_expanded_scope_is_reserved_before_native_execution_without_dropping_clauses(public_runtime,tmp_path):
    root,runtime=public_runtime;issue=json.loads((root/'issue.json').read_bytes())
    class Expanded(CycleModel):
        def __call__(self,messages,budget):
            reply=super().__call__(messages,budget)
            value=json.loads(reply['text'])
            if value.get('action')=='finish':
                p=value['proposal'];p['contract']+='\n- **C-1.2** — WHEN value is requested THE SYSTEM SHALL preserve its required numeric meaning.\n'
                p['scenarios']+=p['scenarios'][p['scenarios'].index('### S1.1'):].replace('S1.1','S1.2').replace('C-1.1','C-1.2')
                p['intent_bindings']['C-1.2']=['I1'];reply['text']=json.dumps(value)
            return reply
    def never(*args):pytest.fail('insufficient complete-cycle reservation launched a test')
    out=tmp_path/'cycle'
    r=run_cycle(str(root),str(runtime),str(out),Expanded(issue),budget=Budget(max_calls=12,max_test_runs=20),execute=never)
    assert r['state']=='INCOMPLETE' and not r['released']
    assert r['resources']['spent']=={'model_calls':2,'test_runs':0}
    p=json.loads((out/'attempt-001/proposals/001/proposal.json').read_bytes())
    assert 'C-1.2' in p['contract'] and (out/'attempt-001/proposals/001/prediction.json').exists()
    assert (out/'attempt-001-manifest.json').exists()
    forecast=json.loads((out/'attempt-001/proposals/001/budget-plan.json').read_bytes())
    assert forecast['required']['test_runs']==28 and forecast['available_before_forward']['test_runs']==20
    assert forecast['shortfall']['test_runs']==8 and forecast['feasible'] is False


def test_changed_earlier_attempt_during_repair_prevents_final_release(public_runtime,tmp_path):
    root,runtime=public_runtime;issue=json.loads((root/'issue.json').read_bytes());out=tmp_path/'cycle'
    counter=0
    def altered(action,reference):
        nonlocal counter
        counter+=1
        if counter==8:(out/'attempt-001/outcome.json').write_text('changed by another writer')
        return execution(action,reference)
    r=run_cycle(str(root),str(runtime),str(out),CycleModel(issue),budget=Budget(max_calls=12,max_test_runs=24),execute=altered)
    assert r['state']=='INCOMPLETE' and not r['released'] and not (out/'prediction.json').exists()
