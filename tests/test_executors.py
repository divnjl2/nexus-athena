"""v3.12 executors — a registry of who may type the code, none of them trusted.

Each test is the executable spec of one C-3.* clause in features/executor-layer/contract.md.
"""
from __future__ import annotations

import pytest

from lib.executors import (EDIT_TOOLS, EXECUTORS, LOCAL_GATEWAY, availability, claude_command,
                           local_lane_command, openhands_config, resolve)


def test_the_registry_resolves_known_executors_and_refuses_unknown():
    """C-3.1 — four names, no guessing: an unknown executor is refused with the list."""
    assert set(EXECUTORS) == {"local-27b", "local-9b", "openhands", "claude", "pi-27b", "pi-9b"}
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
    # the packet travels on stdin: on the command line it hit Windows' 32k limit (WinError 206)
    assert cmd["stdin"] == "# Task T1.1 ..." and "# Task T1.1 ..." not in argv
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


def test_openhands_gets_an_implementers_prompt_not_an_explorers():
    """C-3.5 — the packet already holds what an explorer would go looking for; the executor
    is told it is an implementer, and the stock prompt is an explicit choice."""
    cfg = openhands_config("# Task", workspace="C:/repo", model="openai/qwopus-27b")
    prompt = cfg["system_prompt"]
    assert "implementer" in prompt.lower() and "Do not explore" in prompt
    assert "str_replace" in prompt and "DONE" in prompt and "contract.md" in prompt
    assert "orchestrator runs the specs" in prompt
    stock = openhands_config("# Task", workspace="C:/repo", model="m", prompt="default")
    assert stock["system_prompt"] == ""


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


def test_the_pi_executor_runs_print_mode_on_the_lane_with_the_packet_on_stdin():
    """C-3.6 — pi in print mode, JSON events, nothing loaded but the packet; the lane is the
    provider; the claim, the tokens and an error come out of the events."""
    import json
    from lib.executors import PI_ORDER, availability, pi_command, pi_result, resolve
    assert resolve("pi-27b") == {"name": "pi-27b", "kind": "pi", "model": "qwen3.8-27b"}
    cmd = pi_command("pi-9b", "# Task T1.1 ...", pi_bin="C:/bin/pi", thinking="low")
    argv = cmd["argv"]
    assert argv[0] == "C:/bin/pi" and "-p" in argv and argv[argv.index("--mode") + 1] == "json"
    for flag in ("--no-session", "--no-extensions", "--no-skills", "--no-context-files"):
        assert flag in argv
    assert argv[argv.index("--tools") + 1] == "read,bash,edit,write"
    assert argv[argv.index("--provider") + 1] == "lane9" and argv[argv.index("--model") + 1] == "qwen3.5-9b"
    assert argv[argv.index("--thinking") + 1] == "low"
    assert argv[-1] == PI_ORDER and cmd["stdin"] == "# Task T1.1 ..." and cmd["parse"] == "pi"
    # the lane's own default effort when none is asked: the 27B's default xhigh never answered
    assert pi_command("pi-27b", "x")["argv"][pi_command("pi-27b", "x")["argv"].index("--thinking") + 1] == "low"
    with pytest.raises(ValueError):
        pi_command("local-27b", "x")

    def ev(msg):
        return json.dumps({"type": "message_end", "message": msg})
    out = "\n".join([
        json.dumps({"type": "session", "id": "s"}),
        ev({"role": "user", "content": [{"type": "text", "text": "hi"}]}),
        ev({"role": "assistant", "content": [{"type": "thinking", "thinking": "t"},
                                             {"type": "toolCall", "id": "1", "name": "edit", "arguments": {}}],
            "usage": {"input": 1000, "output": 40}, "stopReason": "toolUse"}),
        ev({"role": "assistant", "content": [{"type": "text", "text": "\n\nDONE"}],
            "usage": {"input": 1200, "output": 5}, "stopReason": "stop"}),
        "not json",
    ])
    claim, tokens, err = pi_result(out)
    assert claim == "DONE" and err == ""
    assert tokens == {"input_tokens": 2200, "output_tokens": 45}
    bad = ev({"role": "assistant", "content": [], "usage": {}, "stopReason": "error",
              "errorMessage": "400 Unexpected message role."})
    assert pi_result(bad)[2] == "400 Unexpected message role."
    assert availability("pi-27b", which=lambda n: "C:/bin/pi" if n == "pi" else None)["available"]
    assert not availability("pi-27b", which=lambda n: None)["available"]


def test_a_pi_executor_with_hashline_loads_the_extension_and_leaves_files_to_the_read_tool():
    """C-3.7 — with hashline the argv loads the extension and offers the anchored tools; the
    order names the files for the read tool; without an installed extension it is refused."""
    from lib.executors import PI_HASHLINE_TOOLS, hashline_order, pi_command
    cmd = pi_command("pi-9b", "# Task", hashline="C:/ext/hashline/index.ts", files=["lib/x.py", "lib/y.py"])
    argv = cmd["argv"]
    assert argv[argv.index("-e") + 1] == "C:/ext/hashline/index.ts"
    assert argv[argv.index("--tools") + 1] == PI_HASHLINE_TOOLS and "edit" not in PI_HASHLINE_TOOLS.split(",")
    assert "replace" in PI_HASHLINE_TOOLS and "read" in PI_HASHLINE_TOOLS
    assert argv[-1] == hashline_order(["lib/x.py", "lib/y.py"])
    assert "lib/x.py" in argv[-1] and "read" in argv[-1] and "anchor" in argv[-1].lower()
    plain = pi_command("pi-9b", "# Task")
    assert "-e" not in plain["argv"]
    with pytest.raises(ValueError):
        pi_command("pi-9b", "# Task", hashline="", files=["lib/x.py"], require_hashline=True)
