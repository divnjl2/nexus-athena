"""Frozen fresh-cohort admission and full-denominator, post-generation accounting."""
from __future__ import annotations
import copy
import itertools
import json
import math
import pathlib
from .adapter import sha
from .intent import digest

STATES = ('PASS', 'FAIL', 'INCOMPLETE')


def validate_design(design):
    evaluation, calibration, excluded = (design[k] for k in ('evaluation_ids','calibration_ids','excluded_prior_ids'))
    for values in (evaluation, calibration, excluded, design['arms']):
        if not isinstance(values,list) or len(values)!=len(set(values)) or any(not isinstance(v,str) or not v for v in values):
            raise ValueError('study identifiers must be unique nonempty strings')
    if not evaluation or not calibration or not design['arms']:
        raise ValueError('study partitions and arms must be nonempty')
    if set(evaluation)&(set(calibration)|set(excluded)) or set(calibration)&set(excluded):
        raise ValueError('fresh study partitions overlap prior or calibration cases')
    if type(design.get('denominator_per_arm')) is not int or len(evaluation)!=design['denominator_per_arm']:
        raise ValueError('the frozen denominator differs from selected cases')
    return design


def freeze_execution(design_file, destination, *, files, runtime_files, evaluator_bindings, model_configuration):
    """Create once before inference. Content hashes are bindings, never signatures."""
    path=pathlib.Path(design_file);design=validate_design(json.loads(path.read_bytes()))
    ids=set(design['evaluation_ids'])|set(design['calibration_ids'])
    if set(runtime_files)!=ids: raise ValueError('every selected case requires a runtime binding')
    if not files or not evaluator_bindings or not model_configuration:
        raise ValueError('source/driver, evaluator and model configuration bindings are required')
    bound={str(path.resolve()):sha(path.read_bytes())}
    for filename in files:
        p=pathlib.Path(filename).resolve();bound[str(p)]=sha(p.read_bytes())
    runtimes={}
    for identity, filename in runtime_files.items():
        p=pathlib.Path(filename).resolve();raw=p.read_bytes();runtime=json.loads(raw)
        if runtime.get('state')=='INCOMPLETE' and runtime.get('instance_id')==identity and runtime.get('reason'):
            bound[str(p)]=sha(raw)
            runtimes[identity]={'path':str(p),'sha256':sha(raw),'state':'UNAVAILABLE','reason':runtime['reason']}
            continue
        if (runtime.get('instance_id')!=identity or not isinstance(runtime.get('image_id'),str)
                or not runtime['image_id'].startswith('sha256:') or not runtime.get('snapshot_sha256')):
            raise ValueError('runtime is not pinned to this case snapshot')
        bound[str(p)]=sha(raw);runtimes[identity]={'path':str(p),'sha256':sha(raw), 'state':'READY',
            'image_id':runtime['image_id'],'snapshot_sha256':runtime['snapshot_sha256']}
    body={'schema':'athena.execution_freeze/1','design_sha256':sha(path.read_bytes()),
        'files':bound,'runtimes':runtimes,'evaluator':copy.deepcopy(evaluator_bindings),
        'model_configuration':copy.deepcopy(model_configuration)}
    frozen={**body,'sha256':digest(body)}
    out=pathlib.Path(destination);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as handle:json.dump(frozen,handle,indent=2)
    return frozen


def verify_execution(frozen):
    body={k:v for k,v in frozen.items() if k!='sha256'}
    if frozen.get('schema')!='athena.execution_freeze/1' or frozen.get('sha256')!=digest(body):
        raise ValueError('execution freeze changed')
    for filename, expected in frozen['files'].items():
        if sha(pathlib.Path(filename).read_bytes())!=expected:
            raise ValueError('frozen execution input changed')
    return frozen


def admit_inference(freeze_file, study_directory, *, instance_id=None):
    """Must be called before each study inference; no inference after grading begins."""
    root=pathlib.Path(study_directory)
    if (root/'generation-ended.json').exists() or (root/'grading-started.json').exists():
        raise ValueError('generation has ended; grader feedback cannot enter another inference')
    frozen=verify_execution(json.loads(pathlib.Path(freeze_file).read_bytes()))
    if instance_id is not None and frozen['runtimes'].get(instance_id,{}).get('state')!='READY':
        raise ValueError('this case has no ready immutable runtime binding')
    return frozen['sha256']


