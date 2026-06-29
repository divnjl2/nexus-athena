"""Offline tests for the implementation-parity proxy scorer (no repo, no agent)."""
from __future__ import annotations

import json
import pathlib

from evals.swebench.parity import hunk_ranges, proxy_score

FIX = pathlib.Path(__file__).resolve().parents[1] / "evals" / "swebench" / "fixtures"


def _gold():
    return json.load(open(FIX / "astropy__astropy-12907.json", encoding="utf-8"))["patch"]


def test_hunk_ranges_parses_old_side():
    patch = ("diff --git a/pkg/m.py b/pkg/m.py\n--- a/pkg/m.py\n+++ b/pkg/m.py\n"
             "@@ -10,3 +10,4 @@ def f():\n-x\n+y\n+z\n")
    hr = hunk_ranges(patch)
    assert hr == {"pkg/m.py": [(10, 3)]}


def test_perfect_patch_scores_one():
    # the gold patch scored against itself = right file AND overlapping hunks
    gold = _gold()
    v = proxy_score(gold, gold)
    assert v["file_touch"] and v["hunk_overlap"] and v["score"] == 1.0


def test_right_file_wrong_place_scores_half():
    gold = _gold()  # touches astropy/modeling/separable.py around line 242
    candidate = ("diff --git a/astropy/modeling/separable.py b/astropy/modeling/separable.py\n"
                 "--- a/astropy/modeling/separable.py\n+++ b/astropy/modeling/separable.py\n"
                 "@@ -900,2 +900,2 @@ def unrelated():\n-a\n+b\n")
    v = proxy_score(candidate, gold)
    assert v["file_touch"] is True and v["hunk_overlap"] is False and v["score"] == 0.5


def test_wrong_file_scores_zero():
    gold = _gold()
    candidate = ("diff --git a/setup.py b/setup.py\n--- a/setup.py\n+++ b/setup.py\n"
                 "@@ -1,1 +1,1 @@\n-x\n+y\n")
    v = proxy_score(candidate, gold)
    assert v["file_touch"] is False and v["score"] == 0.0


def test_empty_candidate_scores_zero():
    v = proxy_score("", _gold())
    assert v["score"] == 0.0
