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
    trace_hash = hashlib.sha256((attempt_dir / "trace.jsonl").read_bytes()).hexdigest()
    stderr_hash = hashlib.sha256((attempt_dir / "stderr.txt").read_bytes()).hexdigest()
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
                 "trace_sha256": trace_hash, "stderr_sha256": stderr_hash,
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
            "trace_sha256": trace_hash, "stderr_sha256": stderr_hash,
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


def test_attempt_rejects_semantically_identical_trace_with_changed_bytes(tmp_path):
    """A newline rewrite cannot silently alter the evidence behind usage."""
    manifest = select(_rows())
    record = _attempt(manifest, tmp_path)
    path = tmp_path / "attempts.jsonl"
    path.write_text(json.dumps(record) + "\n")
    assert load_attempts(path, manifest, tmp_path / "artifacts") == [record]
    trace_path = (tmp_path / "artifacts" / manifest["tasks"][0]["split"] /
                  record["task_id"] / record["arm"] / "1" / "trace.jsonl")
    original = trace_path.read_bytes()
    changed = original.replace(b"\r\n", b"\n") if b"\r\n" in original else \
        original.replace(b"\n", b"\r\n")
    assert changed != original
    trace_path.write_bytes(changed)
    with pytest.raises(ValueError, match="trace.jsonl bytes"):
        load_attempts(path, manifest, tmp_path / "artifacts")
    trace_path.write_bytes(original)
    stderr_path = trace_path.with_name("stderr.txt")
    stderr_path.write_bytes(b"late diagnostic\r\n")
    with pytest.raises(ValueError, match="stderr.txt bytes"):
        load_attempts(path, manifest, tmp_path / "artifacts")


