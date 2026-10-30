"""Extracted acceptance controls from the frozen-study scope audit.

These are minimal reproductions of false-rejection *risks*, not reruns of the
upstream projects or claims that their original benchmark grades were wrong.
The reviewed `preserve` seam below explicitly adapts each fixture's mechanism;
no automatic discovery of arbitrary replacement APIs is claimed.
Warning guidance is an owner-reviewed finite set of English messages, not an
automatic semantic recognizer for arbitrary equivalent wording.

Source: verification-study-20261028-01/semantic-scope-audit-20261029/result.json
Public issues: pydata/xarray#4687, astropy/astropy#13236, pylint-dev/pylint#4661.
The collector/helper control additionally extracts pytest-dev/pytest#10356;
the separately archived native experiment is not a dependency of this fixture.
"""
from __future__ import annotations

import json
import textwrap

import pytest

from lib.contract import parse, pin_scenarios
from lib.spec_trust import SCHEMA, audit


def source(text):
    return textwrap.dedent(text).lstrip()


CASES = {
    'equivalent-mechanism': {
        'intent': 'Preserve the supplied metadata through an explicitly reviewed public mechanism.',
        'origin': 'https://github.com/pydata/xarray/issues/4687',
        'baseline': source('''
            def select(data, *, keep_attrs=False):
                values, attrs = data
                return list(values), dict(attrs) if keep_attrs else {}

            def preserve(data):
                return select(data, keep_attrs=True)
        '''),
        'valid': source('''
            from contextlib import contextmanager
            _preserve_attributes = False

            @contextmanager
            def metadata_policy():
                global _preserve_attributes
                before = _preserve_attributes
                _preserve_attributes = True
                try:
                    yield
                finally:
                    _preserve_attributes = before

            def select(data):
                values, attrs = data
                return list(values), dict(attrs) if _preserve_attributes else {}

            def preserve(data):
                with metadata_policy():
                    return select(data)
        '''),
        'violation': source('''
            def select(data, *, keep_attrs=False):
                return list(data[0]), {}

            def preserve(data):
                return select(data, keep_attrs=True)
        '''),
        'oracle': source('''
            from api import preserve

            def test_observable_contract():
                data = ([2, 7, -3], {'units': 'm', 'description': 'height'})
                actual = preserve(data)
                assert actual == ([2, 7, -3], {'units': 'm', 'description': 'height'})
                assert data == ([2, 7, -3], {'units': 'm', 'description': 'height'})
        '''),
        'too_strict': source('''
            import inspect
            from api import select

            def test_overstrict_keyword_contract():
                # This wrongly upgrades one API mechanism into the requirement.
                assert 'keep_attrs' in inspect.signature(select).parameters
                assert select(([2, 7, -3], {'units': 'm'}), keep_attrs=True)[1] == {'units': 'm'}
        '''),
        'activation': source('''
            from api import preserve

            def test_violation_is_observable():
                assert preserve(([2, 7, -3], {'units': 'm'}))[1] != {'units': 'm'}
        '''),
        'distinction': 'A context-managed policy replaces the keep_attrs keyword; the reviewed preserve seam exposes equivalent values and metadata.',
    },
    'warning-wording': {
        'intent': 'Warn about the selected transition with explicit Column migration guidance while preserving values.',
        'origin': 'https://github.com/astropy/astropy/issues/13236',
        'baseline': source('''
            import warnings

            def convert(data):
                warnings.warn('Wrap structured input in Column(data); future conversion will change.', FutureWarning)
                return tuple(data)
        '''),
        'valid': source('''
            import warnings

            def convert(data):
                warnings.warn('Use Column(data) explicitly; automatic conversion will change.', FutureWarning)
                return tuple(data)
        '''),
        'additional_valid': [{
            'id': 'next-release-guidance',
            'reason': 'Owner-reviewed next-release/is-changing wording conveys the same selected warning-stage transition.',
            'source': source('''
                import warnings

                def convert(data):
                    warnings.warn('Use Column(data) explicitly; automatic conversion is changing in the next release.', FutureWarning)
                    return tuple(data)
            '''),
        }],
        'violation': source('''
            def convert(data):
                return tuple(data)
        '''),
        'oracle': source('''
            import warnings
            from api import convert

            def test_observable_contract():
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    actual = convert([('a', 1), ('b', 2)])
                assert actual == (('a', 1), ('b', 2))
                messages = [str(w.message).lower() for w in caught if issubclass(w.category, FutureWarning)]
                assert messages
                # This fixture's owner explicitly reviewed these finite messages.
                # It does not pretend lexical fragments decide arbitrary semantics.
                reviewed_guidance = {
                    'wrap structured input in column(data); future conversion will change.',
                    'use column(data) explicitly; automatic conversion will change.',
                    'use column(data) explicitly; automatic conversion is changing in the next release.',
                }
                assert any(text in reviewed_guidance for text in messages)
        '''),
        'too_strict': source('''
            import warnings
            from api import convert

            def test_overstrict_warning_word():
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    convert([('a', 1)])
                assert any('structured' in str(w.message).lower() for w in caught)
        '''),
        'activation': source('''
            import warnings
            from api import convert

            def test_violation_is_observable():
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    convert([('a', 1)])
                assert not any(issubclass(w.category, FutureWarning) for w in caught)
        '''),
        'distinction': 'Owner-reviewed finite migration messages include will-change and next-release/is-changing wording without the literal structured; this fixture freezes the warning stage and does not resolve the original release-stage ambiguity.',
    },
    'unrelated-files': {
        'intent': 'Store the persistent statistics product beneath the selected root and preserve roundtrip content.',
        'origin': 'https://github.com/pylint-dev/pylint/issues/4661',
        'baseline': source('''
            import json

            def persist(workspace, root, data):
                product = root / 'application' / 'results.json'
                product.parent.mkdir(parents=True, exist_ok=True)
                product.write_text(json.dumps(data), encoding='utf-8')
                return product
        '''),
        'valid': source('''
            import json

            def persist(workspace, root, data):
                product = root / 'application' / 'results.json'
                product.parent.mkdir(parents=True, exist_ok=True)
                product.write_text(json.dumps(data), encoding='utf-8')
                # An unrelated allowed diagnostic is not a statistics product.
                (workspace / 'run.log').write_text('statistics saved', encoding='utf-8')
                return product
        '''),
        'additional_valid': [{
            'id': 'diagnostic-in-legacy-named-directory',
            'reason': 'The statistics product stays under the selected root; an unrelated diagnostic under a legacy-named directory does not move that product.',
            'source': source('''
                import json

                def persist(workspace, root, data):
                    product = root / 'application' / 'results.json'
                    product.parent.mkdir(parents=True, exist_ok=True)
                    product.write_text(json.dumps(data), encoding='utf-8')
                    diagnostics = workspace / '.pylint.d'
                    diagnostics.mkdir(exist_ok=True)
                    (diagnostics / 'run.log').write_text('diagnostic only', encoding='utf-8')
                    return product
            '''),
        }],
        'violation': source('''
            import json

            def persist(workspace, root, data):
                product = workspace / '.pylint.d' / 'results.json'
                product.parent.mkdir(parents=True, exist_ok=True)
                product.write_text(json.dumps(data), encoding='utf-8')
                return product
        '''),
        'oracle': source('''
            import json
            from api import persist

            def test_observable_contract(tmp_path):
                root = tmp_path / 'xdg-data'
                payload = {'statement': 7, 'warning': 2}
                product = persist(tmp_path, root, payload)
                assert product.is_file()
                assert root in product.parents
                assert json.loads(product.read_text(encoding='utf-8')) == payload
        '''),
        'too_strict': source('''
            from api import persist

            def test_overstrict_all_workspace_files(tmp_path):
                root = tmp_path / 'xdg-data'
                persist(tmp_path, root, {'statement': 7})
                files = [path for path in tmp_path.rglob('*') if path.is_file()]
                assert files
                # Wrongly extends a product-placement rule to every workspace file.
                assert all(root in path.parents for path in files)
        '''),
        'activation': source('''
            from api import persist

            def test_violation_is_observable(tmp_path):
                root = tmp_path / 'xdg-data'
                product = persist(tmp_path, root, {'statement': 7})
                assert root not in product.parents
                assert product.is_file()
        '''),
        'distinction': 'Same persistence product and roundtrip, plus a permitted diagnostic outside the product root; only the product-placement obligation is enforced.',
    },
}


