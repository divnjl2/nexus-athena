"""Validate immutable attempt records and summarize only complete pilot matrices.

This module reads evidence. It does not run or impersonate the acceptance harness.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .codex_driver import executor_failure, price_usd, usage_from_trace
from .corpus import ARMS, acceptance, fingerprint, inputs, validate_manifest_shape
from .gate_adapter import HARNESS_VERSION, run_id_for, validate_harness_io

SCHEMA = "athena.self-improve.attempt/1"
STAGES = {"baseline": ARMS[:2], "final": ARMS}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_attempt(record: dict, manifest: dict, artifacts: Path) -> None:
    """Fail closed on absent provenance, altered gate reports and inconsistent verdicts."""
    tasks = {task["id"]: task for task in manifest["tasks"]}
    if record.get("schema") != SCHEMA or record.get("task_id") not in tasks:
        raise ValueError("unknown attempt schema or task")
    task = tasks[record["task_id"]]
    if record.get("arm") not in ARMS or record.get("attempt", 0) < 1:
        raise ValueError("unknown arm or attempt number")
    for key, expected in (("manifest_sha256", fingerprint(manifest)),
                          ("base_commit", task["base_commit"]),
                          ("input_sha256", task["input_sha256"]),
                          ("acceptance_sha256", task["acceptance_sha256"])):
        if record.get(key) != expected:
            raise ValueError(f"attempt has wrong {key}")
    for key in ("run_id", "model", "model_version", "model_resolution",
                "codex_cli_version", "cost_basis", "dataset_revision",
                "prompt_sha256", "trace_sha256", "stderr_sha256",
                "config_sha256", "started_at", "ended_at",
                "patch_sha256"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValueError(f"missing {key}")
    attempt_dir = (artifacts / task["split"] / record["task_id"] /
                   record["arm"] / str(record["attempt"])).resolve()
    if not attempt_dir.is_relative_to(artifacts.resolve()):
        raise ValueError("candidate artifacts escaped the run root")
    prompt_path = attempt_dir / "prompt.txt"
    if not prompt_path.is_file() or file_sha256(prompt_path) != record["prompt_sha256"]:
        raise ValueError("saved prompt bytes do not match the recorded hash")
    for name, key in (("trace.jsonl", "trace_sha256"),
                      ("stderr.txt", "stderr_sha256")):
        path = attempt_dir / name
        if not path.is_file() or file_sha256(path) != record[key]:
            raise ValueError(f"saved {name} bytes do not match the recorded hash")
    candidate = json.loads((attempt_dir / "candidate.json").read_text(encoding="utf-8"))
    metadata = json.loads((attempt_dir / "attempt.json").read_text(encoding="utf-8"))
    invocation = json.loads((attempt_dir / "invocation.json").read_text(encoding="utf-8"))
    source = json.loads((attempt_dir / "input.json").read_text(encoding="utf-8"))
    patch = (attempt_dir / "candidate.patch").read_bytes()
    trace = (attempt_dir / "trace.jsonl").read_text(encoding="utf-8")
    stderr = (attempt_dir / "stderr.txt").read_text(encoding="utf-8")
    if fingerprint(source) != task["input_sha256"] or \
            metadata.get("manifest_sha256") != record["manifest_sha256"] or \
            metadata.get("base_commit") != task["base_commit"] or \
            metadata.get("input_sha256") != task["input_sha256"] or \
            metadata.get("acceptance_sha256") != task["acceptance_sha256"] or \
            metadata.get("dataset_revision") != manifest["revision"] or \
            metadata.get("task_id") != record["task_id"] or \
            metadata.get("arm") != record["arm"] or \
            metadata.get("attempt") != record["attempt"] or \
            metadata.get("athena_commit") != record.get("athena_commit") or \
            metadata.get("seed") != record.get("seed") or \
            metadata.get("candidate_status") != candidate.get("candidate_status"):
        raise ValueError("saved candidate input or framework revision changed")
    patch_sha = hashlib.sha256(patch).hexdigest()
    config_sha = fingerprint({"argv": invocation["argv"],
                              "rates": invocation["rates_usd_per_million"],
                              "timeout": invocation["timeout_seconds"]})
    if patch_sha != record["patch_sha256"] or \
            candidate.get("patch_sha256") != patch_sha or \
            candidate.get("patch_bytes") != len(patch) or \
            candidate.get("trace_sha256") != record["trace_sha256"] or \
            candidate.get("stderr_sha256") != record["stderr_sha256"] or \
            config_sha != record["config_sha256"] or \
            candidate.get("config_sha256") != config_sha:
        raise ValueError("saved candidate patch or invocation changed")
    usage = usage_from_trace(trace)
    estimated_cost = price_usd(usage, invocation["rates_usd_per_million"])
    if candidate.get("usage") != usage or \
            record.get("input_tokens") != usage["input_tokens"] or \
            record.get("output_tokens") != usage["output_tokens"] or \
            not math.isclose(record.get("cost_usd", -1), estimated_cost,
                             rel_tol=0, abs_tol=1e-9) or \
            not math.isclose(candidate.get("cost_usd", -1), estimated_cost,
                             rel_tol=0, abs_tol=1e-9) or \
            executor_failure(trace, stderr, candidate.get("exit_code"), len(patch)) is not None:
        raise ValueError("saved candidate trace, cost or executor status changed")
    expected_status = "unverified_candidate" if patch else "empty_patch"
    for key in ("model", "codex_cli_version", "prompt_sha256", "cost_basis",
                "wall_seconds", "started_at", "ended_at"):
        if candidate.get(key) != record.get(key):
            raise ValueError(f"saved candidate {key} changed")
    if candidate.get("candidate_status") != expected_status or \
            candidate.get("executor_failure") is not None or \
            candidate.get("verified") is not False or \
            record.get("model_version") != record["model"] or \
            record.get("dataset_revision") != manifest["revision"] or \
            record.get("run_id") != run_id_for(record["task_id"], record["arm"],
                                               record["attempt"], patch):
        raise ValueError("candidate identity or run id changed")
    try:
        started = datetime.fromisoformat(record["started_at"])
        ended = datetime.fromisoformat(record["ended_at"])
        if started.tzinfo is None or ended.tzinfo is None or ended < started:
            raise ValueError("invalid attempt time interval")
    except ValueError as exc:
        raise ValueError("invalid attempt timestamps") from exc
    if record["model_resolution"] != "requested_identifier":
        raise ValueError("model resolution claim is unsupported")
    if "seed" not in record or "failure_reason" not in record:
        raise ValueError("seed and failure_reason must be recorded, even if null")
    for key in ("input_tokens", "output_tokens", "wall_seconds",
                "gate_wall_seconds", "total_wall_seconds", "cost_usd"):
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid {key}")
    if record["input_tokens"] + record["output_tokens"] > 0 and record["cost_usd"] == 0:
        raise ValueError("nonzero model usage cannot have an unpriced zero-cost estimate")
    gate = record.get("gate")
    if not isinstance(gate, dict) or gate.get("runner") != "swebench-harness":
        raise ValueError("independent SWE-bench gate report required")
    relative = Path(gate.get("artifact", ""))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("gate artifact must be relative to the artifact directory")
    path = (artifacts / relative).resolve()
    if not path.is_relative_to(artifacts.resolve()) or not path.is_file():
        raise ValueError("gate artifact missing or outside the artifact directory")
    if file_sha256(path) != gate.get("sha256"):
        raise ValueError("gate artifact fingerprint mismatch")
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if envelope.get("schema") != "athena.self-improve.gate/1" or \
            envelope.get("runner") != "swebench-harness" or \
            envelope.get("instance_id") != record["task_id"] or \
            envelope.get("patch_sha256") != record["patch_sha256"] or \
            envelope.get("run_id") != record["run_id"] or \
            envelope.get("harness_version") != HARNESS_VERSION:
        raise ValueError("gate envelope does not bind this task and patch")
    gate_seconds = envelope.get("gate_wall_seconds")
    if isinstance(gate_seconds, bool) or not isinstance(gate_seconds, (int, float)) or \
            not math.isfinite(gate_seconds) or gate_seconds < 0 or \
            not math.isclose(record["gate_wall_seconds"], gate_seconds,
                             rel_tol=0, abs_tol=1e-9) or \
            not math.isclose(record["total_wall_seconds"],
                             record["wall_seconds"] + gate_seconds,
                             rel_tol=0, abs_tol=1e-9):
        raise ValueError("gate duration or total attempt time changed")
    dataset_path = (artifacts.parent / "harness" /
                    f"{record['run_id']}.dataset.json").resolve()
    if not dataset_path.is_relative_to(artifacts.parent.resolve()) or \
            not dataset_path.is_file() or \
            file_sha256(dataset_path) != envelope.get("dataset_sha256"):
        raise ValueError("official dataset snapshot changed")
    snapshot = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, list) or len(snapshot) != 1 or \
            snapshot[0].get("instance_id") != record["task_id"] or \
            fingerprint(inputs(snapshot[0])) != task["input_sha256"] or \
            fingerprint(acceptance(snapshot[0])) != task["acceptance_sha256"]:
        raise ValueError("official gate used a different task row")
    validate_harness_io(artifacts.parent / "harness", envelope,
                        task_id=record["task_id"],
                        model_name=f"{record['arm']}_{record['attempt']}", patch=patch)
    official_relative = Path(envelope.get("official_report", ""))
    official_path = (path.parent / official_relative).resolve()
    if not official_relative.parts or official_relative.is_absolute() or \
            ".." in official_relative.parts or not official_path.is_relative_to(artifacts.resolve()) or \
            not official_path.is_file():
        raise ValueError("official report missing or outside artifact directory")
    if file_sha256(official_path) != envelope.get("official_report_sha256"):
        raise ValueError("official report fingerprint mismatch")
    from .gate_adapter import official_verdict
    resolved = official_verdict(json.loads(official_path.read_text(encoding="utf-8")),
                                record["task_id"])
    if gate.get("passed") is not resolved or envelope.get("resolved") is not resolved:
        raise ValueError("gate verdict mismatch")
    if record["failure_reason"] is None and not gate["passed"]:
        raise ValueError("failed attempt needs a failure reason")


def load_attempts(path: Path, manifest: dict, artifacts: Path) -> list[dict]:
    records, keys, run_ids = [], set(), set()
    if path.is_dir():
        lines = [entry.read_text(encoding="utf-8") for entry in sorted(path.glob("*.json"))]
    else:
        lines = path.read_text(encoding="utf-8").splitlines()
    for line_no, line in enumerate(lines, 1):
        record = json.loads(line)
        try:
            validate_attempt(record, manifest, artifacts)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise ValueError(f"line {line_no}: {exc}") from exc
        key = (record["task_id"], record["arm"], record["attempt"])
        if key in keys or record["run_id"] in run_ids:
            raise ValueError(f"line {line_no}: duplicate attempt or run id")
        keys.add(key)
        run_ids.add(record["run_id"])
        records.append(record)
    return records


def _ungraded_candidate_cost(attempt_dir: Path, task: dict, manifest: dict,
                             arm: str, attempt: int) -> dict:
    """Price a candidate only when its saved inputs and usage validate."""
    candidate = json.loads((attempt_dir / "candidate.json").read_text(encoding="utf-8"))
    metadata = json.loads((attempt_dir / "attempt.json").read_text(encoding="utf-8"))
    invocation = json.loads((attempt_dir / "invocation.json").read_text(encoding="utf-8"))
    source = json.loads((attempt_dir / "input.json").read_text(encoding="utf-8"))
    patch = (attempt_dir / "candidate.patch").read_bytes()
    prompt = (attempt_dir / "prompt.txt").read_bytes()
    trace_bytes = (attempt_dir / "trace.jsonl").read_bytes()
    stderr_bytes = (attempt_dir / "stderr.txt").read_bytes()
    trace = trace_bytes.decode("utf-8", "replace")
    stderr = stderr_bytes.decode("utf-8", "replace")
    for key, expected in (("task_id", task["id"]), ("arm", arm),
                          ("attempt", attempt), ("manifest_sha256", fingerprint(manifest)),
                          ("base_commit", task["base_commit"]),
                          ("input_sha256", task["input_sha256"]),
                          ("acceptance_sha256", task["acceptance_sha256"]),
                          ("dataset_revision", manifest["revision"]),
                          ("candidate_status", candidate["candidate_status"])):
        if metadata.get(key) != expected:
            raise ValueError(f"ungraded candidate has wrong {key}")
    if fingerprint(source) != task["input_sha256"]:
        raise ValueError("ungraded candidate input changed")
    for key, data in (("patch_sha256", patch), ("prompt_sha256", prompt),
                      ("trace_sha256", trace_bytes), ("stderr_sha256", stderr_bytes)):
        if candidate.get(key) != hashlib.sha256(data).hexdigest():
            raise ValueError(f"ungraded candidate {key} changed")
    config_sha = fingerprint({"argv": invocation["argv"],
                              "rates": invocation["rates_usd_per_million"],
                              "timeout": invocation["timeout_seconds"]})
    if candidate.get("config_sha256") != config_sha or candidate.get("patch_bytes") != len(patch):
        raise ValueError("ungraded candidate invocation or patch changed")
    failure = executor_failure(trace, stderr, candidate.get("exit_code"), len(patch))
    expected_status = "executor_error" if failure else "unverified_candidate" if patch else "empty_patch"
    if candidate.get("candidate_status") != expected_status or candidate.get("executor_failure") != failure:
        raise ValueError("ungraded candidate executor status changed")
    usage = usage_from_trace(trace)
    cost = price_usd(usage, invocation["rates_usd_per_million"])
    wall = candidate.get("wall_seconds")
    if candidate.get("usage") != usage or isinstance(wall, bool) or \
            not isinstance(wall, (int, float)) or not math.isfinite(wall) or wall < 0 or \
            not isinstance(candidate.get("cost_usd"), (int, float)) or \
            not math.isclose(candidate["cost_usd"], cost, rel_tol=0, abs_tol=1e-9):
        raise ValueError("ungraded candidate usage or cost changed")
    return {"status": expected_status, "observed_cost_usd": cost,
            "candidate_wall_seconds": wall,
            "observed_wall_seconds": None if (attempt_dir / "gate").exists() else wall,
            "input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"]}


def ungraded_attempts(manifest: dict, records: list[dict], artifacts: Path,
                      arms: tuple[str, ...]) -> list[dict]:
    graded = {(r["task_id"], r["arm"], r["attempt"]) for r in records}
    found = []
    for task in manifest["tasks"]:
        for arm in arms:
            parent = artifacts / task["split"] / task["id"] / arm
            if not parent.is_dir():
                continue
            for attempt_dir in sorted(parent.iterdir()):
                if not attempt_dir.is_dir() or not attempt_dir.name.isdecimal():
                    continue
                attempt = int(attempt_dir.name)
                if (task["id"], arm, attempt) in graded:
                    continue
                try:
                    observed = _ungraded_candidate_cost(attempt_dir, task, manifest, arm, attempt)
                except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
                    observed = {"status": "incomplete_or_invalid_artifacts",
                                "observed_cost_usd": None,
                                "candidate_wall_seconds": None,
                                "observed_wall_seconds": None,
                                "input_tokens": None, "output_tokens": None}
                found.append({"task_id": task["id"], "arm": arm,
                              "attempt": attempt, **observed})
    return found


def wilson(successes: int, total: int, z: float = 1.96) -> list[float]:
    if total == 0:
        return [0.0, 1.0]
    p = successes / total
    d = 1 + z * z / total
    center = (p + z * z / (2 * total)) / d
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return [max(0.0, center - radius), min(1.0, center + radius)]


def paired_success(manifest: dict, cells: dict[tuple[str, str], list[dict]],
                   control: str, treatment: str) -> dict | None:
    """Fixed-seed paired bootstrap; no estimate from a partial task matrix."""
    task_ids = [task["id"] for task in manifest["tasks"]]
    if any((task_id, arm) not in cells for task_id in task_ids
           for arm in (control, treatment)):
        return None
    differences = []
    control_only = treatment_only = 0
    for task_id in task_ids:
        c = any(r["gate"]["passed"] for r in cells[(task_id, control)])
        t = any(r["gate"]["passed"] for r in cells[(task_id, treatment)])
        differences.append(int(t) - int(c))
        control_only += int(c and not t)
        treatment_only += int(t and not c)
    rng = random.Random(20261009)
    n = len(differences)
    boot = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n
                  for _ in range(10000))
    return {"control": control, "treatment": treatment, "tasks": n,
            "success_rate_difference": sum(differences) / n,
            "difference_95pct_paired_bootstrap": [boot[250], boot[9749]],
            "control_only_successes": control_only,
            "treatment_only_successes": treatment_only,
            "statistically_positive": boot[250] > 0}


def summarize(manifest: dict, records: list[dict], artifacts: Path,
              *, stage: str = "final") -> dict:
    validate_manifest_shape(manifest)
    if stage not in STAGES:
        raise ValueError(f"unknown comparison stage: {stage}")
    arms = STAGES[stage]
    for record in records:
        validate_attempt(record, manifest, artifacts)
    keys = [(record["task_id"], record["arm"], record["attempt"]) for record in records]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate attempt in report")
    expected = {(task["id"], arm) for task in manifest["tasks"] for arm in arms}
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        cells[(record["task_id"], record["arm"])].append(record)
    missing = sorted(expected - set(cells))
    ungraded = ungraded_attempts(manifest, records, artifacts, arms)
    result = {"schema": "athena.self-improve.report/1",
              "manifest_sha256": fingerprint(manifest),
              "stage": stage,
              "complete": not missing and not ungraded,
              "missing": [{"task_id": t, "arm": a} for t, a in missing],
              "ungraded_attempts": ungraded,
              "arms": {}}
    for arm in arms:
        arm_cells = [attempts for (task_id, a), attempts in cells.items() if a == arm]
        arm_ungraded = [item for item in ungraded if item["arm"] == arm]
        completed = sum(any(r["gate"]["passed"] for r in attempts) for attempts in arm_cells)
        graded_cost = sum(r["cost_usd"] for attempts in arm_cells for r in attempts)
        observed_cost = sum(item["observed_cost_usd"] for item in arm_ungraded
                            if item["observed_cost_usd"] is not None)
        cost_complete = all(item["observed_cost_usd"] is not None for item in arm_ungraded)
        spent = graded_cost + observed_cost if cost_complete else None
        graded_wall = sum(r["total_wall_seconds"] for attempts in arm_cells for r in attempts)
        graded_candidate_wall = sum(r["wall_seconds"] for attempts in arm_cells
                                    for r in attempts)
        graded_gate_wall = sum(r["gate_wall_seconds"] for attempts in arm_cells
                               for r in attempts)
        observed_candidate_wall = sum(item["candidate_wall_seconds"] for item in arm_ungraded
                                       if item["candidate_wall_seconds"] is not None)
        observed_wall = sum(item["observed_wall_seconds"] for item in arm_ungraded
                            if item["observed_wall_seconds"] is not None)
        time_complete = all(item["observed_wall_seconds"] is not None for item in arm_ungraded)
        elapsed = graded_wall + observed_wall if time_complete else None
        failures = Counter(r["failure_reason"] for attempts in arm_cells
                           for r in attempts if r["failure_reason"])
        failures.update(f"ungraded:{item['status']}" for item in arm_ungraded)
        graded_input = sum(r["input_tokens"] for attempts in arm_cells for r in attempts)
        graded_output = sum(r["output_tokens"] for attempts in arm_cells for r in attempts)
        observed_input = sum(item["input_tokens"] for item in arm_ungraded
                             if item["input_tokens"] is not None)
        observed_output = sum(item["output_tokens"] for item in arm_ungraded
                              if item["output_tokens"] is not None)
        tokens_complete = all(item["input_tokens"] is not None and
                              item["output_tokens"] is not None for item in arm_ungraded)
        result["arms"][arm] = {
            "evaluated_tasks": len(arm_cells), "verified_successes": completed,
            "attempts": sum(len(attempts) for attempts in arm_cells) + len(arm_ungraded),
            "total_cost_usd": spent, "total_wall_seconds": elapsed,
            "candidate_wall_seconds": graded_candidate_wall + observed_candidate_wall,
            "gate_wall_seconds": graded_gate_wall,
            "wall_lower_bound_seconds": graded_wall + observed_candidate_wall,
            "cost_lower_bound_usd": graded_cost + observed_cost,
            "cost_complete": cost_complete, "time_complete": time_complete,
            "input_tokens": graded_input + observed_input if tokens_complete else None,
            "output_tokens": graded_output + observed_output if tokens_complete else None,
            "input_tokens_lower_bound": graded_input + observed_input,
            "output_tokens_lower_bound": graded_output + observed_output,
            "tokens_complete": tokens_complete,
            "cost_per_verified_success_usd": spent / completed if completed and spent is not None else None,
            "seconds_per_verified_success": elapsed / completed if completed and elapsed is not None else None,
            "verified_success_rate": completed / len(arm_cells) if arm_cells else None,
            "success_rate_95pct_wilson": wilson(completed, len(arm_cells)),
            "failure_reasons": dict(sorted(failures.items())),
        }
    control, treatment = ("codex", "codex_athena") if stage == "baseline" else \
                         ("codex_athena", "codex_athena_optimizer")
    result["paired_comparison"] = paired_success(manifest, cells, control, treatment) \
        if result["complete"] else None
    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--stage", choices=tuple(STAGES), default="final")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = summarize(manifest, load_attempts(args.attempts, manifest, args.artifacts),
                       args.artifacts,
                       stage=args.stage)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
