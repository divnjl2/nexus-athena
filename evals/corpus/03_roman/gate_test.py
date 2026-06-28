"""Authoritative ground-truth gate for roman_to_int — LLM-INDEPENDENT.
Run: python -m pytest evals/corpus/03_roman/gate_test.py -q
"""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(__file__)


def _load():
    path = os.path.join(_HERE, "roman.py")
    spec = importlib.util.spec_from_file_location("roman_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.roman_to_int


def test_R1_basic_symbols():
    f = _load()
    assert f("I") == 1
    assert f("V") == 5
    assert f("X") == 10
    assert f("M") == 1000


def test_R2_subtractive():
    f = _load()
    assert f("IV") == 4
    assert f("IX") == 9
    assert f("XL") == 40
    assert f("CM") == 900
    assert f("MCMXCIV") == 1994


def test_R3_additive():
    f = _load()
    assert f("III") == 3
    assert f("XXVII") == 27
    assert f("MMXXIII") == 2023


def test_R4_invalid_char_raises():
    f = _load()
    with pytest.raises(Exception):
        f("ABC")


def test_R5_empty_raises():
    f = _load()
    with pytest.raises(Exception):
        f("")
