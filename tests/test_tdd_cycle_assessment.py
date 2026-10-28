import copy
import json
import pytest
from evals.tddbench.assessment import (validate_design,freeze_execution,admit_inference,seal_generation,
    start_grading,assess_sealed,summarize)
from evals.tddbench.adapter import sha


def design():
    return {'evaluation_ids':['case-1','case-2'],'calibration_ids':['cal-1'],'excluded_prior_ids':['old-1'],
            'arms':['direct','semantic-cycle'],'denominator_per_arm':2}


def frozen(tmp_path):
    d=design();path=tmp_path/'design.json';path.write_text(json.dumps(d))
    source=tmp_path/'source.py';source.write_text('SOURCE')
    runtimes={}
    for identity in d['evaluation_ids']+d['calibration_ids']:
        p=tmp_path/(identity+'.json');p.write_text(json.dumps({'instance_id':identity,'image_id':'sha256:'+'b'*64,
            'snapshot_sha256':'c'*64}));runtimes[identity]=str(p)
    freeze=tmp_path/'execution.json'
    freeze_execution(path,freeze,files=[source],runtime_files=runtimes,
                     evaluator_bindings={'harness_image':'sha256:'+'d'*64},model_configuration={'model':'frozen-model'})
    return d,path,freeze,source


def records(tmp_path):
    rows=[]
    for identity in design()['evaluation_ids']:
        for arm in design()['arms']:
            candidates=[]
            if identity=='case-1':
                for i in range(2):
                    p=tmp_path/(identity+arm+str(i)+'.prediction.json');p.write_text(json.dumps([{'model_patch':str(i)}]))
                    candidates.append({'id':str(i),'native_state':'N/A' if arm=='direct' else ('FAIL' if i==0 else 'INCOMPLETE'),
                        'state':'PASS' if arm=='direct' else ('FAIL' if i==0 else 'INCOMPLETE'),
                        'selected':i==1,'prediction_path':str(p),'prediction_sha256':sha(p.read_bytes())})
            rows.append({'instance_id':identity,'arm':arm,'state':'PASS' if candidates and arm=='direct' else 'INCOMPLETE',
                'released':bool(candidates) and arm=='direct','candidates':candidates,
                'resources':{'spent':{'model_calls':5},'observed_usage':None,'missing_usage_fields':5}})
    return rows


def test_fresh_partitions_and_immutable_execution_are_required_before_inference(tmp_path):
    """C-5.1 - Disjoint partitions and immutable executable bindings precede inference."""
    for key,value in [('calibration_ids',['case-1']),('excluded_prior_ids',['case-2']),('evaluation_ids',['case-1','case-1']),
                      ('denominator_per_arm',1)]:
        d=design();d[key]=value
        with pytest.raises(ValueError):validate_design(d)
    with pytest.raises(FileNotFoundError):admit_inference(tmp_path/'missing.json',tmp_path)
    d,path,freeze,source=frozen(tmp_path)
    assert admit_inference(freeze,tmp_path)
    source.write_text('CHANGED')
    with pytest.raises(ValueError,match='changed'):admit_inference(freeze,tmp_path)


def test_every_missing_pair_and_full_candidate_history_precedes_grading(tmp_path):
    d,path,freeze,_=frozen(tmp_path);rows=records(tmp_path)
    with pytest.raises(FileNotFoundError):start_grading(tmp_path)
    with pytest.raises(ValueError,match='missing study'):seal_generation(path,freeze,tmp_path,rows[:-1])
    seal_generation(path,freeze,tmp_path,rows)
    with pytest.raises(ValueError,match='ended'):admit_inference(freeze,tmp_path)
    start_grading(tmp_path)
    with pytest.raises(FileExistsError):start_grading(tmp_path)
    with pytest.raises(ValueError,match='ended'):admit_inference(freeze,tmp_path)


