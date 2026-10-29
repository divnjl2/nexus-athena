"""Executed, deliberately small controls for assurance accounting, not a benchmark.

Run: python examples/assurance_demo.py OUTPUT_DIRECTORY
The arithmetic oracle is authored here; this does not infer user intent.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.assurance import SCHEMA, assess, render, sha
from lib.contract import parse


def build(destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    sources = {
        'correct.py': 'def twice(x): return x * 2\n',
        'alternative.py': 'def twice(x): return float(x + x)\n',
        'defect.py': 'def twice(x): return x * 3\n',
        'sound.py': 'def check(f): return all(f(x) == 2*x for x in (0, 1, 3))\n',
        'strict.py': 'def check(f): return all(type(f(x)) is int and f(x) == 2*x for x in (0, 1, 3))\n',
        'vacuous.py': 'def check(f): return True\n',
    }
    cases = [('correct implementation', 'correct', 'sound'),
             ('activated defect', 'defect', 'sound'),
             ('valid alternative rejected by strict check', 'alternative', 'strict'),
             ('defect accepted by vacuous check', 'defect', 'vacuous'),
             ('unobserved requirement', None, None)]
    contract = '# Executable assurance demo\n\n' + ''.join(
        f'- **C-1.{i}** — WHEN nonnegative integers are doubled in case "{label}" THE SYSTEM SHALL return a numeric value equal to twice the input.\n'
        for i, (label, _, _) in enumerate(cases, 1))
    sources['contract.md'] = contract
    # The runner and arithmetic witness are bound inputs too.
    sources['runner.py'] = Path(__file__).read_text(encoding='utf-8')
    for name, content in sources.items():
        (destination / name).write_text(content, encoding='utf-8')
    inputs = {name: sha((destination / name).read_bytes()) for name in sources}
    manifest = {'schema': SCHEMA, 'contract': 'contract.md',
                'implementation': ['correct.py', 'alternative.py', 'defect.py'], 'evidence': []}
    parsed = parse(contract)

    def run(program):
        completed = subprocess.run([sys.executable, '-c', program], cwd=destination,
                                   capture_output=True, text=True, timeout=15)
        return {'argv': [sys.executable, '-c', program], 'returncode': completed.returncode,
                'stdout': completed.stdout, 'stderr': completed.stderr}

    for i, (_, target, checker) in enumerate(cases, 1):
        if target is None:
            continue
        # An independently written arithmetic witness establishes that the seeded
        # defect changes the required output, rather than merely changing bytes.
        witness = run('import defect, json; actual=defect.twice(3); print(json.dumps({"input":3,"expected":6,"actual":actual})); raise SystemExit(0 if actual != 6 else 1)')
        for kind, variant in [('execution', target), ('valid_alternative', 'alternative'), ('violation', 'defect')]:
            receipt = run(f'from {variant} import twice; from {checker} import check; raise SystemExit(0 if check(twice) else 1)')
            expected = 1 if kind == 'violation' else 0
            outcome = 'PASS' if receipt['returncode'] == expected else 'FAIL' if receipt['returncode'] in (0, 1) else 'UNKNOWN'
            artifact = f'case-{i}-{kind}.json'
            (destination / artifact).write_text(json.dumps({'observation': receipt, 'activation_witness': witness}, indent=2), encoding='utf-8')
            manifest['evidence'].append({
                'id': f'{i}-{kind}', 'clause': f'C-1.{i}', 'pin': parsed.by_id(f'C-1.{i}').version,
                'kind': kind, 'outcome': outcome, 'scope': 'nonnegative integer examples 0, 1, 3',
                'producer': 'local subprocess demo', 'basis': 'exit status, source-bound check and arithmetic activation witness',
                'inputs': inputs, 'checks': [checker + '.py', 'runner.py'],
                'artifact': artifact, 'artifact_sha256': sha((destination / artifact).read_bytes()),
                **({'activated': witness['returncode'] == 0} if kind == 'violation' else {})})
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    report = assess(destination, 'manifest.json')
    (destination / 'assessment.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    import webbrowser
    output = Path(sys.argv[1]).resolve()
    report = build(output)
    page = output / 'review.html'
    page.write_text(render(report), encoding='utf-8')
    webbrowser.open(page.as_uri())
    print(json.dumps({'report': str(page), 'counts': report['counts']}, indent=2))
