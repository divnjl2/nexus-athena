import json
import pathlib

import pytest

from lib.ast import Plan, Phase, Task
from lib.plan_parser import parse, PlanParseError
from lib.plan2beads import compile, CompileError, EXTERNAL_KEY_PREFIX

FIX = pathlib.Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _cmds(res):
    return [str(c) for c in res.commands]


def test_golden_valid():
    res = compile(parse(_read("valid.md")))
    expected = json.loads(_read("valid.expected.json"))
    assert _cmds(res) == expected


def test_deterministic_repeated():
    plan = parse(_read("valid.md"))
    assert _cmds(compile(plan)) == _cmds(compile(plan))


def test_idempotent_upsert_is_noop():
    plan = parse(_read("valid.md"))
    first = compile(plan)
    all_keys = frozenset(
        a for c in first.commands for i, a in enumerate(c.argv)
        if i > 0 and c.argv[i - 1] == "--label" and a.startswith(EXTERNAL_KEY_PREFIX)
    )
    second = compile(plan, existing_keys=all_keys)
    assert _cmds(second) == []   # full replan on unchanged plan = true no-op


def test_unresolved_dependency_rejected():
    with pytest.raises(CompileError):
        compile(parse(_read("bad_dep.md")))


def test_missing_success_check_rejected_end_to_end():
    with pytest.raises((PlanParseError, CompileError)):
        compile(parse(_read("no_check.md")))


def test_empty_phase_rejected():
    plan = parse("# Plan: P\n## Overview\no\n## Phase 1: Empty\n**Goal:** g\n**Depends on:** none\n")
    with pytest.raises(CompileError):
        compile(plan)


def test_empty_slug_rejected():
    plan = parse("# Plan: ---\n## Overview\no\n## Phase 1: P\n**Goal:** g\n**Depends on:** none\n"
                 "- [ ] T1.1 t\n  - success_check: `true`\n")
    with pytest.raises(CompileError):
        compile(plan)


def test_autonomy_label_emitted_when_non_default():
    plan = parse("# Plan: R\n## Overview\no\n## Phase 1: P\n**Goal:** g\n**Depends on:** none\n"
                 "- [ ] T1.1 heavy\n  - success_check: `true`\n  - autonomy: high\n")
    assert any("--label autonomy:high" in c for c in _cmds(compile(plan)))


def test_default_autonomy_emits_no_label():
    cmds = _cmds(compile(parse(_read("valid.md"))))
    assert not any("autonomy:" in c for c in cmds)


def test_issue_count_and_epic_keys():
    res = compile(parse(_read("valid.md")))
    assert res.issue_count == 2
    assert res.epic_keys == ("athena:demo-feature:phase1", "athena:demo-feature:phase2")


def test_parallel_siblings_no_edges_sequential_chain():
    # phase with T1.1(seq), T1.2[P], T1.3(seq): T1.3 blocked-by T1.1; T1.2 unlinked
    plan = Plan(title="Edge", overview="o", out_of_scope=(), phases=(
        Phase(key="phase1", title="P", goal="g", tasks=(
            Task("T1.1", "a", "true"),
            Task("T1.2", "b", "true", parallel=True),
            Task("T1.3", "c", "true"),
        )),
    ))
    deps = [c for c in _cmds(compile(plan)) if c.split()[:3] == ["bd", "dep", "add"]]
    assert deps == ["bd dep add athena:edge:T1.3 --blocked-by athena:edge:T1.1"]


def test_checkpoint_carried_in_epic_body():
    plan = Plan(title="Cp", overview="o", out_of_scope=(), phases=(
        Phase(key="US1", title="Story", goal="ship it", checkpoint="pytest -q",
              tasks=(Task("T001", "x", "true"),)),
    ))
    epic = [c for c in _cmds(compile(plan)) if c.split()[:4] == ["bd", "create", "--type", "epic"]][0]
    assert "checkpoint: pytest -q" in epic
