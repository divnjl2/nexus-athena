"""Run one Codex attempt and preserve its trace and candidate patch.

Acceptance is deliberately separate: this module never reads test_patch or
FAIL_TO_PASS, and its return value cannot mark a task verified.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .corpus import fingerprint

MODEL_CONTEXT_WINDOW = 272_000
AUTO_COMPACT_LIMIT = 240_000


def usage_from_trace(trace: str) -> dict[str, int]:
    """Sum Codex turn.completed usage without counting partial item events."""
    totals = {key: 0 for key in ("input_tokens", "cached_input_tokens",
                                   "cache_write_input_tokens", "output_tokens",
                                   "reasoning_output_tokens")}
    turns = 0
    max_turn_input_tokens = 0
    for line in trace.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") != "turn.completed":
            continue
        usage = event.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("Codex completed a turn without usage")
        for key in totals:
            value = usage.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"invalid Codex usage: {key}")
            totals[key] += value
        max_turn_input_tokens = max(max_turn_input_tokens, usage.get("input_tokens", 0))
        turns += 1
    if not turns:
        raise ValueError("Codex trace contains no completed turn")
    if totals["cached_input_tokens"] > totals["input_tokens"]:
        raise ValueError("cached input exceeds total input")
    totals["turns"] = turns
    totals["max_turn_input_tokens"] = max_turn_input_tokens
    return totals


def executor_failure(trace: str, stderr: str, exit_code: int,
                     patch_bytes: int = 0) -> str | None:
    """Keep transport and tool-policy failures out of task quality scores."""
    if exit_code:
        return f"process_exit_{exit_code}"
    if "blocked by policy" in stderr.lower() and not patch_bytes:
        return "tool_blocked_by_policy"
    try:
        events = [json.loads(line) for line in trace.splitlines() if line.strip()]
    except json.JSONDecodeError:
        return "invalid_trace"
    if any(event.get("type") == "turn.failed" for event in events):
        return "turn_failed"
    if not any(event.get("type") == "turn.completed" for event in events):
        return "missing_completed_turn"
    return None


def price_usd(usage: dict[str, int], rates: dict[str, float]) -> float:
    """Estimate API-equivalent token cost with a versioned rate card."""
    required = ("input_per_million", "cached_input_per_million",
                "cache_write_input_per_million", "output_per_million",
                "max_request_context_tokens")
    if set(rates) != set(required) or any(isinstance(rates[k], bool) or
                                         not isinstance(rates[k], (int, float)) or
                                         not math.isfinite(rates[k]) or rates[k] < 0
                                         for k in required):
        raise ValueError("a nonnegative three-rate price card is required")
    if rates["max_request_context_tokens"] != MODEL_CONTEXT_WINDOW:
        raise ValueError("price card must match the pinned model context window")
    fresh = usage["input_tokens"] - usage["cached_input_tokens"] - usage["cache_write_input_tokens"]
    if fresh < 0:
        raise ValueError("cache tokens exceed total input tokens")
    return (fresh * rates["input_per_million"] +
            usage["cached_input_tokens"] * rates["cached_input_per_million"] +
            usage["cache_write_input_tokens"] * rates["cache_write_input_per_million"] +
            usage["output_tokens"] * rates["output_per_million"]) / 1_000_000


def candidate_patch(workspace: Path) -> bytes:
    """Include tracked edits and new files; leave the candidate in its worktree."""
    staged = subprocess.run(["git", "add", "--intent-to-add", "--all"], cwd=workspace,
                            capture_output=True, text=True)
    if staged.returncode:
        raise RuntimeError(f"cannot enumerate candidate changes: {staged.stderr}")
    diff = subprocess.run(["git", "diff", "--binary", "HEAD", "--", ".",
                           ":(exclude).athena/**", ":(exclude)**/.athena/**"], cwd=workspace,
                          capture_output=True)
    if diff.returncode:
        raise RuntimeError("cannot capture candidate patch")
    return diff.stdout


def codex_argv(codex_bin: str, workspace: Path, model: str, *, platform: str | None = None) -> list[str]:
    """Pin the same restricted workspace policy on every task attempt."""
    platform = platform or os.name
    command = [codex_bin, "exec", "--json", "--ephemeral", "--ignore-user-config"]
    if platform == "nt":
        command.extend(["-c", "windows.sandbox=elevated"])
    command.extend(["-c", f"model_context_window={MODEL_CONTEXT_WINDOW}",
                    "-c", f"model_auto_compact_token_limit={AUTO_COMPACT_LIMIT}",
                    "--sandbox", "workspace-write", "--model", model,
                    "--cd", str(workspace), "-"])
    return command


def run_codex(workspace: Path, *, prompt: str, model: str, timeout: int,
              artifacts: Path, rates: dict[str, float], codex_bin: str = "codex") -> dict:
    """Preserve exact prompt/config/trace/diff; return only an unverified candidate."""
    if not workspace.is_dir() or not model or timeout < 1:
        raise ValueError("workspace, model and positive timeout are required")
    artifacts.mkdir(parents=True, exist_ok=False)
    prompt_bytes = prompt.encode("utf-8")
    (artifacts / "prompt.txt").write_bytes(prompt_bytes)
    resolved_bin = shutil.which(codex_bin) or codex_bin
    try:
        version_proc = subprocess.run([resolved_bin, "--version"], text=True,
                                      capture_output=True, check=False)
        codex_cli_version = version_proc.stdout.strip() if version_proc.returncode == 0 else "unavailable"
    except OSError:
        codex_cli_version = "unavailable"
    cmd = codex_argv(resolved_bin, workspace, model)
    (artifacts / "invocation.json").write_text(json.dumps(
        {"argv": cmd, "cwd": str(workspace), "timeout_seconds": timeout,
         "rates_usd_per_million": rates}, indent=2) + "\n", encoding="utf-8")
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    trace_path = artifacts / "trace.jsonl"
    stderr_path = artifacts / "stderr.txt"
    with trace_path.open("wb") as trace_file, stderr_path.open("wb") as stderr_file:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=trace_file,
                                    stderr=stderr_file, cwd=workspace)
            try:
                proc.communicate(input=prompt_bytes, timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                exit_code = 124
        except OSError as exc:
            exit_code = 127
            stderr_file.write(str(exc).encode("utf-8", "replace"))
    elapsed = time.monotonic() - start
    ended_at = datetime.now(timezone.utc).isoformat()
    stdout_bytes = trace_path.read_bytes()
    stderr_bytes = stderr_path.read_bytes()
    stdout = stdout_bytes.decode("utf-8", "replace")
    stderr = stderr_bytes.decode("utf-8", "replace")
    patch = candidate_patch(workspace)
    (artifacts / "candidate.patch").write_bytes(patch)
    try:
        usage = usage_from_trace(stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        usage = {"error": str(exc)}
    try:
        estimated_cost = price_usd(usage, rates) if "error" not in usage else None
    except ValueError:
        estimated_cost = None
    failure = executor_failure(stdout, stderr, exit_code, len(patch))
    result = {"exit_code": exit_code, "wall_seconds": elapsed,
              "started_at": started_at, "ended_at": ended_at,
              "model": model, "codex_cli_version": codex_cli_version,
              "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
              "config_sha256": fingerprint({"argv": cmd, "rates": rates, "timeout": timeout}),
              "patch_sha256": hashlib.sha256(patch).hexdigest(), "patch_bytes": len(patch),
              "usage": usage, "cost_basis": "API-equivalent estimate; subscription billing may differ",
              "cost_usd": estimated_cost,
              "executor_failure": failure,
              "executor_warning": ("tool_blocked_by_policy" if
                                   "blocked by policy" in stderr.lower() and patch else None),
              "candidate_status": ("executor_error" if failure else
                                   "empty_patch" if not patch else "unverified_candidate"),
              "verified": False}
    (artifacts / "candidate.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
