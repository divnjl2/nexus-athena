"""The cluster candidate has a separate provider and independent gate trail."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evals.self_improve import cluster_pilot, cluster_report
from evals.self_improve.corpus import acceptance, fingerprint, inputs
from evals.self_improve.gate_adapter import attest, prediction


def test_cluster_provider_is_loopback_and_key_stays_out_of_argv(tmp_path):
    cmd = cluster_pilot.cluster_argv("codex", tmp_path, model="agent",
                                     base_url="http://127.0.0.1:8777/v1",
                                     context_window=65536, platform="nt")
    assert 'model_provider="athena_cluster_bridge"' in cmd
    assert 'model_providers.athena_cluster_bridge.env_key="ATHENA_BRIDGE_CLIENT_KEY"' in cmd
    assert "model_context_window=65536" in cmd
    assert "model_auto_compact_token_limit=49152" in cmd
    assert "windows.sandbox=elevated" in cmd
    assert "workspace-write" in cmd
    with pytest.raises(ValueError, match="loopback"):
        cluster_pilot.cluster_argv("codex", tmp_path, model="agent",
                                  base_url="http://192.168.1.136:30400/v1",
                                  context_window=65536)
    stale = tmp_path / "stale-probe.json"
    stale.write_text(json.dumps({
        "schema": "athena.cluster-probe/1", "passed": True,
        "checked_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "requested_model": "agent", "gateway": "http://127.0.0.1:8777/v1",
        "checks": {name: True for name in ("sse_terminal", "text", "function_call",
                                            "replayed_tool_result")}}))
    with pytest.raises(ValueError, match="stale"):
        cluster_pilot._qualifying_probe(stale, "agent", "http://127.0.0.1:8777/v1")


def test_cluster_candidate_is_unpriced_and_only_official_gate_accepts_it(tmp_path, monkeypatch):
    row = {"instance_id": "owner__demo-1", "repo": "owner/demo",
           "base_commit": "a" * 40, "problem_statement": "Write a marker.", "hints_text": "",
           "FAIL_TO_PASS": "[]", "PASS_TO_PASS": "[]", "test_patch": "",
           "image": "test-image", "eval_script": "", "environment_setup_commit": "",
           "eval_type": "pytest", "log_parser": "pytest"}
    manifest = {"revision": "pinned", "tasks": [{
        "id": row["instance_id"], "repo": row["repo"], "base_commit": row["base_commit"],
        "split": "development", "input_sha256": fingerprint(inputs(row)),
        "acceptance_sha256": fingerprint(acceptance(row))}]}
    monkeypatch.setattr(cluster_pilot, "verify", lambda *_: None)
    monkeypatch.setattr(cluster_report, "validate_manifest_shape", lambda *_: None)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "commit.gpgsign", "false"], check=True)
    (workspace / "README").write_text("base\n")
    subprocess.run(["git", "-C", str(workspace), "add", "README"], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-qm", "base"], check=True)
    monkeypatch.setattr(cluster_pilot, "prepare", lambda *_, **__: workspace)
    fake = tmp_path / "fake_codex.py"
    fake.write_text("""import json, pathlib, sys
