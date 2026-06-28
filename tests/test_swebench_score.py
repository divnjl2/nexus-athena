"""Offline, deterministic tests for the SWE-bench-Lite scoring core.

Runs against the committed fixtures (no network, no LLM, no claude -p). Covers the gold
patch parser, FAIL_TO_PASS normalisation, and the secondary file_recall signal.
"""
from __future__ import annotations

from evals.swebench.loader import load_fixtures
from evals.swebench.score import fail_to_pass, file_recall, gold_patch_targets


def _astropy():
    return next(i for i in load_fixtures() if i["instance_id"] == "astropy__astropy-12907")


def test_fixtures_present():
    insts = load_fixtures()
    assert len(insts) >= 2
    assert all("problem_statement" in i and "patch" in i for i in insts)


def test_gold_patch_targets_files_and_symbols():
    t = gold_patch_targets(_astropy()["patch"])
    assert t["files"] == ["astropy/modeling/separable.py"]
    assert "_cstack" in t["symbols"]          # hunk context `@@ ... def _cstack(left, right):`
    assert t["test_files"] == []               # gold patch (not test_patch) touches no tests


def test_test_files_split_out():
    # a synthetic diff touching both a source and a test file
    patch = (
        "diff --git a/pkg/core.py b/pkg/core.py\n@@ -1,1 +1,1 @@ def f():\n-x\n+y\n"
        "diff --git a/pkg/tests/test_core.py b/pkg/tests/test_core.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    )
    t = gold_patch_targets(patch)
    assert t["files"] == ["pkg/core.py"]
    assert t["test_files"] == ["pkg/tests/test_core.py"]


def test_fail_to_pass_normalises_json_string():
    f2p = fail_to_pass(_astropy())
    assert isinstance(f2p, list) and len(f2p) == 2
    assert all("::" in t for t in f2p)         # pytest node ids


def test_file_recall_basename_match():
    inst = _astropy()
    # a plan that named the right file by basename scores full recall
    hit = file_recall({"separable.py", "unrelated.py"}, inst)
    assert hit["recall"] == 1.0
    assert "separable.py" in hit["matched"]
    # a plan that named nothing relevant scores zero
    miss = file_recall({"wrong.py"}, inst)
    assert miss["recall"] == 0.0


def test_file_recall_empty_plan():
    assert file_recall(set(), _astropy())["recall"] == 0.0
