"""Typed negative/positive activation evidence for the engineering pilot."""
import pathlib
import runpy

import pytest

CLAUSES = [f'C-1.{i}' for i in range(1, 8)] + ['C-2.1', 'C-2.3', 'C-2.4', 'C-2.6', 'C-2.8']


@pytest.mark.parametrize('clause', CLAUSES)
def test_violation_active(clause):
    activated = runpy.run_path(str(pathlib.Path(__file__).with_name('activate.py')))['activated']
    assert activated(clause), 'violation is not active on this implementation'
