"""The model sees shared execution limits; reviewer reservation cannot be spent."""
import json
from test_tdd_execution import public_runtime
from evals.tddbench.generator import Budget, generate_direct


def test_review_reservation_and_used_test_runs_are_visible(public_runtime, tmp_path, monkeypatch):
    import evals.tddbench.execution as execution
    monkeypatch.setattr(execution, 'run_tests', lambda *a, **k: {'status': 'PASS'})
    root, runtime = public_runtime
    observed = []
    def model(messages, budget):
        observed.append(json.loads(messages[-1]['content'])['execution_budget'])
        action = ({'action': 'run', 'files': {'tests/test_new.py': 'assert True\n'},
                   'tests': ['tests/test_new.py']} if len(observed) == 1 else
                  {'action': 'read', 'path': 'api.py'})
        return {'text': json.dumps(action), 'finish_reason': 'stop'}
    out = tmp_path / 'reserved-budget'
    receipt = generate_direct(str(root), str(out), model, mode='athena-trust', runtime_receipt=str(runtime),
                              budget=Budget(max_calls=3, max_test_runs=2))
    assert [b['generation_calls_available_including_current'] for b in observed] == [2, 1]
    assert [b['test_runs_available'] for b in observed] == [2, 1]
    assert all(b['reserved_review_calls'] == 1 for b in observed)
    assert receipt['calls'] == 2 and receipt['test_runs'] == 1
    assert receipt['status'] == 'INCOMPLETE' and not (out / 'prediction.json').exists()