pathlib.Path(sys.argv[1], 'marker.txt').write_text('candidate\\n')
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':2}}))
""")
    monkeypatch.setattr(cluster_pilot, "cluster_argv",
                        lambda _bin, _workspace, **_kw: [sys.executable, str(fake), str(workspace)])
    key_file = tmp_path / "client.key"
    key_file.write_text("private-client-token\n")
    probe_file = tmp_path / "probe.json"
    probe_file.write_text(json.dumps({
        "schema": "athena.cluster-probe/1", "checked_at": datetime.now(timezone.utc).isoformat(),
        "passed": True, "requested_model": "agent", "gateway": "http://127.0.0.1:8777/v1",
        "reported_models": ["cluster-model-v1"] * 3,
        "checks": {name: True for name in ("sse_terminal", "text", "function_call",
                                            "replayed_tool_result")}}))
    root = tmp_path / "cluster-root"
    candidate = cluster_pilot.run_candidate(
        manifest=manifest, rows=[row], task_id=row["instance_id"], arm="codex",
        attempt=1, root=root, athena_root=tmp_path, model="agent",
        base_url="http://127.0.0.1:8777/v1", key_file=key_file,
        probe_report=probe_file, codex_bin=sys.executable)
    assert candidate["candidate_status"] == "unverified_candidate"
    assert candidate["verified"] is False and candidate["cost_usd"] is None
    artifact_dir = Path(candidate["artifacts"])
    assert b"marker.txt" in (artifact_dir / "candidate.patch").read_bytes()
    assert "private-client-token" not in (artifact_dir / "invocation.json").read_text()

    trace_path = artifact_dir / "trace.jsonl"
    original_trace = trace_path.read_bytes()
    assert candidate["trace_sha256"] == hashlib.sha256(original_trace).hexdigest()
    altered_trace = (original_trace.replace(b"\r\n", b"\n") if b"\r\n" in original_trace
                     else original_trace.replace(b"\n", b"\r\n"))
    assert altered_trace != original_trace
    trace_path.write_bytes(altered_trace)
    with pytest.raises(ValueError, match="trace"):
        cluster_pilot.run_gate(manifest=manifest, row=row, task_id=row["instance_id"],
                               arm="codex", attempt=1, root=root)
    trace_path.write_bytes(original_trace)

    stderr_path = artifact_dir / "stderr.txt"
    original_stderr = stderr_path.read_bytes()
    assert candidate["stderr_sha256"] == hashlib.sha256(original_stderr).hexdigest()
    stderr_path.write_bytes(original_stderr + b"\r\n")
    with pytest.raises(ValueError, match="trace"):
        cluster_pilot.run_gate(manifest=manifest, row=row, task_id=row["instance_id"],
                               arm="codex", attempt=1, root=root)
    stderr_path.write_bytes(original_stderr)

    original_prompt = (artifact_dir / "prompt.txt").read_bytes()
    (artifact_dir / "prompt.txt").write_bytes(b"changed prompt")
    with pytest.raises(ValueError, match="prompt"):
        cluster_pilot.run_gate(manifest=manifest, row=row, task_id=row["instance_id"],
                               arm="codex", attempt=1, root=root)
    (artifact_dir / "prompt.txt").write_bytes(original_prompt)

    original_patch = (artifact_dir / "candidate.patch").read_bytes()
    (artifact_dir / "candidate.patch").write_bytes(b"altered")
    with pytest.raises(ValueError, match="altered"):
        cluster_pilot.run_gate(manifest=manifest, row=row, task_id=row["instance_id"],
                               arm="codex", attempt=1, root=root)
    (artifact_dir / "candidate.patch").write_bytes(original_patch)

    def official_gate(**kwargs):
        run_id = "cluster-demo-1"
        kwargs["workdir"].mkdir(parents=True, exist_ok=True)
        dataset = kwargs["workdir"] / f"{run_id}.dataset.json"
        dataset.write_text(json.dumps([row]) + "\n")
        prediction_path = kwargs["workdir"] / f"{run_id}.jsonl"
        prediction_path.write_bytes(prediction(row["instance_id"],
                                               kwargs["model_name"], kwargs["patch"]))
        command_path = kwargs["workdir"] / f"{run_id}.command.json"
        command_path.write_text(json.dumps([
            "python", "-m", "swebench.harness.run_evaluation",
            "--dataset_name", str(dataset), "--split", "test",
            "--predictions_path", str(prediction_path),
            "--instance_ids", row["instance_id"], "--max_workers", "1",
            "--timeout", "600", "--run_id", run_id]))
        stdout_path = kwargs["workdir"] / f"{run_id}.stdout.txt"
        stderr_path = kwargs["workdir"] / f"{run_id}.stderr.txt"
        stdout_path.write_bytes(b"official harness output\n")
        stderr_path.write_bytes(b"")
        report = tmp_path / "official.json"
        report.write_text(json.dumps({row["instance_id"]: {"resolved": True}}))
        envelope = attest(task_id=row["instance_id"], patch=kwargs["patch"],
                          official_report=report, gate_dir=kwargs["gate_dir"],
                          run_id=run_id, harness_version="5.0.2")
        envelope["dataset_sha256"] = hashlib.sha256(dataset.read_bytes()).hexdigest()
        envelope["gate_wall_seconds"] = 20
        for name, path in (("command", command_path), ("prediction", prediction_path),
                           ("stdout", stdout_path), ("stderr", stderr_path)):
            envelope[f"{name}_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (kwargs["gate_dir"] / "gate.json").write_text(json.dumps(envelope))
        return envelope

    monkeypatch.setattr(cluster_pilot, "run_harness", official_gate)
    record = cluster_pilot.run_gate(manifest=manifest, row=row, task_id=row["instance_id"],
                                    arm="codex", attempt=1, root=root)
    assert record["schema"] == cluster_pilot.CLUSTER_SCHEMA
    assert record["gate"]["passed"] is True and record["cost_usd"] is None
    assert record["total_wall_seconds"] == pytest.approx(record["wall_seconds"] + 20)
    assert record["probe_reported_models"] == ["cluster-model-v1"] * 3
    assert (root / "records" / "cluster-demo-1.json").is_file()
    trace_path.write_bytes(altered_trace)
    with pytest.raises(ValueError, match="trace_sha256"):
        cluster_pilot.validate_cluster_attempt(record, manifest, root)
    with pytest.raises(ValueError, match="invalid cluster record"):
        cluster_report.load_records(root, manifest)
    trace_path.write_bytes(original_trace)
    report = cluster_report.summarize_cluster(
        manifest, cluster_report.load_records(root, manifest), root)
    assert report["complete"] is False and report["paired_comparison"] is None
    assert report["missing"] == [{"task_id": row["instance_id"],
                                   "arm": "codex_athena"}]
    assert report["total_cost_usd"] is None
    assert report["probe_reported_models"] == ["cluster-model-v1"]
    assert report["model_identity_basis"] == "synthetic preflight probe only"
    assert report["arms"]["codex"]["verified_successes"] == 1
    assert report["arms"]["codex"]["cost_per_verified_success_usd"] is None
    assert report["arms"]["codex"]["gate_wall_seconds"] == 20
    assert report["arms"]["codex"]["total_wall_seconds"] == \
        pytest.approx(record["total_wall_seconds"])
    altered_record = {**record, "probe_reported_models": ["invented"]}
    with pytest.raises(ValueError, match="probe model observation"):
        cluster_pilot.validate_cluster_attempt(altered_record, manifest, root)
    altered_record = {**record, "total_wall_seconds": record["wall_seconds"]}
    with pytest.raises(ValueError, match="gate duration or total attempt time"):
        cluster_pilot.validate_cluster_attempt(altered_record, manifest, root)
    altered_record = {**record, "failure_reason": "invented failure"}
    with pytest.raises(ValueError, match="failure reason"):
        cluster_pilot.validate_cluster_attempt(altered_record, manifest, root)
    command_path = root / "harness" / f"{record['run_id']}.command.json"
    original_command = command_path.read_bytes()
    command_path.write_bytes(original_command + b"changed\n")
    with pytest.raises(ValueError, match="official harness command evidence"):
        cluster_pilot.validate_cluster_attempt(record, manifest, root)
    command_path.write_bytes(original_command)
    (artifact_dir / "gate" / "official_report.json").write_text("{}")
    with pytest.raises(ValueError, match="official cluster report"):
        cluster_pilot.validate_cluster_attempt(record, manifest, root)
    with pytest.raises(ValueError, match="invalid cluster record"):
        cluster_report.load_records(root, manifest)
    (artifact_dir / "gate" / "official_report.json").write_text(
        json.dumps({row["instance_id"]: {"resolved": True}}))

    candidate_path = artifact_dir / "candidate.json"
    original_candidate = candidate_path.read_text()
    altered_candidate = json.loads(original_candidate)
    altered_candidate["wall_seconds"] += 5
    candidate_path.write_text(json.dumps(altered_candidate))
    with pytest.raises(ValueError, match="provenance or timing"):
        cluster_pilot.validate_cluster_attempt(record, manifest, root)
    candidate_path.write_text(original_candidate)

    metadata_path = artifact_dir / "attempt.json"
    original_metadata = metadata_path.read_text()
    altered_metadata = json.loads(original_metadata)
    altered_metadata["acceptance_sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(altered_metadata))
    with pytest.raises(ValueError, match="input or framework revision"):
        cluster_pilot.validate_cluster_attempt(record, manifest, root)
    metadata_path.write_text(original_metadata)
    cluster_pilot.validate_cluster_attempt(record, manifest, root)

    fake.write_text("""import json, sys, time
