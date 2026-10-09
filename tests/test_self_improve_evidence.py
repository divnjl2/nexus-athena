"""Executable specs for honest, auditable pilot summaries."""
import hashlib
import json

import pytest

from evals.self_improve.codex_driver import usage_from_trace
from evals.self_improve.corpus import fingerprint, inputs, select
from evals.self_improve.evidence import SCHEMA, load_attempts, summarize
from evals.self_improve.gate_adapter import HARNESS_VERSION, run_id_for


def _rows():
    return [{"instance_id": f"repo{i}__task{j}", "repo": f"org/repo{i}",
             "base_commit": f"sha{i}{j}", "problem_statement": f"bug {i}/{j}",
             "hints_text": "", "FAIL_TO_PASS": [f"test_{i}_{j}"],
             "PASS_TO_PASS": [], "test_patch": f"diff {i}/{j}",
             "image": f"image-{i}-{j}", "eval_script": f"pytest test_{i}_{j}",
             "environment_setup_commit": f"env{i}{j}", "eval_type": "pytest",
             "log_parser": "pytest"}
            for i in range(10) for j in range(5)]


def _attempt(manifest, tmp_path, *, arm="codex", task=None, passed=True, attempt=1):
    task = task or manifest["tasks"][0]
    row = next(row for row in _rows() if row["instance_id"] == task["id"])
    prompt = b"frozen prompt\nsecond line\n"
    patch = b"diff --git a/x b/x\n"
    patch_hash = hashlib.sha256(patch).hexdigest()
    run_id = run_id_for(task["id"], arm, attempt, patch)
    artifact_root = tmp_path / "artifacts"
    attempt_dir = artifact_root / task["split"] / task["id"] / arm / str(attempt)
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "prompt.txt").write_bytes(prompt)
    (attempt_dir / "candidate.patch").write_bytes(patch)
    (attempt_dir / "input.json").write_text(json.dumps(inputs(row)))
    rates = {"input_per_million": 10000, "cached_input_per_million": 0,
             "cache_write_input_per_million": 0, "output_per_million": 10000,
             "max_request_context_tokens": 272000}
    invocation = {"argv": ["codex", "exec"], "cwd": str(attempt_dir),
                  "timeout_seconds": 900, "rates_usd_per_million": rates}
    config_hash = fingerprint({"argv": invocation["argv"], "rates": rates,
                               "timeout": invocation["timeout_seconds"]})
    (attempt_dir / "invocation.json").write_text(json.dumps(invocation))
    trace = json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 100, "output_tokens": 50}}) + "\n"
    (attempt_dir / "trace.jsonl").write_text(trace)
    (attempt_dir / "stderr.txt").write_text("")
    usage = usage_from_trace(trace)
    athena_commit = None if arm == "codex" else "f" * 40
    metadata = {"manifest_sha256": fingerprint(manifest),
                "base_commit": task["base_commit"], "input_sha256": task["input_sha256"],
                "acceptance_sha256": task["acceptance_sha256"],
                "dataset_revision": manifest["revision"], "task_id": task["id"],
                "arm": arm, "attempt": attempt, "athena_commit": athena_commit,
                "seed": None, "candidate_status": "unverified_candidate"}
    (attempt_dir / "attempt.json").write_text(json.dumps(metadata))
    candidate = {"patch_sha256": patch_hash, "patch_bytes": len(patch),
                 "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
                 "config_sha256": config_hash, "model": "codex",
                 "codex_cli_version": "codex-cli 0.161.0",
                 "cost_basis": "API-equivalent estimate", "usage": usage,
                 "wall_seconds": 60, "cost_usd": 1.5,
                 "started_at": "2026-10-09T10:00:00Z",
                 "ended_at": "2026-10-09T10:01:00Z", "exit_code": 0,
                 "candidate_status": "unverified_candidate", "verified": False,
                 "executor_failure": None}
    (attempt_dir / "candidate.json").write_text(json.dumps(candidate))
    artifact = f"gate-{task['id']}-{arm}-{attempt}.json"
    official_name = f"official-{task['id']}-{arm}-{attempt}.json"
    official_data = json.dumps({task["id"]: {"resolved": passed}}).encode()
    (artifact_root / official_name).write_bytes(official_data)
    dataset = tmp_path / "harness" / f"{run_id}.dataset.json"
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text(json.dumps([row]))
    report = {"schema": "athena.self-improve.gate/1", "runner": "swebench-harness",
              "instance_id": task["id"], "patch_sha256": patch_hash,
              "run_id": run_id, "harness_version": HARNESS_VERSION,
              "resolved": passed, "official_report": official_name,
              "official_report_sha256": hashlib.sha256(official_data).hexdigest(),
              "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest()}
    data = json.dumps(report).encode()
    (artifact_root / artifact).write_bytes(data)
    return {"schema": SCHEMA, "run_id": run_id,
            "task_id": task["id"], "arm": arm, "attempt": attempt,
            "manifest_sha256": fingerprint(manifest), "base_commit": task["base_commit"],
            "input_sha256": task["input_sha256"], "acceptance_sha256": task["acceptance_sha256"],
            "model": "codex", "model_version": "codex",
            "model_resolution": "requested_identifier", "codex_cli_version": "codex-cli 0.161.0",
            "cost_basis": "API-equivalent estimate", "dataset_revision": manifest["revision"],
            "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
            "config_sha256": config_hash, "seed": None,
            "athena_commit": athena_commit,
            "started_at": "2026-10-09T10:00:00Z", "ended_at": "2026-10-09T10:01:00Z",
            "input_tokens": 100, "output_tokens": 50, "wall_seconds": 60, "cost_usd": 1.5,
            "patch_sha256": patch_hash, "failure_reason": None if passed else "tests failed",
            "gate": {"runner": "swebench-harness", "artifact": artifact,
                     "sha256": hashlib.sha256(data).hexdigest(), "passed": passed}}


def test_attempt_requires_pinned_provenance_and_matching_gate_artifact(tmp_path):
    """C-2.1: changed inputs or altered gate artifacts invalidate a run."""
    manifest = select(_rows())
    record = _attempt(manifest, tmp_path)
    path = tmp_path / "attempts.jsonl"
    path.write_text(json.dumps(record) + "\n")
    assert load_attempts(path, manifest, tmp_path / "artifacts") == [record]
    record["input_sha256"] = "changed"
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError):
        load_attempts(path, manifest, tmp_path / "artifacts")
    record["input_sha256"] = manifest["tasks"][0]["input_sha256"]
    path.write_text(json.dumps(record) + "\n")
    (tmp_path / "artifacts" / record["gate"]["artifact"]).write_text("{}")
    with pytest.raises(ValueError):
        load_attempts(path, manifest, tmp_path / "artifacts")


