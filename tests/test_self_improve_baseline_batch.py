"""Executable checks for safe baseline continuation."""
import json
from pathlib import Path

import pytest

from evals.self_improve import baseline_batch
from evals.self_improve.baseline_batch import cell_action


def test_resume_skips_proved_cells_and_never_overwrites_partial_attempts(tmp_path):
    """C-3.13: a resume cannot silently repeat an existing candidate or gate."""
    cell = {"task_id": "astropy__astropy-8872", "arm": "codex",
            "split": "development"}
    candidate = (tmp_path / "artifacts" / "development" /
                 cell["task_id"] / cell["arm"] / "1")
    assert cell_action(cell, set(), tmp_path) == "candidate"
    candidate.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="partial candidate"):
        cell_action(cell, set(), tmp_path)
    for name in ("candidate.json", "candidate.patch", "attempt.json", "input.json",
                 "prompt.txt", "invocation.json", "trace.jsonl", "stderr.txt"):
        (candidate / name).write_text("preserved")
    (candidate / "candidate.json").write_text(
        '{"candidate_status":"unverified_candidate","executor_failure":null}')
    assert cell_action(cell, set(), tmp_path) == "gate"
    (candidate / "gate").mkdir()
    with pytest.raises(RuntimeError, match="unfinished gate"):
        cell_action(cell, set(), tmp_path)
    (candidate / "gate").rmdir()
    (candidate / "gate_started.json").write_text("started")
    with pytest.raises(RuntimeError, match="unfinished gate"):
        cell_action(cell, set(), tmp_path)
    (candidate / "gate_started.json").unlink()
    (candidate / "candidate.json").write_text(
        '{"candidate_status":"executor_error","executor_failure":"process_exit_124"}')
    with pytest.raises(RuntimeError, match="executor error"):
        cell_action(cell, set(), tmp_path)
    assert cell_action(cell, {(cell["task_id"], cell["arm"])}, tmp_path) == "skip"


def test_partial_baseline_artifacts_are_reported_before_resume_stops(tmp_path, monkeypatch):
    manifest = json.loads(Path("evals/self_improve/manifest.json").read_text(encoding="utf-8"))
    task = manifest["tasks"][0]
    attempt_dir = (tmp_path / "artifacts" / task["split"] / task["id"] / "codex" / "1")
    attempt_dir.mkdir(parents=True)
    (attempt_dir / "prompt.txt").write_bytes(b"interrupted")
    monkeypatch.setattr(baseline_batch, "verify", lambda *_: None)
    monkeypatch.setattr(baseline_batch, "frozen_commit", lambda *_: None)
    monkeypatch.setattr(baseline_batch, "run_one", lambda **_: pytest.fail("candidate replayed"))
    with pytest.raises(RuntimeError, match="partial candidate"):
        baseline_batch.run_batch(
            manifest=manifest, rows=[], root=tmp_path, athena_root=tmp_path,
            athena_commit="a" * 40, model="test", rates={},
            candidate_timeout=1, gate_timeout=1, wsl_distro="Ubuntu",
            harness_python="python", max_pairs=1)
    report = json.loads((tmp_path / "reports" / "partial-baseline.json").read_text())
    assert report["complete"] is False
    assert report["ungraded_attempts"][0]["status"] == "incomplete_or_invalid_artifacts"
    assert report["arms"]["codex"]["total_cost_usd"] is None
