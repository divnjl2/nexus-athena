"""Opt-in public-only repair lineage; shared admission precedes every external action."""
from __future__ import annotations
from dataclasses import asdict
import copy
import json
import pathlib

from lib.contract import parse, lint
from lib.scenario_parser import parse as scenarios
from .adapter import sha
from .generator import Budget, generate_direct
from .intent import derive_intent, digest, public_issue, verify_intent
from .lineage import Journal, Limits, BudgetExhausted, audit_cost, plan_remaining
from .native import framework_context, pytest_nodes, test_patch
from .semantic import create_semantic_review
from .trust import audit_candidate, load_candidate, candidate_digest
from .workspace import verify_workspace


def public_feedback(proposal, review, audit):
    """Allowlisted public/native feedback. There is deliberately no evaluator argument."""
    def rows(values, keys):
        return [{k: copy.deepcopy(v[k]) for k in keys if k in v}
                for v in values if isinstance(v, dict)] if isinstance(values, list) else []
    feedback = {'proposal': copy.deepcopy(proposal),
        'review': {'state': review.get('state'), 'reason': review.get('reason'),
            'intent_reviews': rows(review.get('intent_reviews'), ('intent', 'status', 'reason')),
            'assertion_reviews': rows(review.get('assertion_reviews'), ('assertion', 'status', 'reason', 'intents', 'quotes'))},
        'native': {'state': audit.get('state', 'INCOMPLETE'), 'reason': audit.get('reason')}}
    for name in ('support', 'diversity', 'protocol'):
        layer = review.get(name, {})
        feedback['review'][name] = {k: copy.deepcopy(layer[k]) for k in ('state', 'problems', 'unjustified') if k in layer}
    evidence = audit.get('evidence', {})
    feedback['native']['metrics'] = {k: v for k, v in evidence.get('metrics', {}).items() if type(v) is int}
    feedback['native']['clauses'] = rows(evidence.get('clauses'), ('clause', 'state', 'baseline', 'challenges'))
    feedback['review']['activation_files'] = copy.deepcopy(review.get('activation_files', {}))
    feedback['review']['passports'] = rows(review.get('passports'), ('clause', 'known_gaps', 'variants'))
    feedback['review']['uncertainty_reviews'] = rows(review.get('uncertainty_reviews'),
        ('question', 'status', 'reason', 'quotes', 'source_quotes'))
    return feedback


def preserve_requirements(previous, proposal):
    """No erased or rewritten identities; an old live clause can only be superseded."""
    before, after = parse(previous['contract']), parse(proposal['contract'])
    if lint(after): raise ValueError('repair contract is inconsistent')
    for old in before.clauses:
        new = after.by_id(old.id)
        if new is None or new.text != old.text:
            raise ValueError('repair erased or rewrote a previous requirement identity')
        if not set(old.superseded_by) <= set(new.superseded_by):
            raise ValueError('repair erased supersession history')
        if old.is_live and not new.is_live and not new.superseded_by:
            raise ValueError('repair silently dropped an obligation')
        if old.status in ('withdrawn', 'superseded') and old.status != new.status:
            raise ValueError('repair revived a retired requirement identity')


def _tree(root):
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}


class _ChargedModel:
    def __init__(self, model, journal, phase):
        self.wrapped, self.journal, self.phase = model, journal, phase
        for attr in ('model', 'source_kind', 'endpoint'):
            if hasattr(model, attr): setattr(self, attr, getattr(model, attr))

    def __call__(self, messages, budget):
        return self.journal.invoke('model_calls', self.phase, reference=digest(messages),
                                  operation=lambda: self.wrapped(messages, budget))


