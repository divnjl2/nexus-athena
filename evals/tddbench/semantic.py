"""Fresh semantic declarations and structural contrast checks; never a truth oracle."""
from __future__ import annotations
import ast
import json
import pathlib

from lib.contract import parse
from .adapter import sha
from .intent import digest, public_issue, verify_intent, new_assertions, check_support
from .execution import validate_reference
from .trust import load_candidate, review_payload, review_scope, REVIEW_SYSTEM, _variant
from .native import pytest_nodes


SEMANTIC_REVIEW_SYSTEM = REVIEW_SYSTEM.replace(
    'with activation_files and passports.',
    'with activation_files, passports, intent_reviews and assertion_reviews.') + '''
The intent passport predates candidate generation. Review it rather than assuming it is
correct. For every live intent return {intent: ID, status: SUPPORTED|UNJUSTIFIED|UNRESOLVED,
reason: text}. For every assertion_manifest entry return {assertion: ID, status: same,
reason: text, intents: [live IDs], quotes: [exact public issue substrings]}. Supported
assertions require at least one exact quote. Explain the logical connection; quotations
alone do not prove an oracle. Distinguish numeric meaning from its spelling, observable
requirements from internal implementation, and examples from exhaustive restrictions.
Each valid variant also needs distinction (mechanism or representation), source_quotes
(exact issue substrings), and distinction_reason. At least one mechanism alternative is
required; where any bound intent has representation=open, a separate representation
alternative is required too. Two copies or parenthesis-only edits supply no diversity.
Do not invent justification to obtain approval. Real unknowns must stay UNRESOLVED.
These are advisory declarations. Executed controls provide only curated challenge evidence.
Also return uncertainty_reviews (a list, empty when there are no issue questions).
For every intent.unresolved entry, its ID is U1, U2, ... in that list's order. Return
{question: ID, status: RESOLVED|NONBLOCKING|UNRESOLVED, reason: text, quotes: [exact issue
substrings], source_quotes: [{path: public implementation path, quote: exact BASE code
substring}]}. A RESOLVED or NONBLOCKING judgment needs public issue or base-code evidence.
Missing example inputs, unspecified harmless formatting choices or tolerances do not
automatically prevent constructing a justified regression test. Explain specifically
why a question is harmless or resolved for this candidate's obligations; do not infer
authority from the proposed reference. Real ambiguity still stays UNRESOLVED. Keep all
questions in the record; this review adds declarations rather than rewriting the passport.
'''


def _base(directory, names):
    root = pathlib.Path(directory) / 'source'
    return {n: (root / n).read_text(encoding='utf-8') if (root / n).is_file() else '' for n in names}


def check_protocol(proposal, payload):
    """Useful pre-execution schema diagnostics; no command is executed here."""
    result={'state':'INCOMPLETE','problems':[],'validity':'STRUCTURAL_ONLY'}
    try:
        expected={r['clause']:r for r in review_scope(proposal)}
        passports=payload.get('passports')
        if (not isinstance(passports,list) or len(passports)!=len(expected)
                or {p.get('clause') for p in passports if isinstance(p,dict)}!=set(expected)):
            raise ValueError('passports must cover exactly the controller live_scope clauses')
        activation=payload.get('activation_files')
        for p in passports:
            for key in ('intent_source','owner_decision','input_domain','observable_outcome','oracle_source'):
                if not isinstance(p.get(key),str) or not p[key].strip():
                    raise ValueError('passport '+key+' must be a nonempty string')
            for key in ('assumptions','undefined_behavior','known_gaps'):
                if not isinstance(p.get(key),list) or any(not isinstance(v,str) for v in p[key]):
                    raise ValueError('passport '+key+' must be a list of strings')
            specs=p.get('specs')
            if not isinstance(specs,list) or len(specs)!=len(expected[p['clause']]['specs']) or set(specs)!=set(expected[p['clause']]['specs']):
                raise ValueError('passport specs differ from controller live_scope')
            variants=p.get('variants')
            if not isinstance(variants,list):raise ValueError('passport variants must be a list')
            for v in variants:
                if not isinstance(v,dict):raise ValueError('variant must be an object')
                if v.get('kind')=='violation':pytest_nodes(v.get('activation'),activation)
        result['state']='PASS'
    except (ValueError,TypeError,KeyError,AttributeError) as error:
        result['problems'].append(str(error))
    return result


