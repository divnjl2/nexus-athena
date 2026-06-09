import json
import pathlib

import pytest

from lib.plan_parser import parse, PlanParseError
from lib.plan2beads import compile, CompileError, EXTERNAL_KEY_PREFIX

FIX = pathlib.Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _cmds(res):
    return [str(c) for c in res.commands]


def test_golden_valid():
    """valid.md -> exact expected bd command list (snapshot, human-reviewed)."""
    res = compile(parse(_read("valid.md")))
    expected = json.loads(_read("valid.expected.json"))
    assert _cmds(res) == expected


def test_deterministic_repeated():
    """Compiling twice yields byte-identical output."""
    plan = parse(_read("valid.md"))
    assert _cmds(compile(plan)) == _cmds(compile(plan))


def test_idempotent_upsert():
    """With existing_keys=all, not a single `bd create` is emitted."""
    plan = parse(_read("valid.md"))
    first = compile(plan)
    all_keys = frozenset(
        a for c in first.commands for i, a in enumerate(c.argv)
        if i > 0 and c.argv[i - 1] == "--label" and a.startswith(EXTERNAL_KEY_PREFIX)
    )
    second = compile(plan, existing_keys=all_keys)
    assert [c for c in _cmds(second) if c.split()[:2] == ["bd", "create"]] == []
    # dependency edges are still emitted (they are not creates)
    assert any(c.split()[:3] == ["bd", "dep", "add"] for c in _cmds(second))


def test_unresolved_dependency_rejected():
    with pytest.raises(CompileError):
        compile(parse(_read("bad_dep.md")))


def test_missing_success_check_rejected_end_to_end():
    with pytest.raises((PlanParseError, CompileError)):
        compile(parse(_read("no_check.md")))


def test_autonomy_label_emitted():
    plan = parse(
        "# Plan: Routed\n## Overview\no\n## Phase 1: P\n**Goal:** g\n**Depends on:** none\n"
        "- [ ] T1.1 heavy task\n  - success_check: `true`\n  - autonomy: high\n"
    )
    cmds = _cmds(compile(plan))
    assert any("autonomy:high" in c for c in cmds)


def test_issue_count_and_epics():
    res = compile(parse(_read("valid.md")))
    assert res.issue_count == 2
    assert res.epic_keys == ("athena:demo-feature:epic1", "athena:demo-feature:epic2")
