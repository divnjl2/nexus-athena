"""A cluster batch must preserve interrupted attempts and stop for review."""
import json

import pytest

from evals.self_improve import cluster_batch, cluster_report


def test_cluster_batch_resume_requires_a_complete_candidate(tmp_path):
    task = {"id": "owner__demo-1", "split": "development"}
    parent = tmp_path / "artifacts" / "development" / task["id"] / "codex"
    assert cluster_batch.cell_action(task, "codex", set(), tmp_path) == "candidate"
    attempt = parent / "1"
    attempt.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="partial candidate"):
        cluster_batch.cell_action(task, "codex", set(), tmp_path)
    for name in cluster_batch.REQUIRED_CANDIDATE:
        (attempt / name).write_text("{}")
    (attempt / "candidate.json").write_text(json.dumps({
        "candidate_status": "unverified_candidate", "executor_failure": None}))
    assert cluster_batch.cell_action(task, "codex", set(), tmp_path) == "gate"
    (attempt / "gate").mkdir()
    with pytest.raises(RuntimeError, match="unfinished gate"):
        cluster_batch.cell_action(task, "codex", set(), tmp_path)
    (attempt / "gate").rmdir()
    (attempt / "candidate.json").write_text(json.dumps({
        "candidate_status": "executor_error", "executor_failure": "process_exit_124"}))
    with pytest.raises(RuntimeError, match="executor error"):
        cluster_batch.cell_action(task, "codex", set(), tmp_path)
    assert cluster_batch.cell_action(task, "codex", {(task["id"], "codex")}, tmp_path) == "skip"
    (parent / "2").mkdir()
    with pytest.raises(RuntimeError, match="ungraded extra attempt"):
        cluster_batch.cell_action(task, "codex", {(task["id"], "codex")}, tmp_path)


def test_cluster_batch_reports_partial_artifacts_without_launching(tmp_path, monkeypatch):
    task = {"id": "owner__demo-1", "split": "development", "repo": "owner/demo"}
    manifest = {"tasks": [task], "revision": "pinned"}
    attempt = tmp_path / "artifacts" / "development" / task["id"] / "codex" / "1"
    attempt.mkdir(parents=True)
    (attempt / "prompt.txt").write_text("interrupted")
    monkeypatch.setattr(cluster_batch, "verify", lambda *_: None)
    monkeypatch.setattr(cluster_batch, "frozen_commit", lambda *_: None)
    monkeypatch.setattr(cluster_report, "validate_manifest_shape", lambda *_: None)
    monkeypatch.setattr(cluster_batch, "run_candidate", lambda **_: pytest.fail("launched candidate"))
    with pytest.raises(RuntimeError, match="partial candidate"):
        cluster_batch.run_batch(
            manifest=manifest, rows=[{"instance_id": task["id"]}], root=tmp_path,
            athena_root=tmp_path, athena_commit="a" * 40, model="agent",
            bridge_url="http://127.0.0.1:8777/v1", key_file=tmp_path / "key",
            probe_report=tmp_path / "probe", context_window=65536,
            candidate_timeout=900, gate_timeout=1800, wsl_distro="Ubuntu",
            harness_python="python", max_pairs=1)
    report = json.loads((tmp_path / "reports" / "development.json").read_text())
    assert report["complete"] is False
    assert report["ungraded_attempts"] == [{"task_id": task["id"], "arm": "codex",
                                             "attempt": 1, "status": "incomplete_artifacts"}]
