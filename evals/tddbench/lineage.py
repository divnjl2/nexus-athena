"""Durable, single-coordinator budgets shared by every revision of one case.

Units are charged outer model requests and test-tool attempts, not wire requests,
server spending or proof of successful execution. Errors never refund a charge.
Hashes expose changes against a trusted head; they do not authenticate the owner.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import copy
import hashlib
import json
import os
import pathlib
import re
import subprocess

RESOURCES = ('model_calls', 'test_runs')
USAGE_FIELDS = ('input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_output_tokens')
OUTCOMES = {'COMPLETED', 'PASS', 'ASSERTION_FAIL', 'TOOL_ERROR', 'TIMEOUT', 'ERROR',
            'INTERRUPTED', 'UNKNOWN', 'BUDGET_EXHAUSTED'}


class BudgetExhausted(RuntimeError):
    pass


class JournalCorrupt(RuntimeError):
    pass


class JournalBusy(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    model_calls: int = 24
    test_runs: int = 36

    def validate(self):
        if any(type(n) is not int or n <= 0 for n in asdict(self).values()):
            raise ValueError('lineage limits must be positive integers')


def audit_cost(bound_commands: dict[str, int], *, valid: int = 2, violations: int = 1) -> int:
    """Baseline and each control run every bound command; activation runs twice."""
    if (not isinstance(bound_commands, dict) or not bound_commands
            or any(not isinstance(k, str) or not k or type(n) is not int or n <= 0
                   for k, n in bound_commands.items())
            or type(valid) is not int or valid < 1 or type(violations) is not int or violations < 1):
        raise ValueError('audit planning requires live bindings and positive control counts')
    return sum(n * (1 + valid + violations) + 2 * violations for n in bound_commands.values())


def plan_remaining(bound_commands: dict[str, int], *, calls: int, tests: int,
                   attempts: int = 2, repair_calls: int = 4) -> dict:
    """Plan after generation: current review/audit, then reserved repair cycles.

    Future costs assume these bindings are retained; recompute if a revision adds
    commands. A forecast is neither admission nor permission to drop obligations.
    """
    cost = audit_cost(bound_commands)
    if (any(type(n) is not int or n < 0 for n in (calls, tests))
            or type(attempts) is not int or attempts < 1
            or type(repair_calls) is not int or repair_calls < 1):
        raise ValueError('invalid cycle planning budget')
    future = attempts - 1
    required = {'model_calls': 1 + future * (repair_calls + 1),
                'test_runs': cost + future * (sum(bound_commands.values()) + cost)}
    shortfall = {'model_calls': max(0, required['model_calls'] - calls),
                 'test_runs': max(0, required['test_runs'] - tests)}
    return {'feasible': not any(shortfall.values()), 'required': required, 'shortfall': shortfall,
            'current_audit_runs': cost, 'future_attempts': future,
            'scope': 'full declared bindings; future growth requires replanning'}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise ValueError('expected a SHA-256 digest')
    return value


def _phase(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}', value):
        raise ValueError('invalid phase identity')
    return value


def _units(value):
    if (not isinstance(value, dict) or set(value) != set(RESOURCES)
            or any(type(n) is not int or n < 0 for n in value.values())):
        raise ValueError('invalid resource units')
    return value


def _usage(value):
    if not isinstance(value, dict):
        return None
    result = {}
    for key in USAGE_FIELDS:
        if key in value:
            if type(value[key]) is not int or value[key] < 0:
                return None
            result[key] = value[key]
    return result or None


class Journal:
    """Append-only events, OS file locking and pre-side-effect admission.

    Reopen explicitly after another writer advances the journal. A partial write
    fails closed. Crash-pending tickets remain charged. Trusted consumers should
    pass expected_head when checking a previously frozen receipt.
    """
    def __init__(self, directory, limits, binding):
        limits.validate()
        self.directory = pathlib.Path(directory).resolve()
        self.limits = asdict(limits)
        self.binding = _digest(binding)
        self.head = None

    @classmethod
    def create(cls, directory, limits: Limits, binding: str):
        instance = cls(directory, limits, binding)
        instance.directory.mkdir(parents=True, exist_ok=False)
        with instance._locked():
            instance.head = instance._write(0, '0' * 64, {
                'kind': 'open', 'schema': 'athena.lineage_budget/1',
                'limits': instance.limits, 'binding': instance.binding})
        return instance

    @classmethod
    def open(cls, directory, limits: Limits, binding: str, *, expected_head=None):
        instance = cls(directory, limits, binding)
        if not instance.directory.is_dir():
            raise JournalCorrupt('lineage directory is missing')
        with instance._locked():
            _, head, _ = instance._read()
            if expected_head is not None and head != _digest(expected_head):
                raise JournalCorrupt('journal differs from the trusted receipt head')
            instance.head = head
        return instance

    @contextmanager
    def _locked(self):
        with (self.directory / '.lock').open('a+b') as handle:
            if handle.seek(0, 2) == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise JournalBusy('another coordinator owns the journal lock') from None
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _write(self, sequence, previous, event):
        body = {'sequence': sequence, 'previous': previous, 'event': event}
        head = hashlib.sha256(_canonical(body)).hexdigest()
        with (self.directory / f'{sequence:09d}.json').open('xb') as handle:
            handle.write(_canonical({**body, 'sha256': head})); handle.flush(); os.fsync(handle.fileno())
        return head

    def _read(self):
        files = sorted(self.directory.glob('*.json'))
        if not files:
            raise JournalCorrupt('journal header is missing')
        state = {'spent': dict.fromkeys(RESOURCES, 0), 'reservations': {}, 'tickets': {}, 'denied': 0}
        previous = '0' * 64
        try:
            for index, path in enumerate(files):
                if path.name != f'{index:09d}.json':
                    raise ValueError('journal sequence is not contiguous')
                row = json.loads(path.read_bytes())
                if set(row) != {'sequence', 'previous', 'event', 'sha256'}:
                    raise ValueError('invalid journal envelope')
                body = {k: row[k] for k in ('sequence', 'previous', 'event')}
                if (type(row['sequence']) is not int or row['sequence'] != index
                        or row['previous'] != previous or row['sha256'] != hashlib.sha256(_canonical(body)).hexdigest()):
                    raise ValueError('journal fingerprint or sequence changed')
                event = row['event']
                if index == 0:
                    if event != {'kind': 'open', 'schema': 'athena.lineage_budget/1',
                                 'limits': self.limits, 'binding': self.binding}:
                        raise ValueError('journal binding or limits differ')
                else:
                    self._apply(state, event, index)
                previous = row['sha256']
        except (ValueError, KeyError, TypeError, OSError, BudgetExhausted) as error:
            raise JournalCorrupt('invalid journal evidence: ' + type(error).__name__) from error
        if self.head is not None and self.head != previous:
            raise JournalBusy('journal advanced or changed; reopen against trusted evidence')
        return state, previous, len(files)

    def _apply(self, state, event, sequence):
        kind = event['kind']
        if kind in ('reserve', 'release', 'transfer', 'charge', 'denied'):
            phase = _phase(event['phase'])
        if kind == 'reserve':
            units = _units(event['units'])
            for resource in RESOURCES:
                held = sum(v[resource] for v in state['reservations'].values())
                if state['spent'][resource] + held + units[resource] > self.limits[resource]:
                    raise BudgetExhausted('cannot reserve required future work')
            held = state['reservations'].setdefault(phase, dict.fromkeys(RESOURCES, 0))
            for resource in RESOURCES:
                held[resource] += units[resource]
        elif kind in ('release', 'transfer'):
            if any(t['phase'] == phase and t['outcome'] is None for t in state['tickets'].values()):
                raise ValueError('cannot release or transfer a phase with pending work')
            held = state['reservations'][phase]
            if kind == 'release':
                _digest(event['evidence'])
                del state['reservations'][phase]
            else:
                target = _phase(event['target']); units = _units(event['units'])
                if target == phase or any(units[r] > held[r] for r in RESOURCES):
                    raise ValueError('invalid reservation transfer')
                destination = state['reservations'].setdefault(target, dict.fromkeys(RESOURCES, 0))
                for resource in RESOURCES:
                    held[resource] -= units[resource]; destination[resource] += units[resource]
        elif kind in ('charge', 'denied'):
            resource = event['resource']; _digest(event['reference'])
            if resource not in RESOURCES:
                raise ValueError('unknown resource')
            if kind == 'denied':
                state['denied'] += 1
                return
            protected = sum(v[resource] for owner, v in state['reservations'].items() if owner != phase)
            if state['spent'][resource] + protected >= self.limits[resource]:
                raise BudgetExhausted('remaining budget is exhausted or reserved')
            state['spent'][resource] += 1
            if phase in state['reservations'] and state['reservations'][phase][resource]:
                state['reservations'][phase][resource] -= 1
            state['tickets'][sequence] = {'phase': phase, 'resource': resource, 'outcome': None, 'usage': None}
        elif kind == 'finish':
            ticket = event['ticket']
            if type(ticket) is not int or ticket not in state['tickets']:
                raise ValueError('unknown charge ticket')
            charged = state['tickets'][ticket]
            if charged['outcome'] is not None or event['outcome'] not in OUTCOMES:
                raise ValueError('ticket already settled or invalid outcome')
            if event.get('error_type') and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,95}', event['error_type']):
                raise ValueError('invalid bounded error type')
            charged.update(outcome=event['outcome'], usage=_usage(event.get('usage')))
        else:
            raise ValueError('unknown journal event')

    def _append(self, event):
        with self._locked():
            state, previous, sequence = self._read()
            try:
                self._apply(copy.deepcopy(state), event, sequence)
            except BudgetExhausted:
                if event['kind'] == 'charge':
                    self.head = self._write(sequence, previous, {**event, 'kind': 'denied'})
                raise
            self.head = self._write(sequence, previous, event)
            return sequence

    def reserve(self, phase, *, model_calls=0, test_runs=0):
        return self._append({'kind': 'reserve', 'phase': phase,
                             'units': {'model_calls': model_calls, 'test_runs': test_runs}})

    def transfer(self, phase, target, *, model_calls=0, test_runs=0):
        return self._append({'kind': 'transfer', 'phase': phase, 'target': target,
                             'units': {'model_calls': model_calls, 'test_runs': test_runs}})

    def release(self, phase, *, evidence):
        return self._append({'kind': 'release', 'phase': phase, 'evidence': evidence})

    def charge(self, resource, phase, *, reference):
        return self._append({'kind': 'charge', 'phase': phase, 'resource': resource, 'reference': reference})

    def finish(self, ticket, outcome, *, usage=None, error_type=None):
        return self._append({'kind': 'finish', 'ticket': ticket, 'outcome': outcome,
                             'usage': _usage(usage), 'error_type': error_type})

    def invoke(self, resource, phase, *, reference, operation, classify=None):
        ticket = self.charge(resource, phase, reference=reference)
        try:
            result = operation()
            outcome = classify(result) if classify else ('COMPLETED' if resource == 'model_calls' else result['status'])
            usage = result.get('usage') if resource == 'model_calls' and isinstance(result, dict) else None
        except BaseException as error:
            outcome = ('TIMEOUT' if isinstance(error, (TimeoutError, subprocess.TimeoutExpired)) else
                       'INTERRUPTED' if not isinstance(error, Exception) else 'ERROR')
            self.finish(ticket, outcome, error_type=type(error).__name__)
            raise
        self.finish(ticket, outcome, usage=usage)
        return result

    def snapshot(self):
        with self._locked():
            state, head, _ = self._read()
        models = [t for t in state['tickets'].values() if t['resource'] == 'model_calls']
        observed, missing = {}, {}
        for field in USAGE_FIELDS:
            values = [t['usage'][field] for t in models if t['usage'] is not None and field in t['usage']]
            observed[field] = sum(values) if values else None
            missing[field] = len(models) - len(values)
        return {'head': head, 'limits': self.limits, 'spent': state['spent'],
                'remaining': {r: self.limits[r] - state['spent'][r] for r in RESOURCES},
                'reservations': state['reservations'], 'denied': state['denied'],
                'pending': [i for i, t in state['tickets'].items() if t['outcome'] is None],
                'observed_usage': observed, 'missing_usage_fields': missing,
                'scope': 'charged outer requests and test-tool attempts; no refund or server spending cap'}
