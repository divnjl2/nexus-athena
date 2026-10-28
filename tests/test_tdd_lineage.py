"""Whole-lineage budget invariants, including an actual abrupt process exit."""
import json
import pathlib
import subprocess
import sys
import pytest
from evals.tddbench.lineage import (BudgetExhausted, Journal, JournalBusy, JournalCorrupt,
                                   Limits, audit_cost, plan_remaining)

BINDING = 'a' * 64
REFERENCE = 'b' * 64


def test_reservations_block_generation_before_it_spends_review_or_repair(tmp_path):
    """C-4.1 - One journal protects admitted review and repair reservations from generation spending."""
    journal = Journal.create(tmp_path/'journal', Limits(3, 6), BINDING)
    journal.reserve('review:1', model_calls=1, test_runs=2)
    journal.reserve('repair', model_calls=1, test_runs=2)
    calls = []
    def model():
        calls.append(1)
        return {'usage': {'input_tokens': 4, 'output_tokens': 1}}
    journal.invoke('model_calls', 'generation:1', reference=REFERENCE, operation=model)
    with pytest.raises(BudgetExhausted):
        journal.invoke('model_calls', 'generation:1', reference=REFERENCE, operation=model)
    assert calls == [1]
    assert journal.snapshot()['spent']['model_calls'] == 1
    assert journal.snapshot()['denied'] == 1
    journal.invoke('model_calls', 'review:1', reference=REFERENCE, operation=model)
    journal.transfer('repair', 'generation:2', model_calls=1)
    journal.invoke('model_calls', 'generation:2', reference=REFERENCE, operation=model)
    assert len(calls) == 3 and journal.snapshot()['remaining']['model_calls'] == 0


@pytest.mark.parametrize('error', [TimeoutError('secret-provider-token'), RuntimeError('secret-provider-token')])
def test_failures_survive_reopen_and_never_refund_or_leak_messages(tmp_path,error):
    root=tmp_path/'journal';journal=Journal.create(root,Limits(1,1),BINDING)
    def fail():raise error
    with pytest.raises(type(error)):
        journal.invoke('model_calls','generation:1',reference=REFERENCE,operation=fail)
    reopened=Journal.open(root,Limits(1,1),BINDING,expected_head=journal.head)
    with pytest.raises(BudgetExhausted):
        reopened.charge('model_calls','generation:2',reference=REFERENCE)
    snapshot=reopened.snapshot()
    assert snapshot['spent']['model_calls']==1 and snapshot['pending']==[]
    assert snapshot['observed_usage']['output_tokens'] is None
    assert snapshot['missing_usage_fields']['output_tokens']==1
    assert all('secret-provider-token' not in p.read_text() for p in root.glob('*.json'))


def test_charge_is_durable_before_a_process_crashes(tmp_path):
    root=tmp_path/'journal';Journal.create(root,Limits(1,1),BINDING)
    code=('import os,sys; from evals.tddbench.lineage import Journal,Limits; '
          'j=Journal.open(sys.argv[1],Limits(1,1),sys.argv[2]); '
          'j.invoke("model_calls","generation:1",reference="b"*64,operation=lambda:os._exit(7))')
    child=subprocess.run([sys.executable,'-c',code,str(root),BINDING],
                         cwd=pathlib.Path(__file__).resolve().parents[1],capture_output=True,timeout=20)
    assert child.returncode==7,child.stderr.decode(errors='replace')
    journal=Journal.open(root,Limits(1,1),BINDING)
    assert journal.snapshot()['spent']['model_calls']==1 and len(journal.snapshot()['pending'])==1
    with pytest.raises(BudgetExhausted):
        journal.charge('model_calls','repair',reference=REFERENCE)
    with pytest.raises(FileExistsError):
        Journal.create(root,Limits(1,1),BINDING)


