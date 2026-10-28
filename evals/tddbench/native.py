"""Actual Athena contract checks over a public, model-proposed reference implementation.

No gold code is read and no proposed implementation enters the evaluator prediction.
All code execution is delegated to the offline pytest tool, never to the host shell.
"""
from __future__ import annotations

import difflib
import json
import pathlib

from lib import check, contract_report
from lib.contract import lint, parse, pin_scenarios
from lib.scenario_parser import parse as parse_scenarios
from lib.spec_runner import _tokenize, make_ledger, run_specs
from lib.versioning import hash_text

from .execution import validate_reference, validate_test_action
from .adapter import sha
from .workspace import verify_workspace
from .fsmodel import through_link
from .test_preservation import preserve_named_tests


def framework_context() -> dict:
    root = pathlib.Path(__file__).resolve().parents[2]
    files = [*sorted((root / 'lib').rglob('*.py')), *sorted((root / 'evals/tddbench').glob('*.py'))]
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in files}


def pytest_nodes(command: str, files: dict) -> list[str]:
    if not isinstance(command, str):
        raise ValueError('pytest command must be a string, not a run_cmd object or list')
    argv, reason = _tokenize(command)
    if reason or argv[:3] != ['python', '-m', 'pytest']:
        raise ValueError('benchmark specs must use python -m pytest without a shell')
    nodes = [x for x in argv[3:] if x not in ('-q', '-v', '-vv')]
    options = [x for x in nodes if x.startswith('-')]
    if options:
        raise ValueError('unsupported pytest option ' + repr(options[0]) + '; allowed flags: -q, -v, -vv')
    validate_test_action({'files': files, 'tests': nodes})
    return nodes


def test_patch(directory: str, files: dict) -> str:
    snapshot = verify_workspace(directory)
    links = {item['path'] for item in snapshot['files'] if item.get('kind') == 'symlink'}
    root = pathlib.Path(directory).resolve() / 'source'
    patch = ''
    for name, content in sorted(files.items()):
        if through_link(name, links):
            raise ValueError('test patches cannot replace source symlinks')
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('test patch path escapes public source')
        old = path.read_text(encoding='utf-8') if path.exists() else ''
        preserve_named_tests(old, content, name)
        if old == content:
            continue
        # Normalize the submitted test to a newline-terminated file for portable diffs.
        if not content.endswith('\n'):
            raise ValueError('test files must end in a newline')
        patch += 'diff --git a/' + name + ' b/' + name + '\n'
        if not path.exists():
            patch += 'new file mode 100644\n'
        lines = difflib.unified_diff(old.splitlines(keepends=True), content.splitlines(keepends=True),
                                    fromfile='a/' + name if path.exists() else '/dev/null', tofile='b/' + name)
        patch += ''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n' for line in lines)
    if not patch:
        raise ValueError('proposal has no changed test files')
    return patch


def check_proposal(directory: str, destination: str, proposal: dict, execute) -> dict:
    """Run native contract/ledger/check. ``execute`` shares the arm's test-run budget."""
    method = framework_context()
    if not isinstance(proposal, dict):
        raise ValueError('Athena finish requires a structured proposal')
    if any(not isinstance(proposal.get(k), str) or not proposal[k].strip() for k in ('contract', 'scenarios')):
        raise ValueError('Athena proposal requires contract and executable scenarios')
    files = proposal.get('files')
    reference = validate_reference(directory, proposal.get('reference'))
    if not reference:
        raise ValueError('Athena needs a public model-proposed reference, never a gold baseline')
    contract = parse(proposal['contract'])
    scenarios_text, _ = pin_scenarios(proposal['scenarios'], contract)
    scenarios = parse_scenarios(scenarios_text)
    if not scenarios:
        raise ValueError('Athena proposal has no executable scenarios')
    for scenario in scenarios:
        pytest_nodes(scenario.run_cmd, files)
    patch = test_patch(directory, files)
    out = pathlib.Path(destination).resolve()
    root = pathlib.Path(directory).resolve()
    if out == root or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError('native artifacts must remain separate from public source')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'contract.md').write_text(proposal['contract'], encoding='utf-8')
    (out / 'scenarios.md').write_text(scenarios_text, encoding='utf-8')
    (out / 'proposal.json').write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding='utf-8')

    def executor(command, *, cwd, timeout):
        result = execute({'action': 'run', 'files': files, 'tests': pytest_nodes(command, files)}, reference)
        status = result.get('status')
        code = 0 if status == 'PASS' else 1 if status == 'ASSERTION_FAIL' else 2
        return code, result.get('tail') or result.get('reason') or status

    results = run_specs(scenarios, contract=contract, executor=executor, jobs=1)
    ledger = make_ledger(results, contract=contract, scenario_version=hash_text(scenarios_text))
    report = check.build(lint_issues=lint(contract), coverage=contract_report.coverage(contract, scenarios),
                         ledger_totals=ledger['totals'], todo=contract_report.todo(contract, scenarios, ledger),
                         drift=contract_report.drift(contract, scenarios, ledger), allow_partial=True)
    incomplete = any(r.exit_code not in (0, 1) for r in results)
    method_changed = framework_context() != method
    incomplete = incomplete or method_changed
    result = {'schema': 'athena.tdd_native_check/1', 'passed': report['passed'],
              'state': 'INCOMPLETE' if incomplete else 'PASS' if report['passed'] else 'FAIL', 'check': report,
              'baseline_origin': 'model-proposed-public-reference', 'gold_used': False,
              'scope': 'native contract fast lane; reverse leg intentionally absent',
              'framework_files': method, 'method_changed': method_changed,
              'ledger': ledger, 'patch': patch}
    if method_changed:
        result['passed'] = False
    (out / 'ledger.json').write_text(json.dumps(ledger, indent=2), encoding='utf-8')
    (out / 'check.json').write_text(json.dumps({k: v for k, v in result.items() if k != 'patch'}, indent=2), encoding='utf-8')
    return result
