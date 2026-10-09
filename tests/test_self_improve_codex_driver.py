"""Executable specs for Codex trace and candidate evidence."""
import json
import hashlib
import subprocess
import sys

import pytest

from evals.self_improve.codex_driver import (candidate_patch, codex_argv,
                                             executor_failure, price_usd, run_codex,
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
    rates = {"input_per_million": 2, "cached_input_per_million": 1,
             "cache_write_input_per_million": 2.5, "output_per_million": 4,
             "max_request_context_tokens": 272_000}
    assert price_usd(usage, rates) == pytest.approx(0.00045)
    with pytest.raises(ValueError):
        usage_from_trace('{"type":"turn.started"}')
    with pytest.raises(ValueError):
        price_usd(usage, {**rates, "max_request_context_tokens": 1_050_000})
    assert price_usd({**usage, "cache_write_input_tokens": 10}, rates) == pytest.approx(0.000455)


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
    (tmp_path / ".athena").mkdir()
    (tmp_path / ".athena" / "cache.json").write_text("generated\n")
    (tmp_path / "features" / "case" / ".athena").mkdir(parents=True)
    (tmp_path / "features" / "case" / ".athena" / "run.json").write_text("generated\n")
    patch = candidate_patch(tmp_path)
    assert b"existing.py" in patch and b"added.py" in patch
    assert b"cache.json" not in patch and b"run.json" not in patch


def test_executor_failures_cannot_be_scored_as_empty_agent_patches():
    """C-3.8: a failed tool or transport is not a verified task failure."""
    completed = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1,
                            "output_tokens": 1}})
    failed = json.dumps({"type": "turn.failed", "error": {"message": "routing failed"}})
    assert executor_failure(completed, "", 0) is None
    assert executor_failure(completed, "exec_command blocked by policy", 0) == "tool_blocked_by_policy"
    assert executor_failure(completed, "cleanup blocked by policy", 0, patch_bytes=100) is None
    assert executor_failure(failed, "", 0) == "turn_failed"
    assert executor_failure(completed, "", 124) == "process_exit_124"


def test_windows_candidate_pins_the_native_elevated_workspace_sandbox(tmp_path):
    """C-3.9: ignored user config cannot silently select a broken Windows sandbox."""
    windows = codex_argv("codex", tmp_path, "fixed-model", platform="nt")
    linux = codex_argv("codex", tmp_path, "fixed-model", platform="posix")
    assert windows[windows.index("-c") + 1] == "windows.sandbox=elevated"
    assert "--ignore-user-config" in windows and "workspace-write" in windows
    assert "model_context_window=272000" in windows
    assert "windows.sandbox=elevated" not in linux and "workspace-write" in linux


def test_candidate_prompt_hash_matches_saved_and_submitted_bytes(tmp_path, monkeypatch):
    """Windows newline translation must not change the prompt after hashing it."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "commit.gpgsign", "false"], check=True)
    (workspace / "README").write_text("base\n")
    subprocess.run(["git", "-C", str(workspace), "add", "README"], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-qm", "base"], check=True)
    fake = tmp_path / "fake_codex.py"
    fake.write_text("""import json, pathlib, sys
pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())
pathlib.Path(sys.argv[2], 'marker.txt').write_text('candidate\\n')
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':2}}))
""")
    received = tmp_path / "received.bin"
    monkeypatch.setattr("evals.self_improve.codex_driver.codex_argv",
                        lambda *_: [sys.executable, str(fake), str(received), str(workspace)])
    rates = {"input_per_million": 2, "cached_input_per_million": 0.1,
             "cache_write_input_per_million": 2.5, "output_per_million": 10,
             "max_request_context_tokens": 272_000}
    prompt = "first line\nsecond line\n"
    artifacts = tmp_path / "artifacts"
    candidate = run_codex(workspace, prompt=prompt, model="test", timeout=5,
                          artifacts=artifacts, rates=rates, codex_bin=sys.executable)
    expected = prompt.encode("utf-8")
    assert (artifacts / "prompt.txt").read_bytes() == expected
    assert received.read_bytes() == expected
    assert candidate["prompt_sha256"] == hashlib.sha256(expected).hexdigest()
    assert candidate["trace_sha256"] == hashlib.sha256(
        (artifacts / "trace.jsonl").read_bytes()).hexdigest()
    assert candidate["stderr_sha256"] == hashlib.sha256(
        (artifacts / "stderr.txt").read_bytes()).hexdigest()
    assert candidate["candidate_status"] == "unverified_candidate"


def test_timed_out_candidate_keeps_streamed_trace_and_fails_closed(tmp_path, monkeypatch):
    """An interrupted Codex run leaves diagnostic bytes but no gate-ready candidate."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "commit.gpgsign", "false"], check=True)
    (workspace / "README").write_text("base\n")
    subprocess.run(["git", "-C", str(workspace), "add", "README"], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-qm", "base"], check=True)
    fake = tmp_path / "slow_codex.py"
    fake.write_text("import sys, time\n"
                    "sys.stdin.buffer.read()\n"
                    "sys.stdout.buffer.write(b'{\"type\":\"turn.started\"}\\n')\n"
                    "sys.stdout.buffer.flush()\n"
                    "sys.stderr.buffer.write(b'partial diagnostic\\n')\n"
                    "sys.stderr.buffer.flush()\n"
                    "time.sleep(10)\n")
    monkeypatch.setattr("evals.self_improve.codex_driver.codex_argv",
                        lambda *_: [sys.executable, str(fake)])
    artifacts = tmp_path / "artifacts"
    rates = {"input_per_million": 2, "cached_input_per_million": 0.1,
             "cache_write_input_per_million": 2.5, "output_per_million": 10,
             "max_request_context_tokens": 272_000}
    candidate = run_codex(workspace, prompt="test\n", model="test", timeout=1,
                          artifacts=artifacts, rates=rates, codex_bin=sys.executable)
    assert candidate["exit_code"] == 124
    assert candidate["candidate_status"] == "executor_error"
    assert candidate["verified"] is False
    assert (artifacts / "trace.jsonl").read_bytes() == b'{"type":"turn.started"}\n'
    assert (artifacts / "stderr.txt").read_bytes() == b"partial diagnostic\n"
