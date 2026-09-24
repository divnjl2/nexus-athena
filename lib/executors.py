"""
Athena executors — the registry of who may type the code, and how each is invoked (v3.12).

None of them is trusted: they receive a packet (`lib.dispatch`) and the verdict comes from
the diff and the spec commands. What this module knows is HOW to start each one:

  local-27b / local-9b   a Claude Code worker on a local model through the LiteLLM gateway,
                         read and edit tools only, turns capped, no Bash (C-3.2). Two
                         measured facts shaped the defaults: the files must be inlined
                         (ten turns went to Read) and the output cap must exceed 2048
                         tokens (it cut every multi-line Edit mid-call). The lanes' models
                         think before they act and the thinking is billed to the same cap
                         (measured through the gateway: 89-200 output tokens for "OK"),
                         so the cap is 8192 and the packet tells the model the number.
  openhands              the OpenHands SDK in-process, workspace = the repository, model
                         named by the caller (C-3.3). No Docker.
  claude                 Claude Code on the subscription, Bash allowed.

An executor that is not installed is "unavailable", never a traceback (C-3.4).

Freeze-line: PURE — commands and configurations only. Spawning is the CLI's job; the
availability probes are injected.
"""
from __future__ import annotations

import pathlib

EXECUTORS = ("local-27b", "local-9b", "openhands", "claude")
LANE_MODELS = {"local-27b": "qwopus-27b", "local-9b": "qwable-9b"}
LOCAL_GATEWAY = "http://127.0.0.1:8413"
EDIT_TOOLS = "Read,Glob,Grep,Edit,Write"
CLAUDE_TOOLS = "Read,Glob,Grep,Edit,Write,Bash"
LOCAL_CONTEXT_TOKENS = 30720
LOCAL_OUTPUT_TOKENS = {"local-27b": 8192, "local-9b": 8192}


def resolve(name: str) -> dict:
    """PURE: {name, kind, model} for a known executor; an unknown name is refused (C-3.1)."""
    if name not in EXECUTORS:
        raise ValueError(f"unknown executor {name!r} (one of {', '.join(EXECUTORS)})")
    if name.startswith("local-"):
        return {"name": name, "kind": "local", "model": LANE_MODELS[name]}
    return {"name": name, "kind": name, "model": ""}


