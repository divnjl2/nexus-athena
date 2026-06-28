"""Authoritative ground-truth gate for is_balanced — LLM-INDEPENDENT.
Run: python -m pytest evals/corpus/04_balanced/gate_test.py -q
"""
import importlib.util
import os

_HERE = os.path.dirname(__file__)


def _load():
    path = os.path.join(_HERE, "balanced.py")
    spec = importlib.util.spec_from_file_location("balanced_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.is_balanced


def test_R1_matched_same_type():
    f = _load()
    assert f("()") is True
    assert f("(]") is False
    assert f("(") is False


def test_R2_proper_nesting():
    f = _load()
    assert f("([])") is True
    assert f("([)]") is False     # interleaved, wrong nesting
    assert f("{[()]}") is True


def test_R3_all_three_pairs():
    f = _load()
    assert f("()[]{}") is True
    assert f("([{}])") is True


def test_R4_ignores_non_brackets():
    f = _load()
    assert f("a(b)c") is True
    assert f("a(b]c") is False


def test_R5_empty_is_balanced():
    f = _load()
    assert f("") is True