def test_attempt_rejects_changed_official_report_even_if_gate_envelope_is_intact(tmp_path):
    """C-4.4: a wrapper cannot hide changes in the official harness report."""
    manifest = select(_rows())
    record = _attempt(manifest, tmp_path)
    path = tmp_path / "attempts.jsonl"
    path.write_text(json.dumps(record) + "\n")
    assert load_attempts(path, manifest, tmp_path / "artifacts")
    envelope = json.loads((tmp_path / "artifacts" / record["gate"]["artifact"]).read_text())
    (tmp_path / "artifacts" / envelope["official_report"]).write_text("{}")
    with pytest.raises(ValueError):
        load_attempts(path, manifest, tmp_path / "artifacts")


def test_attempt_rejects_prompt_bytes_that_differ_from_record(tmp_path):
    """C-3.14: Windows newline conversion cannot pass as exact prompt provenance."""
    manifest = select(_rows())
    record = _attempt(manifest, tmp_path)
    path = tmp_path / "attempts.jsonl"
    path.write_text(json.dumps(record) + "\n")
    assert load_attempts(path, manifest, tmp_path / "artifacts") == [record]
    prompt_path = (tmp_path / "artifacts" / manifest["tasks"][0]["split"] /
                   record["task_id"] / record["arm"] / "1" / "prompt.txt")
    prompt_path.write_bytes(prompt_path.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="prompt bytes"):
        load_attempts(path, manifest, tmp_path / "artifacts")


