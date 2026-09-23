"""v3.12 executors — a registry of who may type the code, none of them trusted.

Each test is the executable spec of one C-3.* clause in features/executor-layer/contract.md.
"""
from __future__ import annotations

import pytest

from lib.executors import (EDIT_TOOLS, EXECUTORS, LOCAL_GATEWAY, availability, claude_command,
                           local_lane_command, openhands_config, resolve)


def test_the_registry_resolves_known_executors_and_refuses_unknown():
    """C-3.1 — four names, no guessing: an unknown executor is refused with the list."""
    assert set(EXECUTORS) == {"local-27b", "local-9b", "openhands", "claude"}
    assert resolve("local-27b") == {"name": "local-27b", "kind": "local", "model": "qwopus-27b"}
    assert resolve("openhands")["kind"] == "openhands" and resolve("claude")["kind"] == "claude"
    with pytest.raises(ValueError) as e:
        resolve("gpt-5")
    assert "local-27b" in str(e.value)


def test_the_local_lane_command_grants_only_read_and_edit_tools():
    """C-3.2 — no Bash, turns capped, the local gateway, an output cap above the one that cut
    every multi-line edit mid-call."""
    cmd = local_lane_command("local-27b", "# Task T1.1 ...", max_turns=25, auth_token="k")
    argv = cmd["argv"]
    assert argv[argv.index("--tools") + 1] == EDIT_TOOLS and "Bash" not in EDIT_TOOLS
    assert argv[argv.index("--max-turns") + 1] == "25"
    assert argv[argv.index("--model") + 1] == "qwopus-27b"
    assert "--bare" in argv and "acceptEdits" in argv
    assert cmd["env"]["ANTHROPIC_BASE_URL"] == LOCAL_GATEWAY
    assert int(cmd["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"]) > 2048
    assert cmd["env"]["ANTHROPIC_AUTH_TOKEN"] == "k" and "ANTHROPIC_API_KEY" in cmd["unset"]
    with pytest.raises(ValueError):
        local_lane_command("openhands", "x")
    assert "Bash" in claude_command("x")["argv"][claude_command("x")["argv"].index("--tools") + 1]


def test_the_openhands_run_is_rooted_at_the_repository_with_the_named_model():
    """C-3.3 — workspace = the repository, model as named, the local gateway when asked."""
    cfg = openhands_config("# Task", workspace="C:/repo", model="openai/qwopus-27b",
                           base_url=LOCAL_GATEWAY, max_iterations=12)
    assert cfg["workspace"].replace("\\", "/") == "C:/repo"
    assert cfg["model"] == "openai/qwopus-27b" and cfg["base_url"] == LOCAL_GATEWAY
    assert cfg["max_iterations"] == 12 and cfg["task"] == "# Task"
    assert "terminal" not in cfg["tools"] and "file_editor" in cfg["tools"], \
        "edit-and-look only: the specs are run by the verdict, not by the executor"
    assert "terminal" in openhands_config("# Task", workspace="C:/repo", model="m", terminal=True)["tools"]
    with pytest.raises(ValueError):
        openhands_config("# Task", workspace="C:/repo", model="")


def test_a_missing_executor_is_unavailable_not_a_traceback():
    """C-3.4 — the probes are injected; a missing SDK or binary is an answer, not a crash."""
    no = availability("openhands", find_spec=lambda name: None)
    assert no["available"] is False and "openhands" in no["reason"]
    yes = availability("openhands", find_spec=lambda name: object())
    assert yes["available"] is True and yes["reason"] == ""
    gone = availability("local-27b", which=lambda name: None, exists=lambda p: False)
    assert gone["available"] is False and "claude" in gone["reason"]
    here = availability("claude", which=lambda name: "C:/bin/claude.exe", exists=lambda p: False)
    assert here["available"] is True
