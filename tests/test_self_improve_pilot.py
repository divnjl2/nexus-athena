"""Executable specs for task inputs and arm isolation."""
import pytest

import hashlib
import json

from evals.self_improve.corpus import acceptance, fingerprint, inputs
from evals.self_improve.codex_driver import usage_from_trace
from evals.self_improve.gate_adapter import HARNESS_VERSION, attest, run_id_for
from evals.self_improve.pilot import authorize_split, gate_one, prompt_for


def test_prompts_expose_only_issue_inputs_and_keep_optimizer_out_of_baselines(tmp_path):
    """C-3.6: baseline inputs are identical; optimizer text enters only its own arm."""
    row = {"repo": "org/repo", "problem_statement": "fix empty input",
           "hints_text": "maintainer hint", "FAIL_TO_PASS": ["hidden_test"],
           "PASS_TO_PASS": ["old_test"], "test_patch": "secret patch"}
    base = prompt_for(row, "codex", athena_root=tmp_path)
    athena = prompt_for(row, "codex_athena", athena_root=tmp_path)
    optimized = prompt_for(row, "codex_athena_optimizer", athena_root=tmp_path,
                           optimizer_instructions="Prefer a smaller context packet.")
    for text in (base, athena, optimized):
        assert "fix empty input" in text and "maintainer hint" in text
        assert "hidden_test" not in text and "secret patch" not in text
    assert "CORE.md" not in base and "CORE.md" in athena
    assert "Prefer a smaller context packet." not in athena
    with pytest.raises(ValueError):
        prompt_for(row, "codex_athena", athena_root=tmp_path,
                   optimizer_instructions="sneak")


def test_optimizer_holdout_requires_matching_frozen_instructions_and_evidence(tmp_path):
    """C-3.7: development candidate text cannot be sent to holdout before promotion."""
    manifest = {"tasks": [{"id": "one", "split": "holdout"}]}
    task = manifest["tasks"][0]
    text = "Use a short context packet."
    with pytest.raises(ValueError):
        authorize_split(manifest, task, "codex_athena_optimizer", text, None, tmp_path)
    reports = {
        "baseline": {"schema": "athena.self-improve.report/1", "stage": "baseline",
                     "manifest_sha256": fingerprint(manifest), "complete": True},
        "development": {"schema": "athena.self-improve.development/1",
                        "manifest_sha256": fingerprint(manifest), "complete": True,
                        "instructions_sha256": hashlib.sha256(text.encode()).hexdigest()},
    }
    promotion = {"schema": "athena.self-improve.promotion/1",
                 "manifest_sha256": fingerprint(manifest),
                 "instructions_sha256": hashlib.sha256(text.encode()).hexdigest()}
    for name, report in reports.items():
        data = json.dumps(report).encode()
        (tmp_path / f"{name}.json").write_bytes(data)
        promotion[f"{name}_report"] = f"{name}.json"
        promotion[f"{name}_report_sha256"] = hashlib.sha256(data).hexdigest()
    authorize_split(manifest, task, "codex_athena_optimizer", text, promotion, tmp_path)
    with pytest.raises(ValueError):
        authorize_split(manifest, task, "codex_athena_optimizer", "changed", promotion, tmp_path)
    (tmp_path / "baseline.json").write_text("{}")
    with pytest.raises(ValueError):
        authorize_split(manifest, task, "codex_athena_optimizer", text, promotion, tmp_path)
    authorize_split(manifest, {"split": "development"}, "codex_athena_optimizer", text, None, tmp_path)


