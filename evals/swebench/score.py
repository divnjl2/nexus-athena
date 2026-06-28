"""SWE-bench-Lite scoring primitives for the intent->plan eval.

SWE-bench is a code-patch benchmark; we repurpose it for PLAN quality. The GitHub
`problem_statement` is the NL intent fed to the Athena frame; the gold `patch` and the
`FAIL_TO_PASS` tests are the answer key. Two signals:

  * behaviour coverage (PRIMARY) — does the plan's scenarios/edge-cases cover what the
    FAIL_TO_PASS tests assert? This needs an LLM judge (see run.py) and is the fair metric,
    since the frame sees only the issue text, not the repo.
  * gold-patch targets (SECONDARY) — the files/symbols the gold patch changed. Only a fair
    recall signal when the frame is given repo context; otherwise informational.

This module holds the DETERMINISTIC, unit-testable extractors only. No LLM, no network.
"""
from __future__ import annotations

import re

_DIFF_FILE_RE = re.compile(r"^diff --git a/(?P<a>.+?) b/(?P<b>.+?)\s*$")
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@\s*(?P<ctx>.*)$")
# python def/class name in the hunk context (the `@@ ... def foo(` trailer)
_SYMBOL_RE = re.compile(r"\b(?:def|class)\s+(?P<name>[A-Za-z_]\w*)")


def gold_patch_targets(patch: str) -> dict:
    """Parse a unified diff -> {files: sorted[str], symbols: sorted[str]}.

    files: every path touched (b-side, test files excluded into `test_files`).
    symbols: function/class names seen in hunk context lines (best-effort).
    """
    files: set[str] = set()
    test_files: set[str] = set()
    symbols: set[str] = set()
    for line in patch.splitlines():
        m = _DIFF_FILE_RE.match(line)
        if m:
            path = m.group("b")
            (test_files if _is_test_path(path) else files).add(path)
            continue
        h = _HUNK_RE.match(line)
        if h:
            sm = _SYMBOL_RE.search(h.group("ctx"))
            if sm:
                symbols.add(sm.group("name"))
    return {
        "files": sorted(files),
        "test_files": sorted(test_files),
        "symbols": sorted(symbols),
    }


def _is_test_path(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    return (
        "/tests/" in p or "/test/" in p
        or p.startswith("test") or p.endswith("_test.py")
        or "/test_" in p or p.rsplit("/", 1)[-1].startswith("test_")
    )


def fail_to_pass(instance: dict) -> list[str]:
    """Normalise FAIL_TO_PASS (stored as a JSON-encoded list string or a real list)."""
    raw = instance.get("FAIL_TO_PASS", [])
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = [raw]
    return list(raw)


def file_recall(plan_files: set[str], instance: dict) -> dict:
    """SECONDARY signal: fraction of gold non-test files whose basename is named by a plan
    task's `files:` field. Basename match (the frame can't know full repo paths)."""
    gold = gold_patch_targets(instance["patch"])["files"]
    gold_base = {f.rsplit("/", 1)[-1] for f in gold}
    plan_base = {f.rsplit("/", 1)[-1].strip() for f in plan_files}
    hit = gold_base & plan_base
    return {
        "gold_files": gold,
        "matched": sorted(hit),
        "recall": (len(hit) / len(gold_base)) if gold_base else 0.0,
    }
