"""The cluster candidate has a separate provider and independent gate trail."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evals.self_improve import cluster_pilot
from evals.self_improve.corpus import acceptance, fingerprint, inputs
from evals.self_improve.gate_adapter import attest


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
        report = tmp_path / "official.json"
        report.write_text(json.dumps({row["instance_id"]: {"resolved": True}}))
        envelope = attest(task_id=row["instance_id"], patch=kwargs["patch"],
                          official_report=report, gate_dir=kwargs["gate_dir"],
                          run_id=run_id, harness_version="5.0.2")
        envelope["dataset_sha256"] = hashlib.sha256(dataset.read_bytes()).hexdigest()
        (kwargs["gate_dir"] / "gate.json").write_text(json.dumps(envelope))
        return envelope

    monkeypatch.setattr(cluster_pilot, "run_harness", official_gate)
    record = cluster_pilot.run_gate(manifest=manifest, row=row, task_id=row["instance_id"],
                                    arm="codex", attempt=1, root=root)
    assert record["schema"] == cluster_pilot.CLUSTER_SCHEMA
    assert record["gate"]["passed"] is True and record["cost_usd"] is None
    assert (root / "records" / "cluster-demo-1.json").is_file()
    (artifact_dir / "gate" / "official_report.json").write_text("{}")
    with pytest.raises(ValueError, match="official cluster report"):
        cluster_pilot.validate_cluster_attempt(record, manifest, root)
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