@pytest.mark.parametrize("changed,reason", [
    ("input", "candidate input"),
    ("patch", "candidate patch"),
    ("invocation", "invocation"),
    ("trace", "trace.jsonl bytes"),
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
    report = summarize(manifest, [failed, passed], tmp_path / "artifacts")
    assert not report["complete"] and len(report["missing"]) == 119
    assert report["arms"]["codex"]["total_cost_usd"] == 3.0
    assert report["arms"]["codex"]["cost_per_verified_success_usd"] == 3.0
    assert report["arms"]["codex"]["attempts"] == 2
    assert report["arms"]["codex"]["seconds_per_verified_success"] == 120
    assert report["arms"]["codex"]["input_tokens"] == 200


def test_report_prices_ungated_attempts_only_from_complete_candidate_evidence(tmp_path):
    """Executor and interrupted gate costs cannot disappear from a comparison."""
    manifest = select(_rows())
    first = _attempt(manifest, tmp_path, passed=True)
    _attempt(manifest, tmp_path, attempt=2)
    report = summarize(manifest, [first], tmp_path / "artifacts", stage="baseline")
    arm = report["arms"]["codex"]
    assert report["complete"] is False and report["paired_comparison"] is None
    assert report["ungraded_attempts"][0]["attempt"] == 2
    assert report["ungraded_attempts"][0]["observed_cost_usd"] == 1.5
    assert arm["attempts"] == 2 and arm["total_cost_usd"] == 3.0
    assert arm["cost_per_verified_success_usd"] == 3.0
    assert arm["cost_complete"] is True
    assert arm["input_tokens"] == 200 and arm["output_tokens"] == 100

    task = manifest["tasks"][0]
    attempt_dir = (tmp_path / "artifacts" / task["split"] / task["id"] / "codex" / "2")
    (attempt_dir / "stderr.txt").unlink()
    report = summarize(manifest, [first], tmp_path / "artifacts", stage="baseline")
    arm = report["arms"]["codex"]
    assert report["ungraded_attempts"][0]["status"] == "incomplete_or_invalid_artifacts"
    assert arm["cost_complete"] is False
    assert arm["cost_lower_bound_usd"] == 1.5
    assert arm["total_cost_usd"] is None
    assert arm["cost_per_verified_success_usd"] is None
    assert arm["input_tokens"] is None and arm["input_tokens_lower_bound"] == 100
    assert arm["failure_reasons"] == {"ungraded:incomplete_or_invalid_artifacts": 1}


def test_report_counts_executor_error_with_completed_usage(tmp_path):
    """A failed turn still incurs a measured cost if prior turn usage is intact."""
    manifest = select(_rows())
    record = _attempt(manifest, tmp_path)
    task = manifest["tasks"][0]
    attempt_dir = (tmp_path / "artifacts" / task["split"] / task["id"] / "codex" / "1")
    trace_path = attempt_dir / "trace.jsonl"
    trace_path.write_bytes(trace_path.read_bytes() + b'{"type":"turn.failed"}\n')
    candidate_path = attempt_dir / "candidate.json"
    candidate = json.loads(candidate_path.read_text())
    candidate["trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    candidate["candidate_status"] = "executor_error"
    candidate["executor_failure"] = "turn_failed"
    candidate_path.write_text(json.dumps(candidate))
    metadata_path = attempt_dir / "attempt.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["candidate_status"] = "executor_error"
    metadata_path.write_text(json.dumps(metadata))
    report = summarize(manifest, [], tmp_path / "artifacts", stage="baseline")
    assert report["ungraded_attempts"][0]["status"] == "executor_error"
    assert report["ungraded_attempts"][0]["observed_cost_usd"] == record["cost_usd"]
    assert report["arms"]["codex"]["total_cost_usd"] == record["cost_usd"]
    assert report["complete"] is False


def test_report_is_complete_only_with_all_three_arms_on_every_task(tmp_path):
    """C-2.3: a complete report covers all 40 tasks in all three configurations."""
    manifest = select(_rows())
    records = [_attempt(manifest, tmp_path, arm=arm, task=task)
               for task in manifest["tasks"] for arm in manifest["arms"]]
    report = summarize(manifest, records, tmp_path / "artifacts")
    assert report["complete"] and report["missing"] == []
    assert all(v["verified_successes"] == 40 for v in report["arms"].values())


def test_baseline_precedes_optimizer_and_requires_both_original_arms(tmp_path):
    """C-2.4: the pre-optimizer baseline is the full paired two-arm matrix."""
    manifest = select(_rows())
    records = [_attempt(manifest, tmp_path, arm=arm, task=task)
               for task in manifest["tasks"] for arm in manifest["arms"][:2]]
    baseline = summarize(manifest, records, tmp_path / "artifacts", stage="baseline")
    final = summarize(manifest, records, tmp_path / "artifacts", stage="final")
    assert baseline["complete"] and len(baseline["arms"]) == 2
    assert not final["complete"] and len(final["missing"]) == 40
    assert baseline["paired_comparison"]["tasks"] == 40
    assert final["paired_comparison"] is None
    with pytest.raises(ValueError):
        summarize(manifest, records, tmp_path / "artifacts", stage="development")


def test_paired_report_counts_discordant_tasks_and_failure_reasons(tmp_path):
    """C-2.5: gains and regressions use matched tasks, with failed attempts visible."""
    manifest = select(_rows())
    records = []
    for index, task in enumerate(manifest["tasks"]):
        records.append(_attempt(manifest, tmp_path, arm="codex", task=task,
                                passed=index != 0))
        records.append(_attempt(manifest, tmp_path, arm="codex_athena", task=task,
                                passed=index != 1))
    result = summarize(manifest, records, tmp_path / "artifacts", stage="baseline")
    pair = result["paired_comparison"]
    assert pair["control_only_successes"] == 1
    assert pair["treatment_only_successes"] == 1
    assert pair["success_rate_difference"] == 0
    assert pair["difference_95pct_paired_bootstrap"][0] <= 0 <= \
        pair["difference_95pct_paired_bootstrap"][1]
    assert result["arms"]["codex"]["failure_reasons"] == {"tests failed": 1}


def test_empty_or_shrunken_manifest_cannot_claim_a_complete_pilot(tmp_path):
    """C-2.7: report completeness requires the frozen 40-task shape."""
    with pytest.raises(ValueError):
        summarize({"schema": "athena.self-improve.corpus/1", "tasks": []},
                  [], tmp_path / "artifacts")