@pytest.mark.parametrize("changed,reason", [
    ("input", "candidate input"),
    ("patch", "candidate patch"),
    ("invocation", "invocation"),
    ("trace", "candidate trace"),
    ("cost", "candidate trace"),
    ("dataset", "dataset snapshot"),
    ("missing_candidate", "line 1"),
])
def test_attempt_rejects_changed_candidate_or_dataset_evidence(tmp_path, changed, reason):
    """A gate verdict cannot conceal tampering in the runner's other evidence."""
    manifest = select(_rows())
    record = _attempt(manifest, tmp_path)
    task = manifest["tasks"][0]
    attempt = (tmp_path / "artifacts" / task["split"] / task["id"] /
               record["arm"] / "1")
    if changed == "input":
        source = json.loads((attempt / "input.json").read_text())
        source["problem_statement"] = "changed"
        (attempt / "input.json").write_text(json.dumps(source))
    elif changed == "patch":
        (attempt / "candidate.patch").write_bytes(b"different patch")
    elif changed == "invocation":
        invocation = json.loads((attempt / "invocation.json").read_text())
        invocation["timeout_seconds"] += 1
        (attempt / "invocation.json").write_text(json.dumps(invocation))
    elif changed == "trace":
        (attempt / "trace.jsonl").write_text(json.dumps({
            "type": "turn.completed", "usage": {"input_tokens": 101,
                                                   "output_tokens": 50}}))
    elif changed == "cost":
        candidate = json.loads((attempt / "candidate.json").read_text())
        candidate["cost_usd"] = 0.5
        (attempt / "candidate.json").write_text(json.dumps(candidate))
    elif changed == "dataset":
        dataset = tmp_path / "harness" / f"{record['run_id']}.dataset.json"
        dataset.write_text("[]")
    elif changed == "missing_candidate":
        (attempt / "candidate.json").unlink()
    path = tmp_path / "attempts.jsonl"
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError, match=reason):
        load_attempts(path, manifest, tmp_path / "artifacts")


def test_report_refuses_missing_arms_and_charges_failed_attempts(tmp_path):
    """C-2.2: incomplete matrices stay incomplete; failed attempts count toward cost."""
    manifest = select(_rows())
    failed = _attempt(manifest, tmp_path, passed=False)
    passed = _attempt(manifest, tmp_path, attempt=2)
    report = summarize(manifest, [failed, passed])
    assert not report["complete"] and len(report["missing"]) == 119
    assert report["arms"]["codex"]["total_cost_usd"] == 3.0
    assert report["arms"]["codex"]["cost_per_verified_success_usd"] == 3.0
    assert report["arms"]["codex"]["attempts"] == 2
    assert report["arms"]["codex"]["seconds_per_verified_success"] == 120
    assert report["arms"]["codex"]["input_tokens"] == 200


def test_report_is_complete_only_with_all_three_arms_on_every_task(tmp_path):
    """C-2.3: a complete report covers all 40 tasks in all three configurations."""
    manifest = select(_rows())
    records = [_attempt(manifest, tmp_path, arm=arm, task=task)
               for task in manifest["tasks"] for arm in manifest["arms"]]
    report = summarize(manifest, records)
    assert report["complete"] and report["missing"] == []
    assert all(v["verified_successes"] == 40 for v in report["arms"].values())


def test_baseline_precedes_optimizer_and_requires_both_original_arms(tmp_path):
    """C-2.4: the pre-optimizer baseline is the full paired two-arm matrix."""
    manifest = select(_rows())
    records = [_attempt(manifest, tmp_path, arm=arm, task=task)
               for task in manifest["tasks"] for arm in manifest["arms"][:2]]
    baseline = summarize(manifest, records, stage="baseline")
    final = summarize(manifest, records, stage="final")
    assert baseline["complete"] and len(baseline["arms"]) == 2
    assert not final["complete"] and len(final["missing"]) == 40
    assert baseline["paired_comparison"]["tasks"] == 40
    assert final["paired_comparison"] is None
    with pytest.raises(ValueError):
        summarize(manifest, records, stage="development")


def test_paired_report_counts_discordant_tasks_and_failure_reasons(tmp_path):
    """C-2.5: gains and regressions use matched tasks, with failed attempts visible."""
    manifest = select(_rows())
    records = []
    for index, task in enumerate(manifest["tasks"]):
        records.append(_attempt(manifest, tmp_path, arm="codex", task=task,
                                passed=index != 0))
        records.append(_attempt(manifest, tmp_path, arm="codex_athena", task=task,
                                passed=index != 1))
    result = summarize(manifest, records, stage="baseline")
    pair = result["paired_comparison"]
    assert pair["control_only_successes"] == 1
    assert pair["treatment_only_successes"] == 1
    assert pair["success_rate_difference"] == 0
    assert pair["difference_95pct_paired_bootstrap"][0] <= 0 <= \
        pair["difference_95pct_paired_bootstrap"][1]
    assert result["arms"]["codex"]["failure_reasons"] == {"tests failed": 1}


def test_empty_or_shrunken_manifest_cannot_claim_a_complete_pilot():
    """C-2.7: report completeness requires the frozen 40-task shape."""
    with pytest.raises(ValueError):
        summarize({"schema": "athena.self-improve.corpus/1", "tasks": []}, [])
