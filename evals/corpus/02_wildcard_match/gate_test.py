"""Authoritative ground-truth gate for wildcard_match — LLM-INDEPENDENT.

The planner never sees this. Code built to the plan is run against it. Test names encode
the requirement they prove (R1..R5).
Run: python -m pytest evals/corpus/02_wildcard_match/gate_test.py -q
"""
import importlib.util
import os

_HERE = os.path.dirname(__file__)


def _load():
    path = os.path.join(_HERE, "wildcard.py")
    spec = importlib.util.spec_from_file_location("wildcard_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.wildcard_match


def test_R1_star_matches_any_including_empty():
    f = _load()
    assert f("a*", "a") is True          # * = empty
    assert f("a*", "abc") is True         # * = "bc"
    assert f("*", "anything") is True
    assert f("*", "") is True


def test_R2_question_matches_exactly_one():
    f = _load()
    assert f("a?c", "abc") is True
    assert f("a?c", "ac") is False        # ? needs exactly one
    assert f("a?c", "abbc") is False


def test_R3_literals_match_exactly():
    f = _load()
    assert f("abc", "abc") is True
    assert f("abc", "abd") is False


def test_R4_anchored_full_match_not_substring():
    f = _load()
    assert f("bc", "abcd") is False       # not a substring match
    assert f("a*d", "abcd") is True


def test_R5_empty_pattern_only_empty_text():
    f = _load()
    assert f("", "") is True
    assert f("", "x") is False
