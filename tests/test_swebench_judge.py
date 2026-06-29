"""Offline tests for the behaviour_coverage judge parsing.

Locks the counting fix: the judge returns the SHORT test-function name while FAIL_TO_PASS
holds the full pytest node-id; substring-matching the two silently zeroed real coverage
(a 0.94 result read as 0.12). We trust the judge's covered==true verdict count instead.
"""
from __future__ import annotations

from evals.swebench.judge import _parse_judgement


def test_short_name_verdict_counts_despite_full_node_id():
    f2p = ["astropy/wcs/tests/test_wcs.py::test_zero_size_input"]
    judge_out = '{"per_test":[{"test":"test_zero_size_input","covered":true,"why":"S1.1 covers it"}]}'
    v = _parse_judgement(judge_out, f2p)
    assert v["covered"] == 1 and v["total"] == 1 and v["ratio"] == 1.0


def test_partial_coverage():
    f2p = ["a.py::t1", "a.py::t2", "a.py::t3", "a.py::t4"]
    out = ('{"per_test":[{"test":"t1","covered":true},{"test":"t2","covered":false},'
           '{"test":"t3","covered":true},{"test":"t4","covered":false}]}')
    v = _parse_judgement(out, f2p)
    assert v["covered"] == 2 and v["total"] == 4 and v["ratio"] == 0.5


def test_covered_capped_at_total():
    # judge may return more rows than there are tests — never exceed 1.0
    f2p = ["a.py::t1"]
    out = '{"per_test":[{"test":"t1","covered":true},{"test":"t1-dup","covered":true}]}'
    v = _parse_judgement(out, f2p)
    assert v["covered"] == 1 and v["ratio"] == 1.0


def test_garbage_judge_output_is_zero_not_crash():
    v = _parse_judgement("the model rambled with no json", ["a.py::t1"])
    assert v["covered"] == 0 and v["ratio"] == 0.0


def test_empty_fail_to_pass_is_zero_ratio():
    v = _parse_judgement('{"per_test":[]}', [])
    assert v["total"] == 0 and v["ratio"] == 0.0
