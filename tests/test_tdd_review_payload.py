import copy,difflib,json
import pytest
from evals.tddbench import trust as preview

@pytest.mark.parametrize('old,new',[
    ('a\r\nb\r\n','a\r\nx\r\n'),
    ('a\nb','x\nb\n'),
    ('','x'),
    ('a\n',''),
])
def test_both_versions_round_trip_exactly(old,new):
    proposal={'reference':{'module.py':new},'contract':'intent','files':{'test_x.py':'assert True\n'}}
    original=copy.deepcopy(proposal)
    result=preview.review_payload({'issue':'public'},proposal,{'module.py':old},{'module.py':new})
    delta=result['reference_delta']['module.py']
    assert ''.join(difflib.restore(delta,1))==old
    assert ''.join(difflib.restore(delta,2))==new
    assert result['proposal']=={'contract':'intent','files':{'test_x.py':'assert True\n'}}
    assert proposal==original

def test_large_unchanged_source_fits_same_budget_without_loss():
    old=''.join(f'value_{i} = {i!r}  # public source\n' for i in range(2500))
    new=old.replace('value_1100 = 1100','value_1100 = 9999')
    proposal={'reference':{'module.py':new},'contract':'intent','files':{}}
    old_payload={'issue':{},'proposal':proposal,'base_files':{'module.py':old},'proposed_reference':{'module.py':new}}
    new_payload=preview.review_payload({},proposal,{'module.py':old},{'module.py':new})
    assert len(json.dumps(old_payload,ensure_ascii=False))>160000
    assert len(json.dumps(new_payload,ensure_ascii=False))<160000
    delta=new_payload['reference_delta']['module.py']
    assert ''.join(difflib.restore(delta,1))==old
    assert ''.join(difflib.restore(delta,2))==new

def test_missing_base_is_rejected():
    with pytest.raises(ValueError,match='paths differ'):
        preview.review_payload({}, {}, {}, {'missing.py':'x'})

def test_review_uses_lossless_payload_before_original_context_check(tmp_path,monkeypatch):
    """C-8.7 - lossless inputs, budgets and execution guards remain honest."""
    from dataclasses import asdict
    from evals.tddbench.generator import Budget
    old=''.join(f'value_{i} = {i!r}  # public source\n' for i in range(2500))
    new=old.replace('value_1100 = 1100','value_1100 = 9999')
    root=tmp_path/'public';(root/'source').mkdir(parents=True)
    (root/'source/module.py').write_text(old,encoding='utf-8')
    (root/'issue.json').write_text(json.dumps({'instance_id':'fixture','problem_statement':'public issue'}))
    from test_tdd_native import CONTRACT,SCENARIOS
    proposal={'contract':CONTRACT,'scenarios':SCENARIOS,'files':{},'reference':{'module.py':new}}
    receipt={'candidate_sha256':'candidate','snapshot_sha256':'snapshot','calls':1,
             'source_kind':'scripted-control','budget':asdict(Budget()),'execution_python':'3.9'}
    monkeypatch.setattr(preview,'load_candidate',lambda *a:(receipt,proposal,{}))
    monkeypatch.setattr(preview,'validate_reference',lambda *a:{'module.py':new})
    observed=[]
    class Reviewer:
        source_kind='scripted-control';model='payload-control'
        def __call__(self,messages,budget):
            observed.append(messages)
            assert len(json.dumps(messages,ensure_ascii=False))<=budget.max_context_chars
            data=json.loads(messages[1]['content']);delta=data['reference_delta']['module.py']
            assert ''.join(difflib.restore(delta,1))==old
            assert ''.join(difflib.restore(delta,2))==new
            return {'text':json.dumps({'activation_files':{},'passports':[]}),'finish_reason':'stop'}
    result=preview.create_review(str(root),str(tmp_path/'generation'),str(tmp_path/'review'),Reviewer())
    assert result['state']=='READY' and result['calls']==1 and len(observed)==1