def test_official_gate_creates_one_valid_immutable_attempt_record(tmp_path, monkeypatch):
    """C-4.5: a candidate becomes a record only after official report binding."""
    import evals.self_improve.pilot as pilot
    from evals.self_improve.evidence import load_attempts
    row = {"instance_id": "org__repo-1", "repo": "org/repo",
           "base_commit": "a" * 40, "problem_statement": "fix it", "hints_text": "",
           "FAIL_TO_PASS": ["test_fix"], "PASS_TO_PASS": [], "test_patch": "test diff",
           "image": "test-image", "eval_script": "pytest test_fix",
           "environment_setup_commit": "env", "eval_type": "pytest",
           "log_parser": "pytest"}
    task = {"id": row["instance_id"], "repo": row["repo"],
            "base_commit": row["base_commit"], "split": "development",
            "input_sha256": fingerprint(inputs(row)),
            "acceptance_sha256": fingerprint(acceptance(row))}
    manifest = {"revision": "pin", "tasks": [task]}
    attempt_dir = tmp_path / "artifacts" / "development" / task["id"] / "codex" / "1"
    attempt_dir.mkdir(parents=True)
    patch = b"diff --git a/x b/x\n"
    (attempt_dir / "candidate.patch").write_bytes(patch)
    prompt = b"frozen prompt\n"
    (attempt_dir / "prompt.txt").write_bytes(prompt)
    (attempt_dir / "input.json").write_text(json.dumps(inputs(row)))
    rates = {"input_per_million": 10000, "cached_input_per_million": 0,
             "cache_write_input_per_million": 0, "output_per_million": 10000,
             "max_request_context_tokens": 272000}
    invocation = {"argv": ["codex", "exec"], "cwd": str(attempt_dir),
                  "timeout_seconds": 900, "rates_usd_per_million": rates}
    (attempt_dir / "invocation.json").write_text(json.dumps(invocation))
    trace = json.dumps({"type": "turn.completed", "usage": {
        "input_tokens": 100, "output_tokens": 50}}) + "\n"
    (attempt_dir / "trace.jsonl").write_text(trace)
    (attempt_dir / "stderr.txt").write_text("")
    trace_hash = hashlib.sha256((attempt_dir / "trace.jsonl").read_bytes()).hexdigest()
    stderr_hash = hashlib.sha256((attempt_dir / "stderr.txt").read_bytes()).hexdigest()
    (attempt_dir / "candidate.json").write_text(json.dumps({
        "patch_sha256": hashlib.sha256(patch).hexdigest(), "model": "snapshot",
        "patch_bytes": len(patch), "exit_code": 0, "verified": False,
        "candidate_status": "unverified_candidate",
        "codex_cli_version": "codex-cli test", "cost_basis": "API-equivalent estimate",
        "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
        "trace_sha256": trace_hash, "stderr_sha256": stderr_hash,
        "config_sha256": fingerprint({"argv": invocation["argv"], "rates": rates,
                                       "timeout": invocation["timeout_seconds"]}),
        "started_at": "2026-10-09T10:00:00Z", "ended_at": "2026-10-09T10:01:00Z",
        "usage": usage_from_trace(trace),
        "wall_seconds": 60, "cost_usd": 1.5}))
    (attempt_dir / "attempt.json").write_text(json.dumps({
        "manifest_sha256": fingerprint(manifest), "task_id": task["id"],
        "arm": "codex", "attempt": 1, "athena_commit": None, "seed": None,
        "base_commit": task["base_commit"], "input_sha256": task["input_sha256"],
        "acceptance_sha256": task["acceptance_sha256"],
        "dataset_revision": manifest["revision"],
        "candidate_status": "unverified_candidate"}))

    def fake_harness(**kwargs):
        official = tmp_path / "official.json"
        official.write_text(json.dumps({task["id"]: {"resolved": True}}))
        run_id = run_id_for(task["id"], "codex", 1, patch)
        kwargs["workdir"].mkdir(parents=True, exist_ok=True)
        dataset = kwargs["workdir"] / f"{run_id}.dataset.json"
        dataset.write_text(json.dumps([row]))
        envelope = attest(task_id=task["id"], patch=patch, official_report=official,
                          gate_dir=kwargs["gate_dir"], run_id=run_id,
                          harness_version=HARNESS_VERSION)
        envelope["dataset_sha256"] = hashlib.sha256(dataset.read_bytes()).hexdigest()
        envelope["gate_wall_seconds"] = 20
        (kwargs["gate_dir"] / "gate.json").write_text(json.dumps(envelope))
        return envelope

    monkeypatch.setattr(pilot, "run_harness", fake_harness)
    candidate_path = attempt_dir / "candidate.json"
    failed_candidate = json.loads(candidate_path.read_text())
    failed_candidate["candidate_status"] = "executor_error"
    failed_candidate["executor_failure"] = "tool_blocked_by_policy"
    candidate_path.write_text(json.dumps(failed_candidate))
    with pytest.raises(ValueError):
        gate_one(manifest=manifest, row=row, task_id=task["id"], arm="codex",
                 attempt=1, root=tmp_path)
    failed_candidate["candidate_status"] = "unverified_candidate"
    failed_candidate["executor_failure"] = None
    candidate_path.write_text(json.dumps(failed_candidate))
    (attempt_dir / "prompt.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="prompt bytes"):
        gate_one(manifest=manifest, row=row, task_id=task["id"], arm="codex",
                 attempt=1, root=tmp_path)
    (attempt_dir / "prompt.txt").write_bytes(prompt)
    trace_path = attempt_dir / "trace.jsonl"
    original_trace = trace_path.read_bytes()
    trace_path.write_bytes(original_trace + b"\r\n")
    with pytest.raises(ValueError, match="trace.jsonl bytes"):
        gate_one(manifest=manifest, row=row, task_id=task["id"], arm="codex",
                 attempt=1, root=tmp_path)
    trace_path.write_bytes(original_trace)
    record = gate_one(manifest=manifest, row=row, task_id=task["id"], arm="codex",
                      attempt=1, root=tmp_path)
    assert record["gate"]["passed"] is True
    assert load_attempts(tmp_path / "records", manifest, tmp_path / "artifacts") == [record]
    with pytest.raises(ValueError):
        gate_one(manifest=manifest, row={**row, "test_patch": "changed"},
                 task_id=task["id"], arm="codex", attempt=1, root=tmp_path)
    with pytest.raises(FileExistsError):
        gate_one(manifest=manifest, row=row, task_id=task["id"], arm="codex",
                 attempt=1, root=tmp_path)