def seal_generation(design_file, freeze_file, study_directory, records):
    """Seal outcomes and all existing artifacts in a dedicated study directory."""
    design=validate_design(json.loads(pathlib.Path(design_file).read_bytes()))
    frozen=verify_execution(json.loads(pathlib.Path(freeze_file).read_bytes()))
    if sha(pathlib.Path(design_file).read_bytes())!=frozen['design_sha256']:
        raise ValueError('study design differs from execution freeze')
    _records(design,records,require_grades=False)
    artifacts={}
    for row in records:
        for candidate in row['candidates']:
            path=pathlib.Path(candidate['prediction_path']).resolve()
            if sha(path.read_bytes())!=candidate['prediction_sha256']:
                raise ValueError('candidate changed before generation seal')
            artifacts[str(path)]=candidate['prediction_sha256']
    for path in pathlib.Path(study_directory).resolve().rglob('*'):
        if path.is_symlink():raise ValueError('study artifacts cannot be symlinks')
        if path.is_file():artifacts[str(path.resolve())]=sha(path.read_bytes())
    body={'schema':'athena.generation_seal/1','design_sha256':frozen['design_sha256'], 'design_canonical_sha256':digest(design),
          'execution_sha256':frozen['sha256'],'records':copy.deepcopy(records),'artifacts':artifacts}
    seal={**body,'sha256':digest(body)}
    with (pathlib.Path(study_directory)/'generation-ended.json').open('x',encoding='utf-8') as handle:
        json.dump(seal,handle,indent=2)
    return seal


def start_grading(study_directory):
    root=pathlib.Path(study_directory);seal=json.loads((root/'generation-ended.json').read_bytes())
    body={k:v for k,v in seal.items() if k!='sha256'}
    if seal.get('sha256')!=digest(body):raise ValueError('generation seal changed')
    for name, expected in seal['artifacts'].items():
        if sha(pathlib.Path(name).read_bytes())!=expected:raise ValueError('frozen candidate changed before grading')
    with (root/'grading-started.json').open('x',encoding='utf-8') as handle:
        json.dump({'generation_sha256':seal['sha256']},handle)
    return seal


def _records(design,records,*,require_grades=True):
    expected=set(itertools.product(design['evaluation_ids'],design['arms']));seen=set()
    for row in records:
        pair=(row['instance_id'],row['arm'])
        if pair not in expected or pair in seen:raise ValueError('missing, duplicate or extra study pair')
        seen.add(pair)
        if row.get('state') not in STATES or type(row.get('released')) is not bool:
            raise ValueError('invalid final workflow state')
        candidates=row.get('candidates')
        if not isinstance(candidates,list):raise ValueError('candidate history is required even if empty')
        identities=set();selected=[]
        for c in candidates:
            identity=c.get('id')
            if not isinstance(identity,str) or not identity or identity in identities:
                raise ValueError('duplicate or missing immutable candidate identity')
            identities.add(identity)
            if c.get('native_state') not in (*STATES,'N/A') or c.get('state') not in STATES:
                raise ValueError('candidate layer states missing')
            if type(c.get('selected')) is not bool:raise ValueError('workflow selection must precede grading')
            if c['selected']:selected.append(c)
            if require_grades and c.get('independent_state') not in STATES:
                raise ValueError('every submitted candidate needs independent outcome, including INCOMPLETE')
            if not require_grades and any(k in c for k in ('independent_state','report','grade')):
                raise ValueError('independent grading cannot precede the generation seal')
        if len(selected)>1 or (row['released'] and (len(selected)!=1 or row['state']!='PASS')):
            raise ValueError('release must select one exact workflow candidate')
        if row['arm']=='direct' and any(c['native_state']!='N/A' for c in candidates):
            raise ValueError('direct candidates have no native trust decision')
    if seen!=expected:raise ValueError('missing study pairs must remain explicit INCOMPLETE rows')


def _interval(successes,total):
    # Per-case primary rates only; never treat repair candidates as independent cases.
    z=1.959963984540054;p=successes/total;den=1+z*z/total
    middle=(p+z*z/(2*total))/den
    radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [max(0,middle-radius),min(1,middle+radius)]


