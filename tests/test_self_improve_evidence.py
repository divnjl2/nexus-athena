"""Executable specs for honest, auditable pilot summaries."""
import hashlib
import json

import pytest

from evals.self_improve.corpus import fingerprint, select
from evals.self_improve.evidence import SCHEMA, load_attempts, summarize


def _rows():
    return [{"instance_id": f"repo{i}__task{j}", "repo": f"org/repo{i}",
             "base_commit": f"sha{i}{j}", "problem_statement": f"bug {i}/{j}",
             "hints_text": "", "FAIL_TO_PASS": [f"test_{i}_{j}"],
             "PASS_TO_PASS": [], "test_patch": f"diff {i}/{j}"}
            for i in range(12) for j in range(4)]


def _attempt(manifest, tmp_path, *, arm="codex", task=None, passed=True, attempt=1):
    task = task or manifest["tasks"][0]
    patch_hash = "a" * 64
    artifact = f"gate-{task['id']}-{arm}-{attempt}.json"
    official_name = f"official-{task['id']}-{arm}-{attempt}.json"
    official_data = json.dumps({task["id"]: {"resolved": passed}}).encode()
    (tmp_path / official_name).write_bytes(official_data)
    report = {"schema": "athena.self-improve.gate/1", "runner": "swebench-harness",
              "instance_id": task["id"], "patch_sha256": patch_hash,
              "run_id": f"{task['id']}-{arm}-{attempt}", "harness_version": "test-version",
              "resolved": passed, "official_report": official_name,
              "official_report_sha256": hashlib.sha256(official_data).hexdigest()}
    data = json.dumps(report).encode()
    (tmp_path / artifact).write_bytes(data)
    return {"schema": SCHEMA, "run_id": f"{task['id']}-{arm}-{attempt}",
            "task_id": task["id"], "arm": arm, "attempt": attempt,
            "manifest_sha256": fingerprint(manifest), "base_commit": task["base_commit"],
            "input_sha256": task["input_sha256"], "acceptance_sha256": task["acceptance_sha256"],
            "model": "codex", "model_version": "pinned-version",
            "model_resolution": "requested_identifier", "codex_cli_version": "codex-cli 0.161.0",
            "cost_basis": "API-equivalent estimate", "dataset_revision": "pinned-revision",
            "prompt_sha256": "b" * 64, "config_sha256": "c" * 64, "seed": None,
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
    assert load_attempts(path, manifest, tmp_path) == [record]
    record["input_sha256"] = "changed"
    path.write_text(json.dumps(record) + "\n")
    with pytest.raises(ValueError):
        load_attempts(path, manifest, tmp_path)
    record["input_sha256"] = manifest["tasks"][0]["input_sha256"]
    path.write_text(json.dumps(record) + "\n")
    (tmp_path / record["gate"]["artifact"]).write_text("{}")
    with pytest.raises(ValueError):
        load_attempts(path, manifest, tmp_path)


def test_attempt_rejects_changed_official_report_even_if_gate_envelope_is_intact(tmp_path):
    """C-4.4: a wrapper cannot hide changes in the official harness report."""
    manifest = select(_rows())
    record = _attempt(manifest, tmp_path)
    path = tmp_path / "attempts.jsonl"
    path.write_text(json.dumps(record) + "\n")
    assert load_attempts(path, manifest, tmp_path)
    envelope = json.loads((tmp_path / record["gate"]["artifact"]).read_text())
    (tmp_path / envelope["official_report"]).write_text("{}")
    with pytest.raises(ValueError):
        load_attempts(path, manifest, tmp_path)


def test_report_refuses_missing_arms_and_charges_failed_attempts(tmp_path):
    """C-2.2: incomplete matrices stay incomplete; failed attempts count toward cost."""
    manifest = select(_rows())
    failed = _attempt(manifest, tmp_path, passed=False)
    passed = _attempt(manifest, tmp_path, attempt=2)
    report = summarize(manifest, [failed, passed])
    assert not report["complete"] and len(report["missing"]) == 107
    assert report["arms"]["codex"]["total_cost_usd"] == 3.0
    assert report["arms"]["codex"]["cost_per_verified_success_usd"] == 3.0
    assert report["arms"]["codex"]["attempts"] == 2
    assert report["arms"]["codex"]["seconds_per_verified_success"] == 120
    assert report["arms"]["codex"]["input_tokens"] == 200


def test_report_is_complete_only_with_all_three_arms_on_every_task(tmp_path):
    """C-2.3: a complete report covers all 36 tasks in all three configurations."""
    manifest = select(_rows())
    records = [_attempt(manifest, tmp_path, arm=arm, task=task)
               for task in manifest["tasks"] for arm in manifest["arms"]]
    report = summarize(manifest, records)
    assert report["complete"] and report["missing"] == []
    assert all(v["verified_successes"] == 36 for v in report["arms"].values())


def test_baseline_precedes_optimizer_and_requires_both_original_arms(tmp_path):
    """C-2.4: the pre-optimizer baseline is the full paired two-arm matrix."""
    manifest = select(_rows())
    records = [_attempt(manifest, tmp_path, arm=arm, task=task)
               for task in manifest["tasks"] for arm in manifest["arms"][:2]]
    baseline = summarize(manifest, records, stage="baseline")
    final = summarize(manifest, records, stage="final")
    assert baseline["complete"] and len(baseline["arms"]) == 2
    assert not final["complete"] and len(final["missing"]) == 36
    assert baseline["paired_comparison"]["tasks"] == 36
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
    """C-2.6: report completeness requires the frozen 36-task shape."""
    with pytest.raises(ValueError):
        summarize({"schema": "athena.self-improve.corpus/1", "tasks": []}, [])
