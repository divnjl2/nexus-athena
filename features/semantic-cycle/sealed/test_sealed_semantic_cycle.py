"""Acceptance fixtures authored separately from the open tests.

These are known regression cases, not a fresh independent quality evaluation.
Real subprocess pytest outcomes challenge the numeric oracle in both directions.
"""
import json
from pathlib import Path

import pytest

from lib.contract import parse, pin_scenarios
from lib.spec_trust import SCHEMA, audit
from evals.tddbench.lineage import BudgetExhausted, Journal, Limits, plan_remaining


def _numeric_project(root, oracle):
    root.mkdir()
    contract = ('# Contract\n- **C-1.1** — WHEN a magnitude is rendered THE SYSTEM SHALL '
                'preserve its numeric value; decimal and exponent spellings are allowed.\n')
    parsed = parse(contract)
    (root/'contract.md').write_text(contract, encoding='utf-8')
    scenarios = ('### S1.1 — preserve magnitude\n- **verifies:** C-1.1\n'
                 '- **run_cmd:** `python -m pytest test_magnitude.py -q`\n')
    (root/'scenarios.md').write_text(pin_scenarios(scenarios, parsed)[0], encoding='utf-8')
    (root/'render.py').write_text('def render():\n    return "2500000"\n', encoding='utf-8')
    (root/'test_magnitude.py').write_text(oracle, encoding='utf-8')
    (root/'probe.py').write_text(
        'from decimal import Decimal\nfrom render import render\n'
        'def test_changed_magnitude():\n    assert Decimal(render()) != Decimal("2500000")\n',
        encoding='utf-8')
    variants = [
        {'id': 'exponent', 'kind': 'valid', 'reason': 'The stated domain permits exponent spelling.',
         'files': {'render.py': 'def render():\n    return "2.5e6"\n'}},
        {'id': 'trailing_fraction', 'kind': 'valid', 'reason': 'Trailing fractional zeros preserve the exact value.',
         'files': {'render.py': 'def render():\n    return "2500000.000"\n'}},
        {'id': 'wrong_scale', 'kind': 'violation', 'reason': 'The output loses one order of magnitude.',
         'activation': 'python -m pytest probe.py -q',
         'files': {'render.py': 'def render():\n    return "250000"\n'}},
    ]
    passport = {'clause': 'C-1.1', 'pin': parsed.by_id('C-1.1').version,
                 'intent_source': 'The public numeric contract in this fixture.',
                 'owner_decision': 'Spelling is free; exact magnitude is mandatory.',
                 'input_domain': 'The finite positive magnitude 2500000.',
                 'observable_outcome': 'The numeric value of the rendered string.',
                 'oracle_source': 'Decimal equality, without binary floating-point tolerance.',
                 'assumptions': [], 'undefined_behavior': [], 'known_gaps': [],
                 'specs': ['S1.1'], 'variants': variants}
    manifest = {'schema': SCHEMA, 'contract': 'contract.md', 'scenarios': 'scenarios.md',
                'inputs': ['render.py', 'test_magnitude.py', 'probe.py'],
                'implementation': ['render.py'], 'passports': [passport]}
    (root/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return root


def test_sealed_representation_freedom_and_value_violation_are_both_executed(tmp_path):
    """C-3.1 (sealed) — an oracle admits two equivalent spellings and rejects changed magnitude."""
    root = _numeric_project(tmp_path/'sound',
        'from decimal import Decimal\nfrom render import render\n'
        'def test_magnitude():\n    assert Decimal(render()) == Decimal("2500000")\n')
    report = audit(str(root), 'manifest.json')
    assert report['state'] == 'PASS', report
    row = report['clauses'][0]
    assert row['controls'] == {'valid': 2, 'violation': 1}
    assert [v['state'] for v in row['challenges']] == ['PASS', 'PASS', 'PASS']
    negative = row['challenges'][-1]
    assert negative['activation_baseline']['status'] == 'ASSERTION_FAIL'
    assert negative['activation']['status'] == 'PASS'
    assert negative['checks'][0]['status'] == 'ASSERTION_FAIL'
    assert (root/'render.py').read_text(encoding='utf-8').endswith('return "2500000"\n')


@pytest.mark.parametrize('oracle,problem', [
    ('from render import render\ndef test_magnitude():\n    assert render() == "2500000"\n', 'overspecific'),
    ('from render import render\ndef test_magnitude():\n    assert render()\n', 'vacuous'),
])
def test_sealed_defective_oracles_are_rejected_by_observable_controls(tmp_path, oracle, problem):
    """C-3.1 (sealed) — literal-only and truthiness oracles fail opposite sides of the same contract."""
    root = _numeric_project(tmp_path/problem, oracle)
    report = audit(str(root), 'manifest.json')
    assert report['state'] == 'FAIL', report
    controls = report['clauses'][0]['challenges']
    if problem == 'overspecific':
        assert controls[0]['state'] == 'FAIL' and controls[1]['state'] == 'FAIL'
    else:
        assert controls[-1]['state'] == 'FAIL'
        assert controls[-1]['activation']['status'] == 'PASS'
        assert controls[-1]['checks'][0]['status'] == 'PASS'


def test_sealed_full_scope_reserve_prevents_spending_a_short_audit_budget(tmp_path):
    """C-4.1, C-4.2 (sealed) — a one-run shortfall cannot be erased by spending or narrowing scope."""
    scope = {'python -m pytest tests/test_a.py -q': 2,
             'python -m pytest tests/test_b.py -q': 3}
    plan = plan_remaining(scope, calls=6, tests=64)
    assert plan['required'] == {'model_calls': 6, 'test_runs': 53}
    short = plan_remaining(scope, calls=6, tests=52)
    assert not short['feasible'] and short['shortfall']['test_runs'] == 1
    journal = Journal.create(tmp_path/'journal', Limits(6, 53), 'a'*64)
    journal.reserve('complete-cycle', model_calls=6, test_runs=53)
    ran = []
    with pytest.raises(BudgetExhausted):
        journal.invoke('test_runs', 'unreserved-exploration', reference='b'*64,
                       operation=lambda: ran.append(True))
    assert ran == [] and journal.snapshot()['spent']['test_runs'] == 0