def assess_sealed(design, study_directory, grades):
    """Join grades onto preselected history; grading cannot select a different winner."""
    from .adapter import classify
    root=pathlib.Path(study_directory)
    seal=json.loads((root/'generation-ended.json').read_bytes())
    started=json.loads((root/'grading-started.json').read_bytes())
    body={k:v for k,v in seal.items() if k!='sha256'}
    if seal.get('sha256')!=digest(body) or started.get('generation_sha256')!=seal['sha256']:
        raise ValueError('grading is not bound to the generation seal')
    if digest(design)!=seal.get('design_canonical_sha256'):
        raise ValueError('assessment design differs from generation seal')
    for filename,expected in seal['artifacts'].items():
        if sha(pathlib.Path(filename).read_bytes())!=expected:
            raise ValueError('generation evidence changed after sealing')
    # The original file bytes may use any JSON whitespace; validate the same parsed design.
    records=copy.deepcopy(seal['records']);expected=set();provided={}
    for row in records:
        for c in row['candidates']:expected.add((row['instance_id'],row['arm'],c['id']))
    for grade in grades:
        key=(grade['instance_id'],grade['arm'],grade['candidate_id'])
        if key not in expected or key in provided:raise ValueError('extra or duplicate independent grade')
        provided[key]=grade
    for row in records:
        for c in row['candidates']:
            path=pathlib.Path(c['prediction_path']).resolve()
            if seal['artifacts'].get(str(path))!=c['prediction_sha256'] or sha(path.read_bytes())!=c['prediction_sha256']:
                raise ValueError('candidate changed after generation')
            grade=provided.get((row['instance_id'],row['arm'],c['id']))
            if grade and grade.get('prediction_sha256')!=c['prediction_sha256']:
                raise ValueError('grade belongs to another candidate')
            c['independent_state']=classify(grade.get('report') if grade else None)['state']
    report=summarize(design,records)
    report['generation_sha256']=seal['sha256']
    report['graded_history']=records
    return report


def summarize(design,records):
    validate_design(design);_records(design,records)
    report={'schema':'athena.semantic_assessment/1','denominator_per_arm':design['denominator_per_arm'],
        'arms':{},'limits':['Candidate matrices are descriptive and correlated within case.',
        'Per-case primary intervals do not establish cross-arm superiority.',
        'Independent benchmark correctness covers the benchmark issue, not every possible specification.']}
    for arm in design['arms']:
        rows=[r for r in records if r['arm']==arm];candidates=[c for r in rows for c in r['candidates']]
        native={n:{g:0 for g in STATES} for n in (*STATES,'N/A')}
        combined={n:{g:0 for g in STATES} for n in STATES}
        transitions={a:{b:0 for b in STATES} for a in STATES}
        correct=0;withheld_good=0;released_bad=0;missing_final=0
        for c in candidates:
            native[c['native_state']][c['independent_state']]+=1
            combined[c['state']][c['independent_state']]+=1
        for row in rows:
            final=next((c for c in row['candidates'] if c['selected']),None)
            if final is None:missing_final+=1;continue
            good=final['independent_state']=='PASS'
            correct+=row['released'] and good
            withheld_good+=not row['released'] and good
            released_bad+=row['released'] and final['independent_state']=='FAIL'
            if len(row['candidates'])>1:
                transitions[row['candidates'][0]['independent_state']][final['independent_state']]+=1
        decidable=sum(c['independent_state']!='INCOMPLETE' for c in candidates)
        adequate=bool(candidates) and decidable/len(candidates)>=.8
        report['arms'][arm]={'cases':len(rows),'submitted_candidates':len(candidates),
            'cases_with_submission':sum(bool(r['candidates']) for r in rows),
            'decidable_candidates':decidable,'assessment_state':'DECIDABLE_COVERAGE' if adequate else 'INCOMPLETE',
            'released_and_correct':correct,'primary_rate':correct/len(rows),'primary_wilson95':_interval(correct,len(rows)),
            'released_bad':released_bad,'withheld_good_final':withheld_good,'no_selected_final':missing_final,
            'native_vs_independent':native,'combined_vs_independent':combined,
            'native_decisions':{'accepted_good':native['PASS']['PASS'],'accepted_bad':native['PASS']['FAIL'],
                'rejected_good':native['FAIL']['PASS'],'rejected_bad':native['FAIL']['FAIL'],
                'incomplete_good':native['INCOMPLETE']['PASS'],'incomplete_bad':native['INCOMPLETE']['FAIL'],
                'independent_unknown':sum(v['INCOMPLETE'] for v in native.values())},
            'first_to_selected_independent':transitions,'resources_by_case':[
                {'instance_id':r['instance_id'],'resources':copy.deepcopy(r.get('resources'))} for r in rows],
            'workflow_counts':{s:sum(r['state']==s for r in rows) for s in STATES}}
    return report
