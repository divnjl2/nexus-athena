"""Lifecycle checks of evidence accounting, not independent semantic certification.

The freshness oracle uses event generations, not the implementation's hashes or
current flags. Every edit writes a unique generation, so restoring identical
bytes is deliberately outside this model's declared scope.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test
import pytest

from lib import assurance
from lib.contract import parse


class EvidenceLifecycle(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.directory = tempfile.TemporaryDirectory(prefix='athena-evidence-lifecycle-')
        self.root = Path(self.directory.name)
        self.generations = {'contract.md': 0, 'code.py': 0, 'checks.py': 0}
        self.artifact_generations = {}
        self.records = []
        self.observations = []
        for name in self.generations:
            self.write_input(name)

    def write_input(self, name):
        generation = self.generations[name]
        if name == 'contract.md':
            content = ('# Lifecycle contract\n\n'
                       '- **C-1.1** — WHEN a value is supplied THE SYSTEM SHALL double it.\n'
                       '- **C-1.2** — WHEN an unobserved behavior occurs THE SYSTEM SHALL retain an unknown result.\n'
                       f'\nGeneration note: {generation}\n')
        elif name == 'code.py':
            content = f'def twice(x): return 2*x\n# generation {generation}\n'
        else:
            content = f'assert twice(3) == 6\n# generation {generation}\n'
        (self.root / name).write_text(content, encoding='utf-8')

    def observe(self, kind, outcome='PASS', *, activated=True):
        ident = str(len(self.records))
        artifact = f'observation-{ident}.json'
        self.artifact_generations[artifact] = 0
        # Declared evidence is intentionally labeled; this suite tests accounting.
        (self.root / artifact).write_text(json.dumps({'kind': kind, 'outcome': outcome, 'generation': 0}), encoding='utf-8')
        record = {'id': ident, 'clause': 'C-1.1',
                  'pin': parse((self.root / 'contract.md').read_text(encoding='utf-8')).by_id('C-1.1').version,
                  'kind': kind, 'outcome': outcome, 'scope': 'declared integer example 3',
                  'producer': 'state-machine accounting fixture',
                  'basis': 'declared observation; semantic truth is outside this test',
                  'inputs': {name: assurance.sha((self.root / name).read_bytes()) for name in self.generations},
                  'checks': ['checks.py'], 'artifact': artifact,
                  'artifact_sha256': assurance.sha((self.root / artifact).read_bytes()),
                  'activated': activated}
        self.records.append(record)
        self.observations.append({'id': ident, 'kind': kind, 'outcome': outcome,
                                  'input_generations': dict(self.generations),
                                  'artifact': artifact, 'artifact_generation': 0,
                                  'activated': activated})

    @rule(kind=st.sampled_from(['execution', 'valid_alternative', 'violation', 'code_review', 'spec_review']),
          outcome=st.sampled_from(['PASS', 'FAIL', 'UNKNOWN']), activated=st.booleans())
    def add_observation(self, kind, outcome, activated):
        self.observe(kind, outcome, activated=activated)

    @rule()
    def rerun_passing_bundle(self):
        for kind in ('execution', 'valid_alternative', 'violation'):
            self.observe(kind)

    @rule(name=st.sampled_from(['contract.md', 'code.py', 'checks.py']))
    def change_input(self, name):
        self.generations[name] += 1
        self.write_input(name)

    @rule()
    def change_observation_artifact(self):
        if self.records:
            artifact = self.records[-1]['artifact']
            self.artifact_generations[artifact] += 1
            (self.root / artifact).write_text(json.dumps({'tampered_generation': self.artifact_generations[artifact]}), encoding='utf-8')

    def report(self):
        manifest = {'schema': assurance.SCHEMA, 'contract': 'contract.md', 'implementation': ['code.py'], 'evidence': self.records}
        (self.root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return assurance.assess(self.root, 'manifest.json')

    def current_observations(self):
        return [e for e in self.observations
                if e['input_generations'] == self.generations
                and e['artifact_generation'] == self.artifact_generations[e['artifact']]
                and (e['kind'] != 'violation' or e['activated'])]

    @invariant()
    def accounting_matches_event_history(self):
        report = self.report()
        assert report['denominator'] == 2
        row, unobserved = report['requirements']
        assert unobserved['implementation'] == 'UNKNOWN'
        current = self.current_observations()
        assert {e['id'] for e in row['evidence'] if e['current']} == {e['id'] for e in current}, 'freshness disagrees with event history'
        # Independent four-state truth table, applied only to direct observations.
        truth = {frozenset(): 'UNKNOWN', frozenset({'PASS'}): 'SUPPORTED',
                 frozenset({'FAIL'}): 'CONTRADICTED', frozenset({'PASS', 'FAIL'}): 'CONFLICT'}
        for kind, dimension in (('execution', 'execution'), ('code_review', 'code_correspondence'), ('spec_review', 'specification')):
            seen = frozenset(e['outcome'] for e in current if e['kind'] == kind and e['outcome'] != 'UNKNOWN')
            assert row[dimension] == truth[seen]
        if not current:
            assert all(row[d] == 'UNKNOWN' for d in ('execution', 'implementation', 'check_adequacy', 'specification', 'code_correspondence'))
        # A green implementation requires real current accounting support, never a
        # historical green from another source generation or edited artifact.
        if row['implementation'] == 'SUPPORTED':
            for kind in ('execution', 'valid_alternative', 'violation'):
                assert any(e['kind'] == kind and e['outcome'] == 'PASS' for e in current)
            assert not any(e['outcome'] == 'FAIL' and e['kind'] in ('execution', 'valid_alternative', 'violation', 'spec_review') for e in current)

    def teardown(self):
        self.directory.cleanup()


def test_generated_evidence_lifecycle_preserves_freshness():
    """C-1.7 — generated histories cannot reuse changed input or artifact observations."""
    run_state_machine_as_test(EvidenceLifecycle, settings=settings(
        max_examples=45, stateful_step_count=24, deadline=None, derandomize=True, database=None))


def test_lifecycle_oracle_detects_seeded_stale_read(monkeypatch):
    """C-1.7 — a stale-read implementation must fail the same lifecycle invariant."""
    machine = EvidenceLifecycle()
    try:
        machine.rerun_passing_bundle()
        machine.accounting_matches_event_history()
        frozen = (machine.root / 'code.py').read_bytes()
        original_read = assurance.read_bound
        def stale_read(root, name):
            return frozen if name == 'code.py' else original_read(root, name)
        monkeypatch.setattr(assurance, 'read_bound', stale_read)
        machine.change_input('code.py')
        assert machine.report()['requirements'][0]['implementation'] == 'SUPPORTED'
        with pytest.raises(AssertionError, match='freshness disagrees'):
            machine.accounting_matches_event_history()
    finally:
        machine.teardown()


def test_lifecycle_rerun_recovers_and_counterevidence_stays_visible():
    """C-1.7 — only fresh reruns restore support and conflicting observations stay visible."""
    machine = EvidenceLifecycle()
    try:
        machine.rerun_passing_bundle()
        assert machine.report()['requirements'][0]['implementation'] == 'SUPPORTED'
        machine.change_input('checks.py')
        assert machine.report()['requirements'][0]['implementation'] == 'UNKNOWN'
        machine.rerun_passing_bundle()
        assert machine.report()['requirements'][0]['implementation'] == 'SUPPORTED'
        machine.observe('execution', 'FAIL')
        row = machine.report()['requirements'][0]
        assert row['execution'] == row['implementation'] == 'CONFLICT'
        machine.change_input('code.py')
        assert machine.report()['requirements'][0]['implementation'] == 'UNKNOWN'
        machine.accounting_matches_event_history()
    finally:
        machine.teardown()
