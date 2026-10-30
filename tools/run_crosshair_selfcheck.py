"""CrossHair-first pilot against snapshots of the production evidence reducer.

Mutations never touch the live repository. No Git or implicit installation.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.assurance import sha
from lib.contract import parse
from lib.formal_evidence import SCHEMA, collect


def describe_snapshot(root: Path) -> dict:
    """Exhaustively replay the four boolean inputs, separately from tool search."""
    tree = ast.parse((root / 'lib/assurance.py').read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'combine')
    namespace = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<frozen reducer>', 'exec'), namespace)
    expected = {(False, False): 'UNKNOWN', (True, False): 'SUPPORTED',
                (False, True): 'CONTRADICTED', (True, True): 'CONFLICT'}
    return {'matrix': [{'support': s, 'contradiction': c, 'expected': wanted,
                        'actual': namespace['combine'](s, c)} for (s, c), wanted in expected.items()],
            'method': 'Exhaustive replay of four boolean inputs on the frozen function; distinct from CrossHair search.'}


def prepare(source: Path, output: Path) -> dict:
    """Freeze real production inputs before seeding semantic faults in copies."""
    original = (source / 'lib/assurance.py').read_text(encoding='utf-8')
    tree = ast.parse(original)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'combine')
    segment = ast.get_source_segment(original, function)
    assert segment and segment.count('if support and contradiction:') == 1
    alternative = ast.parse(segment).body[0]
    alternative.body = [alternative.body[0], ast.Return(value=ast.parse(
        '{(False, False): "UNKNOWN", (True, False): "SUPPORTED", '
        '(False, True): "CONTRADICTED", (True, True): "CONFLICT"}[(support, contradiction)]', mode='eval').body)]
    ast.fix_missing_locations(alternative)
    variants = {
        'production': (segment, 'NO_COUNTEREXAMPLE'),
        'valid-table-alternative': (ast.unparse(alternative), 'NO_COUNTEREXAMPLE'),
        'conflict-on-either': (segment.replace('if support and contradiction:', 'if support or contradiction:'), 'COUNTEREXAMPLE'),
        'silence-is-support': (segment.replace('else "UNKNOWN"', 'else "SUPPORTED"'), 'COUNTEREXAMPLE'),
        'hide-conflict': (segment.replace('return "CONFLICT"', 'return "SUPPORTED"'), 'COUNTEREXAMPLE'),
    }
    no_contract = ast.parse(segment).body[0]
    no_contract.body = no_contract.body[1:]
    ast.fix_missing_locations(no_contract)
    variants['missing-contract'] = (ast.unparse(no_contract), 'UNKNOWN')
    output.mkdir(parents=True, exist_ok=True)
    expected = {}
    for label, (replacement, state) in variants.items():
        root = output / label
        (root / 'lib').mkdir(parents=True, exist_ok=True)
        for name in ('__init__.py', 'assurance.py', 'contract.py', 'ast.py', 'versioning.py'):
            raw = (source / 'lib' / name).read_bytes()
            (root / 'lib' / name).write_bytes(raw)
        # Keep the real module around the function, including actual imports.
        if label != 'production':
            (root / 'lib/assurance.py').write_text(original.replace(segment, replacement, 1), encoding='utf-8')
        (root / 'contract.md').write_bytes((source / 'features/assurance/contract.md').read_bytes())
        inputs = {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in [root / 'contract.md', *sorted((root / 'lib').glob('*.py'))]}
        pin = parse((root / 'contract.md').read_text(encoding='utf-8')).by_id('C-1.4').version
        task = {'id': label, 'clause': 'C-1.4', 'pin': pin, 'engine': 'crosshair',
                'target': 'lib/assurance.py', 'subject_kind': 'implementation',
                'scope': 'Only combine(bool, bool): four evidence states; not the complete assess pipeline.',
                'inputs': inputs, 'assumptions': ['The authored postconditions capture the intended four-state truth table.',
                    'The installed CrossHair/Python/solver runtime is trusted.',
                    'This declared module closure covers the selected pure function.']}
        (root / 'manifest.json').write_text(json.dumps({'schema': SCHEMA, 'contract': 'contract.md', 'tasks': [task]}, indent=2), encoding='utf-8')
        expected[label] = state
    provenance = {'source': str(source), 'production_source_sha256': sha((source / 'lib/assurance.py').read_bytes()),
                  'production_snapshot_sha256': sha((output / 'production/lib/assurance.py').read_bytes()),
                  'expected': expected, 'scope': 'One production function, a valid alternative, three seeded defects and missing-contract control.'}
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    return provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    parser.add_argument('--python', required=True, help='Python with installed CrossHair')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    source = Path(__file__).resolve().parents[1]
    provenance = prepare(source, output)
    results = []
    for name in provenance['expected']:
        receipt = collect(output / name, 'manifest.json', python=args.python, dafny='', timeout=30)
        receipt['results'][0]['replay'] = describe_snapshot(output / name)
        (output / name / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        results.extend(receipt['results'])
    report = {'schema': SCHEMA, 'results': results, 'provenance': provenance,
              'matched': all(r['state'] == provenance['expected'][r['id']] for r in results),
              'limitations': ['One selected pure function is assessed, not the full framework.',
                              'Authored controls are not an independent effectiveness benchmark.',
                              'NO_COUNTEREXAMPLE is not a proof or release decision.']}
    (output / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    from lib.formal_review import render
    import webbrowser
    page = output / 'review.html'
    page.write_text(render(report), encoding='utf-8')
    webbrowser.open(page.as_uri())
    print(json.dumps({'matched': report['matched'], 'states': [(r['id'], r['state']) for r in results], 'review': str(page)}))
    return 0 if report['matched'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
