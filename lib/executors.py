"""
Athena executors — the registry of who may type the code, and how each is invoked (v3.12).

None of them is trusted: they receive a packet (`lib.dispatch`) and the verdict comes from
the diff and the spec commands. What this module knows is HOW to start each one:

  local-27b / local-9b   a Claude Code worker on a local model through the LiteLLM gateway,
                         read and edit tools only, turns capped, no Bash (C-3.2). Two
                         measured facts shaped the defaults: the files must be inlined
                         (ten turns went to Read) and the output cap must exceed 2048
                         tokens (it cut every multi-line Edit mid-call).
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
LOCAL_OUTPUT_TOKENS = {"local-27b": 6144, "local-9b": 1024}


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
    argv = [claude_bin, "-p", packet_text, "--bare", "--setting-sources", "",
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
    return {"argv": argv, "env": env, "unset": ["ANTHROPIC_API_KEY", "CLAUDECODE",
                                                "CLAUDE_CODE_ENTRYPOINT"]}


def claude_command(packet_text: str, *, max_turns: int = 40, claude_bin: str = "claude") -> dict:
    """PURE: argv for Claude Code on the subscription; Bash allowed so it can run the specs."""
    argv = [claude_bin, "-p", packet_text, "--tools", CLAUDE_TOOLS, "--allowedTools", CLAUDE_TOOLS,
            "--max-turns", str(max_turns), "--permission-mode", "acceptEdits",
            "--output-format", "json"]
    return {"argv": argv, "env": {}, "unset": []}


#: OpenHands tools for a packet-driven task: edit and look, no terminal. The specs are run by
#: the verdict, not by the executor — and on Windows the terminal tool speaks PowerShell while
#: the model speaks bash (`ls -la` -> "parameter not found" -> stuck-detector), measured.
OPENHANDS_TOOLS = ("file_editor", "glob", "grep")


def openhands_config(packet_text: str, *, workspace: str, model: str, base_url: str = "",
                     api_key_env: str = "LITELLM_LOCAL_KEY", max_iterations: int = 30,
                     terminal: bool = False) -> dict:
    """PURE: the OpenHands SDK run (C-3.3): rooted at the repository, the model as named,
    the local gateway as base url when the caller asks for it, edit-and-look tools only
    unless a terminal is asked for."""
    if not model:
        raise ValueError("openhands needs a model name (e.g. openai/qwopus-27b)")
    tools = list(OPENHANDS_TOOLS) + (["terminal"] if terminal else [])
    return {"workspace": str(pathlib.Path(workspace)), "model": model, "base_url": base_url,
            "api_key_env": api_key_env, "max_iterations": int(max_iterations),
            "tools": tools, "task": packet_text}


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