def test_sealed_selection_and_missing_grades_never_become_best_of_n_or_success(tmp_path):
    """C-5.2 - Sealed selection and missing grades cannot become best-of-n or false success."""
    d,path,freeze,_=frozen(tmp_path);rows=records(tmp_path)
    seal_generation(path,freeze,tmp_path,rows);start_grading(tmp_path)
    grades=[]
    for row in rows:
        for c in row['candidates']:
            # First is correct, selected final is wrong. Reporting cannot choose the first.
            before={'test_x':'FAILED' if c['id']=='0' else 'PASSED'}
            grades.append({'instance_id':row['instance_id'],'arm':row['arm'],'candidate_id':c['id'],
                'prediction_sha256':c['prediction_sha256'],
                'report':{'test_before_patch':before,'test_after_patch':{'test_x':'PASSED'},'resolved':True}})
    report=assess_sealed(d,tmp_path,grades)
    a=report['arms']['semantic-cycle'];direct=report['arms']['direct']
    assert a['cases']==2 and a['submitted_candidates']==2 and a['no_selected_final']==1
    assert a['released_and_correct']==0 and a['primary_rate']==0
    assert a['native_vs_independent']['FAIL']['PASS']==1
    assert a['native_decisions']['rejected_good']==1 and a['native_decisions']['accepted_good']==0
    assert a['first_to_selected_independent']['PASS']['FAIL']==1
    assert direct['released_bad']==1 and direct['native_vs_independent']['N/A']['PASS']==1
    missing=assess_sealed(d,tmp_path,[])['arms']['semantic-cycle']
    assert missing['assessment_state']=='INCOMPLETE' and missing['decidable_candidates']==0
    assert missing['combined_vs_independent']['FAIL']['INCOMPLETE']==1
    with pytest.raises(ValueError,match='duplicate'):assess_sealed(d,tmp_path,grades+[grades[0]])
    grades[0]['prediction_sha256']='wrong'
    with pytest.raises(ValueError,match='another candidate'):assess_sealed(d,tmp_path,grades)


def test_correct_withheld_final_is_reported_separately_from_false_rejection(tmp_path):
    rows=records(tmp_path)
    for row in rows:
        for c in row['candidates']:c['independent_state']='PASS'
    a=summarize(design(),rows)['arms']['semantic-cycle']
    assert a['withheld_good_final']==1 and a['native_vs_independent']['FAIL']['PASS']==1
    assert a['native_vs_independent']['INCOMPLETE']['PASS']==1
    assert a['resources_by_case'][0]['resources']['observed_usage'] is None


def test_changed_candidate_blocks_grading_and_cannot_be_hidden(tmp_path):
    d,path,freeze,_=frozen(tmp_path);rows=records(tmp_path)
    seal_generation(path,freeze,tmp_path,rows)
    from pathlib import Path
    Path(rows[0]['candidates'][0]['prediction_path']).write_text('changed')
    with pytest.raises(ValueError,match='changed'):start_grading(tmp_path)


def test_explicit_infrastructure_failures_stay_selected_but_cannot_receive_inference(tmp_path):
    d,path,freeze,source=frozen(tmp_path)
    runtimes={identity:tmp_path/(identity+'.json') for identity in d['evaluation_ids']+d['calibration_ids']}
    runtimes['case-2'].write_text(json.dumps({'instance_id':'case-2','state':'INCOMPLETE','reason':'public runtime unavailable'}))
    second=tmp_path/'execution-unavailable.json'
    freeze_execution(path,second,files=[source],runtime_files=runtimes,
        evaluator_bindings={'image':'sha256:'+'e'*64},model_configuration={'model':'frozen-model'})
    assert admit_inference(second,tmp_path,instance_id='case-1')
    with pytest.raises(ValueError,match='ready'):admit_inference(second,tmp_path,instance_id='case-2')
    assert 'case-2' in json.loads(second.read_bytes())['runtimes']


def test_review_and_resource_evidence_are_sealed_as_well_as_prediction_patches(tmp_path):
    d,path,freeze,_=frozen(tmp_path);rows=records(tmp_path)
    review=tmp_path/'review.json';review.write_text('{"state":"INCOMPLETE"}')
    resources=tmp_path/'resources.json';resources.write_text('{"model_calls":7}')
    seal_generation(path,freeze,tmp_path,rows)
    resources.write_text('{"model_calls":0}')
    with pytest.raises(ValueError,match='changed'):start_grading(tmp_path)
    resources.write_text('{"model_calls":7}');start_grading(tmp_path)
    review.write_text('{"state":"PASS"}')
    with pytest.raises(ValueError,match='evidence changed'):assess_sealed(d,tmp_path,[])
