"""Agent-agnostic executor adapter contract — routing + the shared code<->spec link.

No real agent is invoked; these cover the pure, deterministic core: the registry, routing
precedence, and the provenance close-commands every adapter funnels through.
"""
from __future__ import annotations

import pytest

from ralph.adapter import (
    ADAPTERS, ClaudeCodeAdapter, ExecResult, ExecutorAdapter, Issue,
    close_commands, close_with_provenance, select_adapter,
)


def _issue(**kw) -> Issue:
    base = dict(key="athena:plan:T1.1", title="add health route", success_check="pytest -q")
    base.update(kw)
    return Issue(**base)


def test_all_adapters_satisfy_the_protocol():
    assert set(ADAPTERS) == {"claude_code", "opencode", "openhands", "hermes"}
    for a in ADAPTERS.values():
        assert isinstance(a, ExecutorAdapter)          # runtime Protocol check
        argv = a.command(_issue(), workdir=".")
        assert isinstance(argv, list) and a.name  # command is pure + returns argv


def test_routing_precedence():
    # explicit agent label wins
    assert select_adapter(_issue(labels=("agent:opencode",))).name == "opencode"
    # autonomy:high -> sandboxed openhands
    assert select_adapter(_issue(labels=("autonomy:high",))).name == "openhands"
    # explicit agent beats autonomy:high
    assert select_adapter(_issue(labels=("autonomy:high", "agent:hermes"))).name == "hermes"
    # default otherwise
    assert select_adapter(_issue()).name == "claude_code"
    assert select_adapter(_issue(), default="opencode").name == "opencode"
    # unknown agent label falls through to default
    assert select_adapter(_issue(labels=("agent:nope",))).name == "claude_code"


def test_close_commands_are_agent_independent():
    """The same issue + commit must yield IDENTICAL link commands regardless of which agent
    produced it (only the agent: label differs) — that is what keeps the graph stable."""
    a = close_commands("athena:plan:T1.1", "abc123", spec_version="sv1",
                       scenario_version="scv1", agent="claude_code")
    b = close_commands("athena:plan:T1.1", "abc123", spec_version="sv1",
                       scenario_version="scv1", agent="openhands")
    # strip the agent label, the rest is identical
    strip = lambda cs: [c for c in cs if not (c[:3] == ("bd", "label", "add") and c[3].startswith("agent:"))]
    assert strip(a) == strip(b)
    # the link is recorded: implements + commit + both versions, then close
    flat = " ".join(" ".join(c) for c in a)
    assert "label add implements" in flat
    assert "label add commit:abc123" in flat
    assert "label add spec_version:sv1" in flat
    assert "label add scenario_version:scv1" in flat
    assert a[-1] == ("bd", "close", "athena:plan:T1.1")


def test_close_with_provenance_runs_on_pass_and_refuses_on_fail():
    applied: list = []
    ok = ExecResult(agent="opencode", commit_sha="deadbeef", passed=True)
    cmds = close_with_provenance("athena:plan:T2.1", ok, spec_version="sv",
                                 scenario_version="scv", run=applied.append)
    assert applied == [list(c) for c in cmds]
    assert ["bd", "close", "athena:plan:T2.1"] in applied
    assert any("commit:deadbeef" in " ".join(c) for c in applied)

    failed = ExecResult(agent="opencode", commit_sha="", passed=False)
    with pytest.raises(ValueError, match="gate did not pass"):
        close_with_provenance("athena:plan:T2.1", failed, spec_version="sv",
                              scenario_version="scv", run=applied.append)


def test_commit_key_in_prompt_for_beads_linkage():
    # the prompt must instruct committing with the issue key (Beads links commit->issue by it)
    argv = ClaudeCodeAdapter().command(_issue(key="athena:plan:T9.9"), workdir=".")
    assert any("athena:plan:T9.9" in part for part in argv)