def run_cycle(directory, runtime_receipt, destination, model, *, budget=Budget(max_calls=24, max_test_runs=36),
              max_attempts=2, repair_calls=4, execute=None):
    """Run real generation, fresh review and native audit. Injection replaces only Docker.

    No evaluator access, new limits or prefix reuse is allowed here. A crash leaves the
    journal charged and the lineage INCOMPLETE; automatic replay/resume is not promised.
    """
    budget.validate()
    if type(max_attempts) is not int or not 1 <= max_attempts <= 2:
        raise ValueError('one or two immutable attempts are supported')
    if type(repair_calls) is not int or repair_calls <= 0: raise ValueError('invalid repair reserve')
    root, out = pathlib.Path(directory).resolve(), pathlib.Path(destination).resolve()
    if out.is_relative_to(root) or root.is_relative_to(out): raise ValueError('cycle must be separate from public source')
    snapshot = verify_workspace(directory)
    issue = public_issue(json.loads((root / 'issue.json').read_bytes()))
    source = framework_context()
    binding = {'schema': 'athena.semantic_cycle/1', 'issue_sha256': digest(issue),
        'snapshot_sha256': sha((root / 'snapshot.json').read_bytes()),
        'runtime_sha256': sha(pathlib.Path(runtime_receipt).read_bytes()), 'framework_files': source,
        'budget': asdict(budget), 'max_attempts': max_attempts, 'repair_calls': repair_calls,
        'model': getattr(model, 'model', None), 'instance_id': snapshot['instance_id']}
    out.mkdir(parents=True, exist_ok=False)
    (out / 'binding.json').write_text(json.dumps(binding, indent=2), encoding='utf-8')
    journal = Journal.create(out / 'journal', Limits(budget.max_calls, budget.max_test_runs), digest(binding))
    result = {**binding, 'state': 'INCOMPLETE', 'released': False, 'attempts': [],
              'reason': 'cycle not completed', 'gold_used': False,
              'limits': ['Semantic judgments and valid-control meaning remain declarations.',
                         'PASS means scoped curated challenges passed, not specification truth.',
                         'Charged outer requests are not a provider spending cap.']}

    def save():
        result['resources'] = journal.snapshot()
        (out / 'cycle.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    def available(phase, resource):
        view = journal.snapshot()
        return view['remaining'][resource] - sum(v[resource] for p, v in view['reservations'].items() if p != phase)

    def ensure(phase, *, calls=0, tests=0):
        held = journal.snapshot()['reservations'].get(phase, {'model_calls': 0, 'test_runs': 0})
        journal.reserve(phase, model_calls=max(0, calls-held['model_calls']), test_runs=max(0, tests-held['test_runs']))

    def release(phase, evidence):
        if phase in journal.snapshot()['reservations']: journal.release(phase, evidence=digest(evidence))

    def tool(phase, target, action, implementation):
        # Reserved phases cannot spill into free generation capacity after exhausting their allocation.
        if phase.startswith(('audit:', 'forward:')) and journal.snapshot()['reservations'].get(phase, {}).get('test_runs', 0) <= 0:
            return {'status': 'BUDGET_EXHAUSTED', 'reason': 'reserved phase allocation exhausted'}
        def operation():
            if execute is not None: return execute(action, implementation)
            from .execution import run_tests
            return run_tests(directory, runtime_receipt, str(target), action,
                             implementation=implementation, timeout=budget.test_timeout)
        try:
            return journal.invoke('test_runs', phase, reference=digest({'action': action, 'implementation': implementation}), operation=operation)
        except BudgetExhausted:
            return {'status': 'BUDGET_EXHAUSTED', 'reason': 'shared lineage budget exhausted or reserved'}

    previous = None; feedback = None; completed = []
    save()
    try:
        # Minimal scope reserve is increased, never narrowed, when complete proposal bindings arrive.
        for i in range(1, max_attempts+1):
            ensure(f'review:{i}', calls=1); ensure(f'audit:{i}', tests=audit_cost({'minimum': 1}))
            ensure(f'forward:{i}', tests=1)
            if i > 1: ensure(f'generation:{i}', calls=repair_calls)
        intent_result = derive_intent(issue, model, journal, str(out / 'intent'), budget=budget)
        result['intent'] = intent_result; save()
        if not (out / 'intent/intent.json').is_file():
            result['reason'] = 'issue intent unavailable or unresolved'; return result
        profile = json.loads((out / 'intent/intent.json').read_bytes())
        verify_intent(issue, profile)
        for i in range(1, max_attempts+1):
            for path, hashes in completed:
                if _tree(path) != hashes: raise ValueError('an earlier attempt changed during repair')
            attempt = out / f'attempt-{i:03d}'; attempt.mkdir()
            generation = attempt / 'generation'
            proposal_number = 0
            requirement_history = previous

            def hook(proposal, ordinal):
                nonlocal proposal_number, requirement_history
                proposal_number += 1
                archive = attempt / 'proposals' / f'{proposal_number:03d}'; archive.mkdir(parents=True)
                (archive / 'proposal.json').write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding='utf-8')
                record = {'candidate_sha256': candidate_digest(proposal), 'state': 'INVALID', 'ordinal': ordinal}
                try:
                    patch = test_patch(directory, proposal['files'])
                    (archive / 'prediction.json').write_text(json.dumps([{'instance_id': issue['instance_id'],
                        'model_patch': patch, 'model_name_or_path': getattr(model, 'model', None) or 'injected-control'}]), encoding='utf-8')
                    record['state'] = 'VALID_TEST_PATCH'
                    if requirement_history: preserve_requirements(requirement_history, proposal)
                    contract = parse(proposal['contract']); rows = scenarios(proposal['scenarios'])
                    if lint(contract): raise ValueError('proposal contract is inconsistent')
                    requirement_history = copy.deepcopy(proposal)
                    counts = {c.id: sum(s.requirement_key == c.id for s in rows) for c in contract.clauses if c.is_live}
                    for s in rows: pytest_nodes(s.run_cmd, proposal['files'])
                    cost = audit_cost(counts)
                    remaining = journal.snapshot()['remaining']
                    forward_cost = sum(counts.values())
                    forecast = plan_remaining(counts, calls=remaining['model_calls'],
                        tests=max(0, remaining['test_runs']-forward_cost),
                        attempts=max_attempts-i+1, repair_calls=repair_calls)
                    forecast['required']['test_runs'] += forward_cost
                    forecast['available_before_forward'] = remaining
                    forecast['shortfall']['test_runs'] = max(0, forecast['required']['test_runs']-remaining['test_runs'])
                    forecast['bound_commands'] = counts
                    forecast['scope'] = 'complete current forward check, review, audit and reserved remaining repairs; no scope reduction'
                    (archive / 'budget-plan.json').write_text(json.dumps(forecast, indent=2), encoding='utf-8')
                    record['budget_plan_sha256'] = sha((archive / 'budget-plan.json').read_bytes())
                    if not forecast['feasible']:
                        raise BudgetExhausted('complete cycle does not fit remaining resources; see immutable budget-plan.json')
                    for later in range(i, max_attempts+1):
                        ensure(f'audit:{later}', tests=cost)
                        ensure(f'forward:{later}', tests=sum(counts.values()))
                    record['reserved_audit_runs'] = cost
                finally:
                    (archive / 'record.json').write_text(json.dumps(record, indent=2), encoding='utf-8')

            def executor(_directory, _runtime, target, action, *, implementation=None, purpose, **kwargs):
                phase = f'forward:{i}' if purpose == 'native-baseline' else f'generation:{i}'
                return tool(phase, target, action, implementation)

            guidance = {'intent': profile}
            if feedback: guidance['previous_public_feedback'] = feedback
            generated = generate_direct(directory, str(generation), _ChargedModel(model, journal, f'generation:{i}'),
                budget=budget, runtime_receipt=runtime_receipt, mode='athena-trust', guidance=guidance,
                test_executor=executor, proposal_hook=hook,
                budget_view=lambda: {'model_calls_available': available(f'generation:{i}', 'model_calls'),
                                     'test_runs_available': available(f'generation:{i}', 'test_runs')})
            row = {'attempt': i, 'generation_state': generated['status'], 'native_state': 'INCOMPLETE',
                   'state': 'INCOMPLETE', 'released': False}
            result['attempts'].append(row)
            release(f'generation:{i}', generated); release(f'forward:{i}', generated)
            if generated['status'] != 'AWAITING_REVIEW':
                (attempt / 'outcome.json').write_text(json.dumps(row, indent=2), encoding='utf-8')
                hashes = _tree(attempt)
                (out / f'attempt-{i:03d}-manifest.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
                result['reason'] = 'generation did not freeze a native-passing candidate'; save(); break
            _, proposal, _ = load_candidate(directory, str(generation))
            review = create_semantic_review(directory, str(generation), str(attempt / 'review'), model,
                                             journal, budget=budget, phase=f'review:{i}')
            release(f'review:{i}', review)
            audit_index = 0
            def audit_execute(action, implementation):
                nonlocal audit_index
                audit_index += 1
                return tool(f'audit:{i}', attempt / 'audit' / 'tools' / f'run-{audit_index:03d}', action, implementation)
            # Native independently typed evidence is retained even if advisory semantics disagree.
            audit = audit_candidate(directory, str(generation), runtime_receipt, str(attempt / 'review/review.json'),
                                    str(attempt / 'audit'), execute=audit_execute, publish=False)
            release(f'audit:{i}', audit)
            row.update(candidate_sha256=generated['candidate_sha256'], native_state=audit['state'],
                support_state=review.get('support', {}).get('state', 'INCOMPLETE'),
                diversity_state=review.get('diversity', {}).get('state', 'INCOMPLETE'))
            ready = (audit['state'] == 'PASS' and row['support_state'] == 'PASS' and row['diversity_state'] == 'PASS')
            row['state'] = 'PASS' if ready else 'FAIL' if audit['state'] == 'FAIL' else 'INCOMPLETE'
            for path, expected_hashes in completed:
                if _tree(path) != expected_hashes:
                    raise ValueError('an earlier immutable attempt changed during execution')
            (attempt / 'outcome.json').write_text(json.dumps(row, indent=2), encoding='utf-8')
            hashes = _tree(attempt)
            (out / f'attempt-{i:03d}-manifest.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
            completed.append((attempt, hashes))
            if ready:
                load_candidate(directory, str(generation))
                if framework_context() != source: raise ValueError('framework changed during cycle')
                prediction = (generation / 'candidate.json').read_bytes()
                (out / 'prediction.json').write_bytes(prediction)
                result.update(state='PASS', released=True, final_attempt=i,
                    prediction_sha256=sha(prediction), reason='declared support/diversity and native curated challenges passed')
                # row remains an immutable attempted outcome; release is recorded by the lineage receipt.
                break
            result.update(state=row['state'], final_attempt=i, reason='candidate withheld; no complete final release')
            previous = proposal
            feedback = public_feedback(proposal, review, audit)
            save()
    except Exception as error:
        result.update(state='INCOMPLETE', released=False, reason='cycle input, model or tool error: '+type(error).__name__)
        (out / 'prediction.json').unlink(missing_ok=True)
    finally:
        save()
    return result
