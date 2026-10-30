"""Opt-in tool collector: a verification result is not validation of user intent.

No Git, shell, implicit tool installation, natural-language formalization or release
decision. Input closure and assumptions are reviewer declarations. Local execution
is not a sandbox. Tool binaries are part of the trusted computing base.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from lib.assurance import read_bound, sha
from lib.contract import lint, parse
from lib.verification import execution_environment

SCHEMA = 'athena.formal_evidence/1'


def classify(engine: str, code: int, output: str) -> str:
    if engine == 'crosshair':
        if code == 0 and re.search(r': info: (Confirmed over all paths|Not confirmed)', output):
            return 'NO_COUNTEREXAMPLE'
        if code == 1 and re.search(r': error: .*when calling ', output):
            return 'COUNTEREXAMPLE'
        return 'UNKNOWN'
    if engine == 'dafny':
        if re.search(r'Prover error:|internal error|Unhandled exception', output, re.IGNORECASE):
            return 'UNKNOWN'
        summaries = re.findall(r'Dafny program verifier finished with (\d+) verified, (\d+) errors?', output)
        if code == 0 and len(summaries) == 1 and int(summaries[0][0]) > 0 and int(summaries[0][1]) == 0:
            return 'VERIFIED_RELATIVE_TO_SPEC'
        # A failed proof is not necessarily a behavioral counterexample.
        return 'UNPROVEN' if summaries and code != 0 else 'UNKNOWN'
    raise ValueError('unsupported formal engine')


def collect(root: str | Path, manifest: str, *, python: str, dafny: str,
            timeout: int = 20) -> dict:
    root = Path(root).resolve()
    raw = read_bound(root, manifest)
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('schema') != SCHEMA:
        raise ValueError('unsupported formal manifest')
    if not 1 <= timeout <= 600:
        raise ValueError('timeout must be 1..600 seconds')
    contract = parse(read_bound(root, data['contract']).decode('utf-8'))
    if lint(contract) or len({c.id for c in contract.clauses}) != len(contract.clauses):
        raise ValueError('invalid formal contract')
    clauses = {c.id: c for c in contract.clauses if c.is_live}
    tasks = data.get('tasks')
    if not isinstance(tasks, list) or not tasks:
        raise ValueError('formal tasks must be a nonempty list')
    seen = set()
    prepared = []
    # Validate every job before running any code.
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError('each formal task must be an object')
        if not isinstance(task.get('id'), str) or not task['id'] or task['id'] in seen:
            raise ValueError('task ids must be unique strings')
        seen.add(task['id'])
        if task['clause'] not in clauses or task['pin'] != clauses[task['clause']].version:
            raise ValueError('unknown or stale clause')
        if task['engine'] not in ('crosshair', 'dafny') or task['subject_kind'] not in ('implementation', 'model'):
            raise ValueError('unknown engine or subject kind')
        if not isinstance(task.get('scope'), str) or not task['scope'].strip():
            raise ValueError('explicit scope required')
        if not isinstance(task.get('assumptions'), list) or not task['assumptions'] or not all(isinstance(s, str) and s.strip() for s in task['assumptions']):
            raise ValueError('explicit nonempty assumptions required')
        inputs = task['inputs']
        if not isinstance(inputs, dict) or not {data['contract'], task['target']}.issubset(inputs):
            raise ValueError('contract and target must be fingerprinted')
        if not isinstance(task['target'], str) or not task['target'].endswith('.py' if task['engine'] == 'crosshair' else '.dfy'):
            raise ValueError('tool target must have the expected source extension')
        for name, digest in inputs.items():
            if sha(read_bound(root, name)) != digest:
                raise ValueError('stale input: ' + name)
        prepared.append(task)
    results = []
    for task in prepared:
        engine = task['engine']
        argv = ([python, '-m', 'crosshair', 'check', str(root / task['target']), '--report_all', '--per_condition_timeout', '3']
                if engine == 'crosshair' else [dafny, 'verify', str(root / task['target']), '--verification-time-limit', str(timeout)])
        started = time.monotonic()
        env = execution_environment()
        overrides = {'DOTNET_SYSTEM_GLOBALIZATION_INVARIANT': '1'} if engine == 'dafny' else {}
        env.update(overrides)
        binary = shutil.which(argv[0])
        tool_binary = {'path': binary, 'sha256': sha(Path(binary).read_bytes()) if binary else None}
        # Earlier jobs may alter a shared input. Initial whole-plan validation is
        # not a substitute for validating the bytes immediately before this job.
        stale_before = []
        for name, digest in task['inputs'].items():
            try:
                if sha(read_bound(root, name)) != digest:
                    stale_before.append(name)
            except (OSError, ValueError):
                stale_before.append(name)
        try:
            stale_manifest = sha(read_bound(root, manifest)) != sha(raw)
        except (OSError, ValueError):
            stale_manifest = True
        try:
            if stale_before or stale_manifest:
                code, stdout, stderr = None, '', ''
                state, reason = 'UNKNOWN', 'inputs or manifest changed before execution; tool not run'
            else:
                proc = subprocess.run(argv, cwd=root, capture_output=True, text=True, errors='replace',
                                      timeout=timeout, shell=False, env=env)
                code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
                state = classify(engine, code, stdout + '\n' + stderr)
                reason = 'tool output interpretation'
        except subprocess.TimeoutExpired:
            code, stdout, stderr, state, reason = None, '', '', 'UNKNOWN', 'process timeout'
        except OSError as exc:
            code, stdout, stderr, state, reason = None, '', str(exc), 'UNKNOWN', 'tool unavailable'
        changed = []
        for name, digest in task['inputs'].items():
            try:
                if sha(read_bound(root, name)) != digest:
                    changed.append(name)
            except (OSError, ValueError):
                changed.append(name)
        try:
            manifest_changed = sha(read_bound(root, manifest)) != sha(raw)
        except (OSError, ValueError):
            manifest_changed = True
        if (changed or manifest_changed) and not (stale_before or stale_manifest):
            state, reason = 'UNKNOWN', 'inputs or manifest changed during execution'
        results.append({**task, 'state': state, 'reason': reason, 'changed_inputs': changed,
                        'argv': argv, 'exit_code': code, 'stdout': stdout, 'stderr': stderr,
                        'environment_overrides': overrides, 'tool_binary': tool_binary,
                        'elapsed_seconds': round(time.monotonic() - started, 3)})
    return {'schema': SCHEMA, 'manifest_sha256': sha(raw), 'results': results,
            'limitations': ['Input closure and assumptions are declared, not inferred or proved complete.',
                            'Formalization fidelity to user intent requires separate review.',
                            'Model verification does not prove a separate deployed implementation.',
                            'Tool output is not an independently authenticated attestation.',
                            'No assurance implementation state or release decision is promoted.']}
