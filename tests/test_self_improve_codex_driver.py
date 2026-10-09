"""Executable specs for Codex trace and candidate evidence."""
import json
import subprocess

import pytest

from evals.self_improve.codex_driver import (candidate_patch, codex_argv,
                                             executor_failure, price_usd,
                                             usage_from_trace)


def test_completed_codex_turns_account_for_cached_and_output_tokens():
    """C-3.4: only completed turns contribute to measured token usage."""
    trace = "\n".join(json.dumps(x) for x in (
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
        {"type": "turn.completed", "usage": {"input_tokens": 100,
             "cached_input_tokens": 40, "output_tokens": 20}},
        {"type": "turn.completed", "usage": {"input_tokens": 50,
             "cached_input_tokens": 10, "output_tokens": 30}},
    ))
    usage = usage_from_trace(trace)
    assert usage["input_tokens"] == 150 and usage["cached_input_tokens"] == 50
    assert usage["output_tokens"] == 50 and usage["turns"] == 2
    assert usage["max_turn_input_tokens"] == 100
    assert price_usd(usage, {"input_per_million": 2, "cached_input_per_million": 1,
                                  "output_per_million": 4}) == pytest.approx(0.00045)
    with pytest.raises(ValueError):
        usage_from_trace('{"type":"turn.started"}')
    with pytest.raises(ValueError):
        price_usd({**usage, "max_turn_input_tokens": 272_001},
                  {"input_per_million": 2, "cached_input_per_million": 0.1,
                   "output_per_million": 10})


def test_candidate_patch_contains_untracked_files_without_a_gate_verdict(tmp_path):
    """C-3.5: a candidate is a replayable patch, including new files, with no claim of success."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "pilot@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Pilot"], check=True)
    (tmp_path / "existing.py").write_text("old\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "existing.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)
    (tmp_path / "existing.py").write_text("new\n")
    (tmp_path / "added.py").write_text("new file\n")
    patch = candidate_patch(tmp_path)
    assert b"existing.py" in patch and b"added.py" in patch


def test_executor_failures_cannot_be_scored_as_empty_agent_patches():
    """C-3.8: a failed tool or transport is not a verified task failure."""
    completed = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1,
                            "output_tokens": 1}})
    failed = json.dumps({"type": "turn.failed", "error": {"message": "routing failed"}})
    assert executor_failure(completed, "", 0) is None
    assert executor_failure(completed, "exec_command blocked by policy", 0) == "tool_blocked_by_policy"
    assert executor_failure(failed, "", 0) == "turn_failed"
    assert executor_failure(completed, "", 124) == "process_exit_124"


def test_windows_candidate_pins_the_native_elevated_workspace_sandbox(tmp_path):
    """C-3.9: ignored user config cannot silently select a broken Windows sandbox."""
    windows = codex_argv("codex", tmp_path, "fixed-model", platform="nt")
    linux = codex_argv("codex", tmp_path, "fixed-model", platform="posix")
    assert windows[windows.index("-c") + 1] == "windows.sandbox=elevated"
    assert "--ignore-user-config" in windows and "workspace-write" in windows
    assert "-c" not in linux and "workspace-write" in linux
