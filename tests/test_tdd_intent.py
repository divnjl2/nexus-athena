"""Issue-only framing, exact quotations and append-only intent revisions."""
import copy
import json
import pytest
from evals.tddbench.generator import Budget
from evals.tddbench.intent import derive_intent,digest,prepare_intent,verify_intent
from evals.tddbench.lineage import Journal,Limits


def make_issue():
    return {'instance_id':'owner__project-1','repo':'owner/project','base_commit':'a'*40,
            'problem_statement':'Show complete numeric values; equivalent numeric representations are allowed.'}


def make_declaration():
    return {'requirements':[{'id':'I1','obligation':'Preserve numeric magnitude',
        'quotes':['Show complete numeric values'],'representation':'open'}],
        'assumptions':[],'unresolved':[]}


def test_quotations_bind_to_unchanged_issue_without_attesting_meaning():
    issue=make_issue();profile=prepare_intent(issue,make_declaration())
    row=profile['requirements'][0];span=row['source_spans'][0]
    assert issue['problem_statement'][span['start']:span['end']]==span['quote']
    assert profile['validity']=='MODEL_DECLARED_NOT_ATTESTED'
    verify_intent(issue,profile)
    changed={**issue,'problem_statement':'Always print the literal 1e6.'}
    with pytest.raises(ValueError,match='changed'):verify_intent(changed,profile)


def test_missing_quote_or_recomputed_false_span_cannot_pass_validation():
    issue=make_issue();raw=make_declaration();raw['requirements'][0]['quotes']=['Always print 1e6']
    with pytest.raises(ValueError,match='absent'):prepare_intent(issue,raw)
    profile=prepare_intent(issue,make_declaration());profile['requirements'][0]['source_spans'][0]['start']=5
    profile['sha256']=digest({k:v for k,v in profile.items() if k!='sha256'})
    with pytest.raises(ValueError,match='source evidence'):verify_intent(issue,profile)


def test_intent_revision_retains_old_words_and_explicit_supersession():
    issue=make_issue();old=prepare_intent(issue,make_declaration())
    raw={k:copy.deepcopy(old[k]) for k in ('assumptions','unresolved')}
    raw['requirements']=[{k:copy.deepcopy(old['requirements'][0][k]) for k in
        ('id','obligation','quotes','representation','supersedes','revision_reason')}]
    raw['requirements'].append({'id':'I2','obligation':'Accept equivalent numeric representations',
       'quotes':['equivalent numeric representations are allowed.'],'representation':'open',
       'supersedes':['I1'],'revision_reason':'Make representation freedom explicit.'})
    revised=prepare_intent(issue,raw,previous=old)
    assert revised['previous_sha256']==old['sha256']
    assert [r['is_live'] for r in revised['requirements']]==[False,True]
    assert old['requirements'][0]['is_live'] is True
    raw['requirements'][0]['obligation']='Silently overwrite the original promise'
    with pytest.raises(ValueError,match='preserve'):prepare_intent(issue,raw,previous=old)


def test_issue_only_model_context_and_charged_frozen_result(tmp_path):
    """C-1.1 - Issue-only intent precedes implementation and retains charged source-bound evidence."""
    issue=make_issue();journal=Journal.create(tmp_path/'journal',Limits(3,6),'a'*64)
    journal.reserve('review',model_calls=1)
    seen=[]
    class Model:
        source_kind='scripted-control'
        def __call__(self,messages,budget):
            seen.append(messages)
            payload=json.loads(messages[1]['content'])
            assert set(payload)=={'issue','execution_budget'} and payload['issue']==issue
            assert 'candidate' not in payload and 'reference' not in payload
            return {'text':json.dumps(make_declaration()),'finish_reason':'stop',
                    'usage':{'input_tokens':10,'output_tokens':20}}
    out=tmp_path/'intent';result=derive_intent(issue,Model(),journal,out,budget=Budget())
    assert result['state']=='READY' and len(seen)==1
    assert journal.snapshot()['spent']['model_calls']==1
    verify_intent(issue,json.loads((out/'intent.json').read_text()))
    with pytest.raises(FileExistsError):derive_intent(issue,Model(),journal,out,budget=Budget())


def test_invalid_model_declaration_stays_incomplete_and_spent(tmp_path):
    journal=Journal.create(tmp_path/'journal',Limits(2,2),'a'*64)
    class Model:
        def __call__(self,*args):
            raw=make_declaration();raw['requirements'][0]['quotes']=['Unsupported literal 1e6']
            return {'text':json.dumps(raw),'finish_reason':'stop'}
    out=tmp_path/'intent';result=derive_intent(make_issue(),Model(),journal,out,budget=Budget())
    assert result['state']=='INCOMPLETE' and not (out/'intent.json').exists()
    assert (out/'response.json').exists() and journal.snapshot()['spent']['model_calls']==1


def test_private_fields_are_rejected_before_contacting_a_model(tmp_path):
    journal=Journal.create(tmp_path/'journal',Limits(2,2),'a'*64)
    def never(*args):pytest.fail('private issue reached a model')
    with pytest.raises(ValueError,match='four public'):
        derive_intent({**make_issue(),'patch':'private gold'},never,journal,tmp_path/'intent',budget=Budget())
    assert journal.snapshot()['spent']['model_calls']==0 and not (tmp_path/'intent').exists()


def test_unresolved_intent_is_preserved_without_ready_claim(tmp_path):
    journal=Journal.create(tmp_path/'journal',Limits(2,2),'a'*64)
    def model(*args):
        raw=make_declaration();raw['unresolved']=['Does the magnitude belong in labels or title?']
        return {'text':json.dumps(raw),'finish_reason':'stop'}
    out=tmp_path/'intent';result=derive_intent(make_issue(),model,journal,out,budget=Budget())
    assert result['state']=='INCOMPLETE' and (out/'intent.json').exists()
    assert json.loads((out/'intent.json').read_text())['unresolved']