def local_lane_command(name: str, packet_text: str, *, max_turns: int = 30,
                       claude_bin: str = "claude", gateway: str = LOCAL_GATEWAY,
                       auth_token: str = "") -> dict:
    """PURE: argv + env for a local-lane worker (C-3.2). Read and edit tools only, turns
    capped, pointed at the local gateway; the worker's own settings are not loaded."""
    spec = resolve(name)
    if spec["kind"] != "local":
        raise ValueError(f"{name} is not a local lane")
    # the packet goes on stdin, never on the command line: with a checkpoint appended it
    # passed 32k chars and Windows refused to start the worker (WinError 206, measured on
    # iterations 2 and 3 of a task whose first iteration had left a 10k tail)
    argv = [claude_bin, "-p", "--bare", "--setting-sources", "",
            "--strict-mcp-config", "--tools", EDIT_TOOLS, "--allowedTools", EDIT_TOOLS,
            "--model", spec["model"], "--max-turns", str(max_turns),
            "--permission-mode", "acceptEdits", "--output-format", "json"]
    env = {
        "ANTHROPIC_BASE_URL": gateway,
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": str(LOCAL_CONTEXT_TOKENS),
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(LOCAL_OUTPUT_TOKENS[name]),
        "CLAUDE_CODE_DISABLE_THINKING": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    if auth_token:
        env["ANTHROPIC_AUTH_TOKEN"] = auth_token
    return {"argv": argv, "env": env, "stdin": packet_text,
            "unset": ["ANTHROPIC_API_KEY", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"]}


def claude_command(packet_text: str, *, max_turns: int = 40, claude_bin: str = "claude") -> dict:
    """PURE: argv for Claude Code on the subscription; Bash allowed so it can run the specs."""
    argv = [claude_bin, "-p", "--tools", CLAUDE_TOOLS, "--allowedTools", CLAUDE_TOOLS,
            "--max-turns", str(max_turns), "--permission-mode", "acceptEdits",
            "--output-format", "json"]
    return {"argv": argv, "env": {}, "stdin": packet_text, "unset": []}


#: OpenHands tools for a packet-driven task: edit and look, no terminal. The specs are run by
#: the verdict, not by the executor — and on Windows the terminal tool speaks PowerShell while
#: the model speaks bash (`ls -la` -> "parameter not found" -> stuck-detector), measured.
OPENHANDS_TOOLS = ("file_editor", "glob", "grep")

#: The implementer's prompt (C-3.5). OpenHands' stock system prompt is written for an
#: explorer of an unknown repository; on a 30k window with a 27B model that prompt won:
#: twelve turns of glob and view per iteration, never an edit (measured, 0 of 8). A packet
#: already carries the requirement, the spec, the file and the test source, so the
#: executor is told what it is: an implementer, not an explorer.
OPENHANDS_IMPLEMENTER_PROMPT = (
    "You are an implementer working inside one repository. You receive a task packet that "
    "already holds the requirement (numbered clauses), the spec commands that decide done, "
    "the files you may change with their full contents, and the source of the test that must "
    "pass. Do not explore the repository and do not read other files: everything you need is "
    "in the packet. Make the change with file_editor str_replace on the named file, using an "
    "exact old_str copied from the packet, in as few calls as possible. Never edit "
    "contract.md, scenarios.md, spec_ledger.json or clause_map.json. You cannot run commands; "
    "the orchestrator runs the specs after you finish and judges by the diff. When the edit "
    "is applied, answer with the single line: DONE."
)


def openhands_config(packet_text: str, *, workspace: str, model: str, base_url: str = "",
                     api_key_env: str = "LITELLM_LOCAL_KEY", max_iterations: int = 30,
                     terminal: bool = False, prompt: str = "implementer") -> dict:
    """PURE: the OpenHands SDK run (C-3.3, C-3.5): rooted at the repository, the model as
    named, the local gateway as base url when the caller asks for it, edit-and-look tools
    only unless a terminal is asked for, and the implementer's prompt unless the stock one
    is asked for (`prompt="default"`)."""
    if not model:
        raise ValueError("openhands needs a model name (e.g. openai/qwopus-27b)")
    tools = list(OPENHANDS_TOOLS) + (["terminal"] if terminal else [])
    return {"workspace": str(pathlib.Path(workspace)), "model": model, "base_url": base_url,
            "api_key_env": api_key_env, "max_iterations": int(max_iterations),
            "tools": tools, "task": packet_text,
            "system_prompt": OPENHANDS_IMPLEMENTER_PROMPT if prompt == "implementer" else ""}


def availability(name: str, *, which=None, find_spec=None, exists=None) -> dict:
    """PURE given its probes: {available, reason} (C-3.4). Defaults probe the real system."""
    import importlib.util
    import shutil
    which = which or shutil.which
    find_spec = find_spec or importlib.util.find_spec
    exists = exists or (lambda p: pathlib.Path(p).exists())
    spec = resolve(name)
    if spec["kind"] == "openhands":
        try:
            ok = find_spec("openhands.sdk") is not None
        except (ImportError, ValueError):
            ok = False
        return {"available": ok, "reason": "" if ok else
                "openhands-sdk is not importable in this interpreter (pip install openhands-sdk openhands-tools)"}
    home_bin = pathlib.Path.home() / ".local" / "bin" / "claude.exe"
    ok = which("claude") is not None or exists(home_bin)
    return {"available": ok, "reason": "" if ok else "the `claude` executable was not found"}


def claude_binary(*, which=None, exists=None) -> str:
    """The claude binary to spawn: PATH first, then the per-user install."""
    import shutil
    which = which or shutil.which
    exists = exists or (lambda p: pathlib.Path(p).exists())
    found = which("claude")
    if found:
        return found
    home_bin = pathlib.Path.home() / ".local" / "bin" / "claude.exe"
    return str(home_bin) if exists(home_bin) else "claude"
