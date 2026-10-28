import json
from test_tdd_cycle import CycleModel
from test_tdd_execution import public_runtime
from test_tdd_trust import execution
from evals.tddbench.cycle import public_feedback,run_cycle
from evals.tddbench.generator import Budget


def test_repair_feedback_excludes_nonpublic_top_level_fields():
    """C-2.2 - Repair feedback excludes evaluator and nonpublic fields."""
    secret='SEALED_GOLD_MUST_NOT_REACH_REPAIR'
    review={'state':'READY','reason':'public','independent_evaluation':secret,'support':{'state':'FAIL','gold':secret},
        'assertion_reviews':[{'assertion':'A1','reason':'public','intents':['I1'],'status':'UNJUSTIFIED','gold':secret}]}
    audit={'state':'PASS','reason':'public','gold_patch':secret,'evidence':{'context':secret,
        'metrics':{'evaluated':2,'gold':secret},'clauses':[{'clause':'C-1.1','state':'PASS','private':secret}]}}
    feedback=public_feedback({'files':{'tests/test_public.py':'assert True\n'}},review,audit)
    assert secret not in json.dumps(feedback)
    assert feedback['review']['assertion_reviews'][0]['reason']=='public'


def test_intent_reviewer_and_generator_have_separate_public_contexts(public_runtime,tmp_path):
    root,runtime=public_runtime;issue=json.loads((root/'issue.json').read_bytes());model=CycleModel(issue)
    (tmp_path/'sealed.json').write_text('GOLD_SECRET_SENTINEL')
    r=run_cycle(str(root),str(runtime),str(tmp_path/'cycle'),model,budget=Budget(max_calls=12,max_test_runs=24),execute=execution)
    assert r['released'] and 'GOLD_SECRET_SENTINEL' not in json.dumps(model.inputs)
    intent_context=json.loads(model.inputs[0][1]['content'])
    assert set(intent_context)=={'issue','execution_budget'}
    for messages in model.inputs:
        if 'Review a frozen' in messages[0]['content']:
            context=json.loads(messages[1]['content'])
            assert 'semantic_cycle' not in context and 'previous_public_feedback' not in context