print(json.dumps({'type': 'turn.started'}), flush=True)
print('executor reached model', file=sys.stderr, flush=True)
time.sleep(60)
""")
    timed_out = cluster_pilot.run_candidate(
        manifest=manifest, rows=[row], task_id=row["instance_id"], arm="codex",
        attempt=2, root=root, athena_root=tmp_path, model="agent",
        base_url="http://127.0.0.1:8777/v1", key_file=key_file,
        probe_report=probe_file, codex_bin=sys.executable, timeout=1)
    timed_out_dir = Path(timed_out["artifacts"])
    assert timed_out["exit_code"] == 124
    assert timed_out["candidate_status"] == "executor_error"
    assert "turn.started" in (timed_out_dir / "trace.jsonl").read_text()
    assert "executor reached model" in (timed_out_dir / "stderr.txt").read_text()
    report = cluster_report.summarize_cluster(
        manifest, cluster_report.load_records(root, manifest), root)
    assert report["arms"]["codex"]["attempts"] == 1
    assert report["arms"]["codex"]["total_wall_seconds"] is None
    assert report["arms"]["codex"]["wall_lower_bound_seconds"] == \
        pytest.approx(record["total_wall_seconds"])
    assert report["ungraded_attempts"] == [{"task_id": row["instance_id"],
                                             "arm": "codex", "attempt": 2,
                                             "status": "executor_error"}]

    official_path = artifact_dir / "gate" / "official_report.json"
    official_path.write_text(json.dumps({row["instance_id"]: {"resolved": False}}))
    gate_path = artifact_dir / "gate" / "gate.json"
    envelope = json.loads(gate_path.read_text())
    envelope["resolved"] = False
    envelope["official_report_sha256"] = hashlib.sha256(official_path.read_bytes()).hexdigest()
    gate_path.write_text(json.dumps(envelope))
    false_record = {**record, "failure_reason": "",
                    "gate": {**record["gate"], "passed": False,
                             "sha256": hashlib.sha256(gate_path.read_bytes()).hexdigest()}}
    with pytest.raises(ValueError, match="failure reason"):
        cluster_pilot.validate_cluster_attempt(false_record, manifest, root)