def check_controls(directory, issue, profile, proposal, review):
    """Reject structurally empty diversity; no algorithm can infer semantic equivalence here."""
    result = {'state': 'INCOMPLETE', 'passed': False, 'problems': [],
              'validity': 'MODEL_DECLARED_NOT_ATTESTED', 'controls': []}
    try:
        verify_intent(issue, profile)
        expected = {c.id for c in parse(proposal['contract']).clauses if c.is_live}
        passports = review.get('passports')
        if (not isinstance(passports, list) or len(passports) != len(expected)
                or {p.get('clause') for p in passports if isinstance(p, dict)} != expected):
            raise ValueError('missing or duplicate clause passports')
        intents = {r['id']: r for r in profile['requirements'] if r['is_live']}
        reference = validate_reference(directory, proposal['reference'])
        for passport in passports:
            owners = proposal['intent_bindings'][passport['clause']]
            required = {'mechanism'}
            if any(intents[i]['representation'] == 'open' for i in owners):
                required.add('representation')
            variants = passport.get('variants')
            if not isinstance(variants, list): raise ValueError('missing variants')
            valid = [v for v in variants if v.get('kind') == 'valid']
            violations = [v for v in variants if v.get('kind') == 'violation']
            if not 1 <= len(valid) <= 2 or len(violations) != 1 or len(valid)+len(violations) != len(variants):
                raise ValueError('incomplete or over-budget control set')
            seen = set(); distinctions = set()
            for v in valid:
                if v.get('distinction') not in ('mechanism', 'representation'):
                    raise ValueError('valid control has no declared distinction')
                if not isinstance(v.get('distinction_reason'), str) or not v['distinction_reason'].strip():
                    raise ValueError('valid control lacks distinction reason')
                quotes = v.get('source_quotes')
                if (not isinstance(quotes, list) or not quotes
                        or any(not isinstance(q, str) or not q or q not in issue['problem_statement'] for q in quotes)):
                    raise ValueError('valid control has no issue source')
                overlay = _variant(directory, v.get('files'), reference)
                paths = set(reference) | set(overlay)
                baseline = {**_base(directory, paths), **reference}
                target = {**baseline, **overlay}
                before = {n: ast.dump(ast.parse(baseline[n]), include_attributes=False) for n in paths}
                after = {n: ast.dump(ast.parse(target[n]), include_attributes=False) for n in paths}
                # Compare complete targets, including unchanged implementation paths.
                signature = digest({n: after[n] for n in paths if after[n] != before[n]})
                if before == after or signature in seen:
                    raise ValueError('unchanged or duplicate control cannot establish diversity')
                seen.add(signature); distinctions.add(v['distinction'])
                result['controls'].append({'clause': passport['clause'], 'id': v.get('id'),
                    'distinction': v['distinction'], 'target_ast_sha256': signature})
            if not required <= distinctions:
                raise ValueError('missing required mechanism or representation alternative')
        result.update(state='PASS', passed=True)
    except (ValueError, TypeError, KeyError, AttributeError, SyntaxError) as error:
        result['problems'].append('invalid diversity evidence: ' + type(error).__name__ + ': ' + str(error))
    return result


