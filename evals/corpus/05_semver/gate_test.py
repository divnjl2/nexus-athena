"""Authoritative ground-truth gate for compare_semver — LLM-INDEPENDENT.
Run: python -m pytest evals/corpus/05_semver/gate_test.py -q
"""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(__file__)


def _load():
    path = os.path.join(_HERE, "semver.py")
    spec = importlib.util.spec_from_file_location("semver_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.compare_semver


def test_R1_field_precedence():
    f = _load()
    assert f("2.0.0", "1.9.9") == 1
    assert f("1.2.0", "1.1.9") == 1
    assert f("1.1.2", "1.1.1") == 1


def test_R2_returns_tri_state():
    f = _load()
    assert f("1.0.0", "1.0.0") == 0
    assert f("1.0.0", "2.0.0") == -1
    assert f("2.0.0", "1.0.0") == 1


def test_R3_prerelease_lower():
    f = _load()
    assert f("1.0.0-rc1", "1.0.0") == -1
    assert f("1.0.0", "1.0.0-rc1") == 1


def test_R4_numeric_not_lexical():
    f = _load()
    assert f("1.10.0", "1.9.0") == 1     # 10 > 9 numerically
    assert f("1.0.10", "1.0.9") == 1


def test_R5_malformed_raises():
    f = _load()
    with pytest.raises(Exception):
        f("1.0", "1.0.0")                # missing patch
