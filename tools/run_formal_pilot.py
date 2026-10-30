"""Execute installed formal tools on authored controls; no Git or auto-install."""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.assurance import sha
from lib.contract import parse
from lib.formal_evidence import SCHEMA, collect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    parser.add_argument('--python', required=True)
    parser.add_argument('--dafny', required=True)
    args = parser.parse_args()
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parents[1] / 'examples/formal_pilot'
    for path in source.iterdir():
        if path.is_file():
            shutil.copyfile(path, root / path.name)
    inputs = {p.name: sha(p.read_bytes()) for p in root.iterdir() if p.suffix in ('.py', '.dfy', '.md')}
    pin = parse((root / 'contract.md').read_text(encoding='utf-8')).by_id('C-1.1').version
    expected = {'correct.py': 'NO_COUNTEREXAMPLE', 'defect.py': 'COUNTEREXAMPLE',
                'no_contract.py': 'UNKNOWN', 'correct.dfy': 'VERIFIED_RELATIVE_TO_SPEC',
                'defect.dfy': 'UNPROVEN', 'weak.dfy': 'VERIFIED_RELATIVE_TO_SPEC',
                'vacuous.dfy': 'VERIFIED_RELATIVE_TO_SPEC'}
    tasks = [{'id': name, 'clause': 'C-1.1', 'pin': pin,
              'engine': 'crosshair' if name.endswith('.py') else 'dafny', 'target': name,
              'subject_kind': 'implementation' if name.endswith('.py') else 'model',
              'scope': 'integer doubling property as written in ' + name,
              'inputs': inputs, 'assumptions': ['Tool and solver installation are trusted.',
                  'These authored source files are the complete declared pilot inputs.',
                  'User-intent fidelity has not been independently reviewed.']} for name in expected]
    (root / 'manifest.json').write_text(json.dumps({'schema': SCHEMA, 'contract': 'contract.md', 'tasks': tasks}, indent=2), encoding='utf-8')
    report = collect(root, 'manifest.json', python=args.python, dafny=args.dafny, timeout=40)
    infrastructure_errors = [r['id'] for r in report['results'] if r['state'] == 'UNKNOWN' and expected[r['id']] != 'UNKNOWN']
    report['pilot'] = {'expected': expected, 'matched': all(r['state'] == expected[r['id']] for r in report['results']),
                       'infrastructure_unknowns': infrastructure_errors,
                       'scope': 'Seven authored tool-boundary controls; not an independent effectiveness benchmark.'}
    (root / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'matched': report['pilot']['matched'], 'results': [(r['id'], r['state']) for r in report['results']]}))
    return 0 if report['pilot']['matched'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