def create_semantic_review(directory, generation, destination, model, journal, *, budget, phase):
    """Issue/profile/candidate-only fresh context, bound to pre-generation guidance."""
    receipt, proposal, _ = load_candidate(directory, generation)
    root = pathlib.Path(directory)
    issue = public_issue(json.loads((root / 'issue.json').read_bytes()))
    frozen = pathlib.Path(generation) / 'semantic-guidance.json'
    if sha(frozen.read_bytes()) != receipt.get('semantic_guidance_sha256'):
        raise ValueError('semantic guidance was not frozen before generation')
    profile = json.loads(frozen.read_bytes())['intent']
    verify_intent(issue, profile)
    out = pathlib.Path(destination).resolve()
    if out.is_relative_to(root.resolve()) or root.resolve().is_relative_to(out):
        raise ValueError('review output must be separate from public source')
    out.mkdir(parents=True, exist_ok=False)
    result = {'schema': 'athena.tdd_review/1', 'state': 'INCOMPLETE', 'calls': 0,
        'candidate_sha256': receipt['candidate_sha256'], 'snapshot_sha256': receipt['snapshot_sha256'],
        'issue_sha256': digest(issue), 'intent_sha256': profile['sha256'],
        'guidance_sha256': receipt['semantic_guidance_sha256'],
        'origin': 'independent-model' if getattr(model, 'source_kind', '') == 'model' else 'scripted-control',
        'reviewer_id': getattr(model, 'model', None) or 'injected-reviewer',
        'independence': 'SEPARATE_CONTEXT_DECLARATION_NOT_ATTESTATION',
        'reason': 'review not completed'}
    try:
        reference = validate_reference(directory, proposal['reference'])
        public = review_payload(issue, proposal, _base(directory, reference), reference)
        public.update(intent=profile, live_scope=review_scope(proposal), assertion_manifest=new_assertions(proposal['files'], _base(directory, proposal['files'])),
                      execution_budget=journal.snapshot(), execution_python=receipt.get('execution_python'))
        messages = [{'role': 'system', 'content': SEMANTIC_REVIEW_SYSTEM},
                    {'role': 'user', 'content': json.dumps(public, ensure_ascii=False)}]
        (out / 'request.json').write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding='utf-8')
        if len(json.dumps(messages, ensure_ascii=False)) > budget.max_context_chars:
            result['reason'] = 'semantic review context budget exhausted'; return result
        if receipt.get('source_kind') == 'model' and getattr(model, 'model', None) != receipt.get('model'):
            result['reason'] = 'review model differs from generation'; return result
        # The journal owns admission. A denied call is not counted as a completed review.
        ticket = journal.charge('model_calls', phase, reference=digest(messages))
        result['calls'] = 1
        (out / 'review.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        try:
            reply = model(messages, budget)
        except BaseException as error:
            journal.finish(ticket, 'TIMEOUT' if isinstance(error, TimeoutError) else 'ERROR', error_type=type(error).__name__)
            raise
        journal.finish(ticket, 'COMPLETED', usage=reply.get('usage'))
        (out / 'response.json').write_text(json.dumps(reply, ensure_ascii=False, indent=2), encoding='utf-8')
        if reply.get('finish_reason') != 'stop':
            result['reason'] = 'semantic review missing or truncated'; return result
        known = {t.get('served_model') for t in receipt.get('turns', []) if t.get('served_model')}
        if result['origin'] == 'independent-model' and known and reply.get('served_model') and reply['served_model'] not in known:
            result['reason'] = 'served review model differs from generation'; return result
        payload = json.loads(reply['text'])
        required={'activation_files', 'passports', 'intent_reviews', 'assertion_reviews'}
        if (not isinstance(payload, dict) or not required <= set(payload)
                or set(payload)-required-{'uncertainty_reviews'}):
            raise ValueError('semantic review fields missing or unexpected')
        result.update(payload)
        result['support'] = check_support(issue, profile, proposal, _base(directory, set(proposal['files']) | set(reference)), result)
        result['diversity'] = check_controls(directory, issue, profile, proposal, result)
        result['protocol'] = check_protocol(proposal, result)
        # READY permits native examination; it does not assert semantic truth or release.
        result.update(state='READY' if result['protocol']['state']=='PASS' else 'INCOMPLETE',
            reason='advisory declarations await independent native execution' if result['protocol']['state']=='PASS'
                   else 'review protocol invalid: '+'; '.join(result['protocol']['problems']))
    except Exception as error:
        result['reason'] = 'semantic review error: ' + type(error).__name__
    finally:
        result['journal_head'] = journal.head
        (out / 'review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
