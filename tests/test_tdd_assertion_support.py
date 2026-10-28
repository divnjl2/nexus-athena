"""Syntactic source coverage cannot silently turn a review declaration into truth."""
import copy
import pytest
from evals.tddbench.intent import check_support,digest,new_assertions,prepare_intent
from evals.tddbench.trust import candidate_digest
from test_tdd_intent import make_issue,make_declaration


def candidate(text='def test_value():\n    assert value() == 3000000\n'):
    return {'contract':'- **C-1.1** — WHEN a numeric value is displayed THE SYSTEM SHALL preserve its magnitude.',
            'scenarios':'public scenarios','files':{'tests/test_value.py':text},
            'reference':{'module.py':'public hypothesis'},'intent_bindings':{'C-1.1':['I1']}}


def supported(issue,profile,proposal):
    sites=new_assertions(proposal['files'],{})
    return {'issue_sha256':digest(issue),'intent_sha256':profile['sha256'],
        'candidate_sha256':candidate_digest(proposal),
        'intent_reviews':[{'intent':r['id'],'status':'SUPPORTED','reason':'Explicit issue meaning.'}
                           for r in profile['requirements'] if r['is_live']],
        'assertion_reviews':[{'assertion':s['id'],'intents':['I1'],'status':'SUPPORTED',
           'quotes':['Show complete numeric values'],'reason':'Checks the observable magnitude.'} for s in sites]}


def test_complete_declared_support_is_labelled_without_semantic_attestation():
    issue=make_issue();profile=prepare_intent(issue,make_declaration());proposal=candidate()
    result=check_support(issue,profile,proposal,{},supported(issue,profile,proposal))
    assert result['state']=='PASS' and result['passed']
    assert result['validity']=='MODEL_DECLARED_NOT_ATTESTED'
    assert 'not proven' in result['scope']


def test_unsupported_literal_is_rejected_and_unknown_support_is_incomplete():
    """C-1.2 - Unjustified representation constraints fail and unresolved assertion support stays incomplete."""
    issue=make_issue();profile=prepare_intent(issue,make_declaration())
    proposal=candidate('def test_value():\n    assert "1e6" in label()\n')
    review=supported(issue,profile,proposal)
    row=review['assertion_reviews'][0]
    row.update(status='UNJUSTIFIED',quotes=[],reason='The issue allows equivalent numeric representations.')
    rejected=check_support(issue,profile,proposal,{},review)
    assert rejected['state']=='FAIL' and rejected['unjustified']==[row['assertion']]
    row.update(status='UNRESOLVED',reason='The issue does not settle this representation.')
    assert check_support(issue,profile,proposal,{},review)['state']=='INCOMPLETE'


@pytest.mark.parametrize('problem',['missing','duplicate','made-up-quote','changed-reference','changed-test'])
def test_missing_stale_or_invalid_evidence_never_releases(problem):
    issue=make_issue();profile=prepare_intent(issue,make_declaration());proposal=candidate()
    review=supported(issue,profile,proposal)
    if problem=='missing':review['assertion_reviews']=[]
    elif problem=='duplicate':review['assertion_reviews']*=2
    elif problem=='made-up-quote':review['assertion_reviews'][0]['quotes']=['The issue says 1e6 is mandatory']
    elif problem=='changed-reference':proposal['reference']['module.py']='different public hypothesis'
    else:proposal['files']['tests/test_value.py']='def test_value():\n    assert True\n'
    result=check_support(issue,profile,proposal,{},review)
    assert result['state']=='INCOMPLETE' and not result['passed']


def test_unchanged_old_assertions_are_excluded_but_aliases_raises_and_new_methods_are_recorded():
    old='def test_old():\n    assert old_value()\n'
    new=old+'\nfrom numpy.testing import assert_equal as check\nimport pytest\nclass TestNew:\n    def test_new(self):\n        check(actual(), 3)\n        with pytest.raises(ValueError):\n            error()\n        self.assertEqual(actual(), 3)\n'
    sites=new_assertions({'tests/test_values.py':new},{'tests/test_values.py':old})
    assert len(sites)==3 and {s['kind'] for s in sites}=={'call:assert_equal','call:raises','call:assertEqual'}
    assert all(s['scope']==['TestNew','test_new'] for s in sites)
    assert len({s['id'] for s in sites})==3


def test_vacuous_or_unmapped_intent_stays_incomplete():
    issue=make_issue();raw=make_declaration()
    raw['requirements'].append({'id':'I2','obligation':'Accept equivalent representations',
        'quotes':['equivalent numeric representations are allowed.'],'representation':'open'})
    profile=prepare_intent(issue,raw);proposal=candidate()
    result=check_support(issue,profile,proposal,{},supported(issue,profile,proposal))
    assert result['state']=='INCOMPLETE' and any('no clause binding' in p for p in result['problems'])
    profile=prepare_intent(issue,make_declaration());proposal=candidate('def test_value():\n    value()\n')
    assert check_support(issue,profile,proposal,{},supported(issue,profile,proposal))['state']=='INCOMPLETE'
