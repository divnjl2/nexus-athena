"""Validate immutable attempt records and summarize only complete pilot matrices.

This module reads evidence. It does not run or impersonate the acceptance harness.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from .corpus import ARMS, fingerprint

SCHEMA = "athena.self-improve.attempt/1"


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
    for key in ("run_id", "model", "model_version", "prompt_sha256",
                "config_sha256", "started_at", "ended_at", "patch_sha256"):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValueError(f"missing {key}")
    if "seed" not in record or "failure_reason" not in record:
        raise ValueError("seed and failure_reason must be recorded, even if null")
    for key in ("input_tokens", "output_tokens", "wall_seconds", "cost_usd"):
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid {key}")
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
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("instance_id") != record["task_id"] or report.get("patch_sha256") != record["patch_sha256"]:
        raise ValueError("gate report does not bind this task and patch")
    if not isinstance(report.get("resolved"), bool) or gate.get("passed") is not report["resolved"]:
        raise ValueError("gate verdict mismatch")
    if record["failure_reason"] is None and not gate["passed"]:
        raise ValueError("failed attempt needs a failure reason")


def load_attempts(path: Path, manifest: dict, artifacts: Path) -> list[dict]:
    records, keys, run_ids = [], set(), set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        record = json.loads(line)
        try:
            validate_attempt(record, manifest, artifacts)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"line {line_no}: {exc}") from exc
        key = (record["task_id"], record["arm"], record["attempt"])
        if key in keys or record["run_id"] in run_ids:
            raise ValueError(f"line {line_no}: duplicate attempt or run id")
        keys.add(key)
        run_ids.add(record["run_id"])
        records.append(record)
    return records


def wilson(successes: int, total: int, z: float = 1.96) -> list[float]:
    if total == 0:
        return [0.0, 1.0]
    p = successes / total
    d = 1 + z * z / total
    center = (p + z * z / (2 * total)) / d
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return [max(0.0, center - radius), min(1.0, center + radius)]


def summarize(manifest: dict, records: list[dict]) -> dict:
    expected = {(task["id"], arm) for task in manifest["tasks"] for arm in ARMS}
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        cells[(record["task_id"], record["arm"])].append(record)
    missing = sorted(expected - set(cells))
    result = {"schema": "athena.self-improve.report/1",
              "manifest_sha256": fingerprint(manifest),
              "complete": not missing, "missing": [{"task_id": t, "arm": a} for t, a in missing],
              "arms": {}}
    for arm in ARMS:
        arm_cells = [attempts for (task_id, a), attempts in cells.items() if a == arm]
        completed = sum(any(r["gate"]["passed"] for r in attempts) for attempts in arm_cells)
        spent = sum(r["cost_usd"] for attempts in arm_cells for r in attempts)
        elapsed = sum(r["wall_seconds"] for attempts in arm_cells for r in attempts)
        input_tokens = sum(r["input_tokens"] for attempts in arm_cells for r in attempts)
        output_tokens = sum(r["output_tokens"] for attempts in arm_cells for r in attempts)
        result["arms"][arm] = {
            "evaluated_tasks": len(arm_cells), "verified_successes": completed,
            "attempts": sum(len(attempts) for attempts in arm_cells),
            "total_cost_usd": spent, "total_wall_seconds": elapsed,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_per_verified_success_usd": spent / completed if completed else None,
            "seconds_per_verified_success": elapsed / completed if completed else None,
            "verified_success_rate": completed / len(arm_cells) if arm_cells else None,
            "success_rate_95pct_wilson": wilson(completed, len(arm_cells)),
        }
    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = summarize(manifest, load_attempts(args.attempts, manifest, args.artifacts))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
