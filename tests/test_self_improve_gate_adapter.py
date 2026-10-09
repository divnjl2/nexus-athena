"""Executable specs for independent SWE-bench evidence binding."""
import hashlib
import json
import subprocess

import pytest

from evals.self_improve.gate_adapter import attest, official_verdict, prediction, run_harness, run_id_for


def test_official_report_shape_is_required():
    """C-4.1: only the official task-keyed report can supply a verdict."""
    assert official_verdict({"repo__task-1": {"resolved": True}}, "repo__task-1")
    with pytest.raises(ValueError):
        official_verdict({"resolved": True}, "repo__task-1")
    with pytest.raises(ValueError):
        official_verdict({"repo__task-1": {"resolved": "yes"}}, "repo__task-1")
    empty = {"schema_version": 2, "total_instances": 1, "submitted_instances": 1,
             "empty_patch_instances": 1, "empty_patch_ids": ["repo__task-1"],
             "submitted_ids": ["repo__task-1"], "resolved_instances": 0,
             "error_instances": 0}
    assert official_verdict(empty, "repo__task-1") is False
    with pytest.raises(ValueError):
        official_verdict({**empty, "empty_patch_ids": ["other-task"]}, "repo__task-1")


def test_prediction_and_run_id_bind_exact_patch_and_attempt():
    """C-4.2: unique attempts never reuse a cached harness verdict for another patch."""
    patch = b"diff --git a/x b/x\n"
    row = json.loads(prediction("repo__task-1", "codex", patch))
    assert row == {"instance_id": "repo__task-1", "model_name_or_path": "codex",
                   "model_patch": patch.decode()}
    assert run_id_for("repo__task-1", "codex", 1, patch) != \
        run_id_for("repo__task-1", "codex", 2, patch)
    assert run_id_for("repo__task-1", "codex", 1, patch) != \
        run_id_for("repo__task-1", "codex", 1, patch + b"changed")
    assert json.loads(prediction("repo__task-1", "codex", b""))["model_patch"] == ""


def test_gate_envelope_preserves_official_report_and_patch_hash(tmp_path):
    """C-4.3: the envelope binds the unchanged official report and exact candidate."""
    patch = b"patch bytes"
    official = tmp_path / "source-report.json"
    official.write_text(json.dumps({"repo__task-1": {"resolved": False}}))
    gate_dir = tmp_path / "gate"
    result = attest(task_id="repo__task-1", patch=patch, official_report=official,
                    gate_dir=gate_dir, run_id="unique-run", harness_version="test-version")
    assert result["resolved"] is False
    assert result["patch_sha256"] == hashlib.sha256(patch).hexdigest()
    assert (gate_dir / "official_report.json").read_bytes() == official.read_bytes()


def test_harness_reads_a_local_pinned_task_snapshot_and_its_v5_report(tmp_path, monkeypatch):
    """C-4.6: the official gate cannot silently reload a changed remote task row."""
    import evals.self_improve.gate_adapter as adapter
    row = {"instance_id": "repo__task-1", "base_commit": "a" * 40,
           "problem_statement": "fix it", "FAIL_TO_PASS": ["test_fix"]}
    patch = b"diff --git a/x b/x\n"
    workdir = tmp_path / "harness"

    def fake_run(command, **kwargs):
        if "-c" in command:
            return subprocess.CompletedProcess(command, 0, stdout="5.0.2\n", stderr="")
        dataset = command[command.index("--dataset_name") + 1]
        assert json.loads(open(dataset, encoding="utf-8").read()) == [row]
        run_id = command[command.index("--run_id") + 1]
        report_dir = workdir / "logs" / "evaluation" / run_id / "codex" / row["instance_id"]
        report_dir.mkdir(parents=True)
        (report_dir / "report.json").write_text(json.dumps({row["instance_id"]: {"resolved": True}}))
        return subprocess.CompletedProcess(command, 0, stdout="done", stderr="")

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    result = run_harness(task_id=row["instance_id"], arm="codex", attempt=1,
                         model_name="codex", patch=patch, row=row,
                         workdir=workdir, gate_dir=tmp_path / "gate",
                         harness_python="python")
    assert result["resolved"] is True and result["harness_version"] == "5.0.2"
    assert result["dataset_sha256"] == hashlib.sha256(
        (workdir / f"{result['run_id']}.dataset.json").read_bytes()).hexdigest()


def test_empty_patch_is_bound_to_official_v5_results(tmp_path, monkeypatch):
    """C-4.7: a skipped empty prediction is a measured failure, not a missing cell."""
    import evals.self_improve.gate_adapter as adapter
    row = {"instance_id": "repo__task-1", "base_commit": "a" * 40,
           "problem_statement": "fix it", "FAIL_TO_PASS": ["test_fix"]}
    workdir = tmp_path / "harness"

    def fake_run(command, **kwargs):
        if "-c" in command:
            return subprocess.CompletedProcess(command, 0, stdout="5.0.2\n", stderr="")
        run_id = command[command.index("--run_id") + 1]
        path = workdir / "logs" / "evaluation" / run_id / "results.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema_version": 2, "total_instances": 1,
                                    "submitted_instances": 1, "empty_patch_instances": 1,
                                    "empty_patch_ids": [row["instance_id"]],
                                    "submitted_ids": [row["instance_id"]],
                                    "resolved_instances": 0, "error_instances": 0}))
        return subprocess.CompletedProcess(command, 0, stdout="done", stderr="")

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)
    result = run_harness(task_id=row["instance_id"], arm="codex", attempt=1,
                         model_name="codex", patch=b"", row=row, workdir=workdir,
                         gate_dir=tmp_path / "gate", harness_python="python")
    assert result["resolved"] is False
    assert json.loads((tmp_path / "gate" / "official_report.json").read_text())["empty_patch_ids"] == [row["instance_id"]]