def test_pending_work_prevents_releasing_its_phase_and_duplicate_settlement(tmp_path):
    journal=Journal.create(tmp_path/'journal',Limits(2,3),BINDING)
    journal.reserve('review',model_calls=2,test_runs=1)
    ticket=journal.charge('model_calls','review',reference=REFERENCE)
    with pytest.raises(ValueError,match='pending'):
        journal.release('review',evidence=REFERENCE)
    with pytest.raises(ValueError,match='pending'):
        journal.transfer('review','repair',model_calls=1)
    journal.finish(ticket,'COMPLETED')
    with pytest.raises(ValueError,match='already settled'):
        journal.finish(ticket,'COMPLETED')
    journal.release('review',evidence=REFERENCE)
    assert journal.snapshot()['spent']['model_calls']==1


def test_stale_writer_cannot_admit_work_after_another_writer_advances(tmp_path):
    root=tmp_path/'journal';first=Journal.create(root,Limits(2,2),BINDING)
    second=Journal.open(root,Limits(2,2),BINDING)
    first.invoke('test_runs','native:1',reference=REFERENCE,operation=lambda:{'status':'ASSERTION_FAIL'})
    with pytest.raises(JournalBusy):
        second.charge('test_runs','native:2',reference=REFERENCE)
    reopened=Journal.open(root,Limits(2,2),BINDING,expected_head=first.head)
    assert reopened.snapshot()['spent']['test_runs']==1


def test_changed_limits_binding_corruption_and_truncated_trusted_head_are_rejected(tmp_path):
    root=tmp_path/'journal';journal=Journal.create(root,Limits(2,2),BINDING)
    with pytest.raises(JournalCorrupt):Journal.open(root,Limits(99,99),BINDING)
    with pytest.raises(JournalCorrupt):Journal.open(root,Limits(2,2),'c'*64)
    journal.reserve('review',model_calls=1)
    trusted=journal.head
    last=sorted(root.glob('*.json'))[-1]
    original=last.read_bytes();last.write_bytes(b'{')
    with pytest.raises(JournalCorrupt):Journal.open(root,Limits(2,2),BINDING)
    last.write_bytes(original);last.unlink()
    with pytest.raises(JournalCorrupt):Journal.open(root,Limits(2,2),BINDING,expected_head=trusted)


def test_missing_usage_is_not_zero_and_observed_zero_stays_zero(tmp_path):
    """C-4.3 - Unknown usage remains distinct from measured zero."""
    journal=Journal.create(tmp_path/'journal',Limits(2,1),BINDING)
    journal.invoke('model_calls','generation',reference=REFERENCE,
                   operation=lambda:{'usage':{'input_tokens':10,'output_tokens':0}})
    journal.invoke('model_calls','review',reference=REFERENCE,operation=lambda:{'usage':None})
    observed=journal.snapshot()
    assert observed['observed_usage']['input_tokens']==10
    assert observed['observed_usage']['output_tokens']==0
    assert observed['missing_usage_fields']['output_tokens']==1
    assert observed['observed_usage']['cached_input_tokens'] is None
    assert observed['missing_usage_fields']['cached_input_tokens']==2


def test_audit_forecast_reserves_full_bindings_and_repair_instead_of_narrowing():
    """C-4.2 - Forecast includes every binding and repair without reducing required scope."""
    bindings={'C-1.1':1,'C-1.2':1}
    assert audit_cost(bindings,valid=1)==10 and audit_cost(bindings)==12
    infeasible=plan_remaining(bindings,calls=10,tests=9,attempts=1)
    assert not infeasible['feasible'] and infeasible['shortfall']['test_runs']==3
    reserved=plan_remaining(bindings,calls=14,tests=33,attempts=2)
    assert reserved['feasible'] and reserved['required']=={'model_calls':6,'test_runs':26}
    assert audit_cost({'C-1.1':2})==10


@pytest.mark.parametrize('bindings',[{}, {'C-1.1':0}, {'C-1.1':True}])
def test_planner_refuses_missing_or_invalid_scope(bindings):
    with pytest.raises(ValueError):audit_cost(bindings)
