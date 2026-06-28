"""Authoritative ground-truth gate for eval_rpn — LLM-INDEPENDENT.

This is the answer key. The planner never sees it. Code built to the LLM's plan is
run against THIS, so the eval reflects real requirement satisfaction, not the LLM's
self-graded scenarios. Each test name encodes the requirement it proves (R1..R5).

Run: python -m pytest evals/corpus/01_rpn/gate_test.py -q
(rpn.py must be importable from the same directory — the harness writes it there.)
"""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(__file__)


def _load():
    path = os.path.join(_HERE, "rpn.py")
    spec = importlib.util.spec_from_file_location("rpn_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.eval_rpn


def test_R1_four_operators():
    f = _load()
    assert f("3 4 +") == 7
    assert f("10 2 -") == 8
    assert f("5 3 *") == 15
    assert f("8 2 /") == 4


def test_R2_float_division():
    f = _load()
    assert f("5 2 /") == 2.5


def test_R3_division_by_zero_raises():
    f = _load()
    with pytest.raises(Exception):
        f("1 0 /")


def test_R4_malformed_raises():
    f = _load()
    with pytest.raises(Exception):
        f("3 +")


def test_R5_chained_expression():
    f = _load()
    assert f("2 3 + 4 *") == 20