def write_project(root, case, *, too_strict):
    root.mkdir()
    (root / 'api.py').write_text(case['baseline'], encoding='utf-8')
    (root / 'test_spec.py').write_text(case['too_strict'] if too_strict else case['oracle'], encoding='utf-8')
    (root / 'activation.py').write_text(case['activation'], encoding='utf-8')
    contract = '# Extracted scope regression\n- **C-1.1** — WHEN the fixture is exercised THE SYSTEM SHALL ' + case['intent'][0].lower() + case['intent'][1:] + '\n'
    (root / 'contract.md').write_text(contract, encoding='utf-8')
    parsed = parse(contract)
    scenarios = '### S1.1 - Observable behavior\n- **verifies:** C-1.1\n- **run_cmd:** `python -m pytest test_spec.py -q`\n'
    (root / 'scenarios.md').write_text(pin_scenarios(scenarios, parsed)[0], encoding='utf-8')
    manifest = {'schema': SCHEMA, 'contract': 'contract.md', 'scenarios': 'scenarios.md',
        'inputs': ['api.py', 'test_spec.py', 'activation.py'], 'implementation': ['api.py'],
        'passports': [{'clause': 'C-1.1', 'pin': parsed.by_id('C-1.1').version,
            'intent_source': case['origin'], 'owner_decision': 'Extracted minimal reproduction, not upstream execution: ' + case['distinction'],
            'input_domain': 'Declared finite fixture examples', 'observable_outcome': case['intent'],
            'oracle_source': 'Reviewed fixture behavior and existing native typed-execution audit',
            'assumptions': ['The stated fixture freedom is owner-declared; not automatically inferred semantic truth.'],
            'undefined_behavior': ['Arbitrary APIs, warning languages and unrelated file policies outside this fixture.'],
            'known_gaps': [], 'specs': ['S1.1'], 'variants': [
                {'id': 'declared-valid-alternative', 'kind': 'valid', 'reason': case['distinction'], 'files': {'api.py': case['valid']}},
                {'id': 'activated-violation', 'kind': 'violation', 'reason': 'The stated observable fixture obligation is broken.',
                 'activation': 'python -m pytest activation.py -q', 'files': {'api.py': case['violation']}}]}]}
    variants = manifest['passports'][0]['variants']
    variants[1:1] = [
        {'id': alternative['id'], 'kind': 'valid', 'reason': alternative['reason'],
         'files': {'api.py': alternative['source']}}
        for alternative in case.get('additional_valid', [])
    ]
    (root / 'trust.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def assert_oracle_controls(tmp_path, case):
    corrected_root = tmp_path / 'corrected'
    strict_root = tmp_path / 'overstrict'
    write_project(corrected_root, case, too_strict=False)
    write_project(strict_root, case, too_strict=True)

    corrected = audit(str(corrected_root), 'trust.json')
    assert corrected['state'] == 'PASS', corrected
    assert corrected['metrics']['false_rejects'] == corrected['metrics']['false_accepts'] == 0
    challenges = corrected['clauses'][0]['challenges']
    valid = [row for row in challenges if row['kind'] == 'valid']
    violation, = [row for row in challenges if row['kind'] == 'violation']
    assert len(valid) == 1 + len(case.get('additional_valid', []))
    assert all(row['state'] == 'PASS' and row['checks'][0]['status'] == 'PASS' for row in valid)
    assert violation['state'] == 'PASS'
    assert violation['activation_baseline']['status'] == 'ASSERTION_FAIL'
    assert violation['activation']['status'] == 'PASS'
    assert violation['checks'][0]['status'] == 'ASSERTION_FAIL'

    strict = audit(str(strict_root), 'trust.json')
    assert strict['clauses'][0]['baseline'][0]['status'] == 'PASS'
    assert strict['state'] == 'FAIL'
    assert strict['metrics']['false_rejects'] == len(valid)
    strict_valid = [row for row in strict['clauses'][0]['challenges'] if row['kind'] == 'valid']
    assert all(row['checks'][0]['status'] == 'ASSERTION_FAIL' for row in strict_valid)
    assert (corrected_root / 'api.py').read_text(encoding='utf-8') == case['baseline']


@pytest.mark.parametrize('case_name', CASES)
def test_semantic_oracles_accept_declared_freedom_and_detect_real_violations(tmp_path, case_name):
    """C-3.2 — executed audit controls expose three observed classes of overstrict-oracle risk."""
    assert_oracle_controls(tmp_path, CASES[case_name])


def test_public_collection_accepts_a_different_private_helper_boundary(tmp_path):
    """C-3.3 — a private helper obligation must not replace public inherited collection."""
    case = {
        'intent': 'Expose inherited marker names through collect for the declared class examples, leaving helper responsibilities free.',
        'origin': 'https://github.com/pytest-dev/pytest/issues/10356',
        'baseline': source('''
            def _stored(cls):
                return [m for base in reversed(cls.__mro__)
                        for m in base.__dict__.get('markers', ())]

            def collect(cls):
                return _stored(cls)
        '''),
        'valid': source('''
            def _stored(cls):
                return list(getattr(cls, 'markers', ()))

            def collect(cls):
                return [m for base in reversed(cls.__mro__) if 'markers' in base.__dict__
                        for m in _stored(base)]
        '''),
        'violation': source('''
            def _stored(cls):
                return list(getattr(cls, 'markers', ()))

            def collect(cls):
                return _stored(cls)
        '''),
        'oracle': source('''
            from api import collect

            def test_observable_contract():
                class Left:
                    markers = ['left']
                class Right:
                    markers = ['right']
                for bases in ((Left, Right), (Right, Left)):
                    for own in ({}, {'markers': ['child']}):
                        child = type('Child', bases, own)
                        assert set(collect(child)) == {'left', 'right'} | set(own.get('markers', ()))
                assert Left.markers == ['left'] and Right.markers == ['right']
        '''),
        'too_strict': source('''
            from api import _stored

            def test_unjustified_private_merge():
                class Left:
                    markers = ['left']
                class Right:
                    markers = ['right']
                class Child(Left, Right):
                    pass
                assert set(_stored(Child)) == {'left', 'right'}
        '''),
        'activation': source('''
            from api import collect

            def test_violation_is_observable():
                class Left:
                    markers = ['left']
                class Right:
                    markers = ['right']
                class Child(Left, Right):
                    pass
                assert 'right' not in collect(Child)
        '''),
        'distinction': 'The same public inherited-name behavior can be implemented in the collector or in a private helper; exact helper responsibilities, marker ordering and duplicates are outside this finite fixture.',
    }
    assert_oracle_controls(tmp_path, case)
