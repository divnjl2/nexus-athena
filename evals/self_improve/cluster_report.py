"""Summarize independently graded cluster attempts without inventing a price.

The cluster lane is exploratory and separate from the priced three-arm pilot.
Candidate files without an official gate remain visible but do not become scores.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from .cluster_pilot import ARMS, validate_cluster_attempt
from .corpus import fingerprint, validate_manifest_shape
from .evidence import paired_success, wilson


def load_records(root: Path, manifest: dict) -> list[dict]:
    records, attempts, run_ids = [], set(), set()
    record_dir = root / "records"
    for path in sorted(record_dir.glob("*.json")) if record_dir.is_dir() else []:
        record = json.loads(path.read_text(encoding="utf-8"))
        try:
            validate_cluster_attempt(record, manifest, root)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"invalid cluster record {path.name}: {exc}") from exc
        key = (record["task_id"], record["arm"], record["attempt"])
        if path.stem != record["run_id"] or key in attempts or record["run_id"] in run_ids:
            raise ValueError(f"duplicate or misnamed cluster record {path.name}")
        attempts.add(key)
        run_ids.add(record["run_id"])
        records.append(record)
    return records


def ungraded_attempts(root: Path, tasks: list[dict], graded: set[tuple]) -> list[dict]:
    found = []
    for task in tasks:
        for arm in ARMS:
            parent = root / "artifacts" / task["split"] / task["id"] / arm
            if not parent.is_dir():
                continue
            for attempt_dir in sorted(parent.iterdir()):
                if not attempt_dir.is_dir() or not attempt_dir.name.isdecimal():
                    continue
                attempt = int(attempt_dir.name)
                if (task["id"], arm, attempt) in graded:
                    continue
                candidate_path = attempt_dir / "candidate.json"
                status = "incomplete_artifacts"
                if candidate_path.is_file():
                    try:
                        status = json.loads(candidate_path.read_text(encoding="utf-8"))[
                            "candidate_status"]
                    except (ValueError, KeyError, TypeError):
                        status = "invalid_candidate"
                found.append({"task_id": task["id"], "arm": arm,
                              "attempt": attempt, "status": status})
    return found


def summarize_cluster(manifest: dict, records: list[dict], root: Path,
                      *, split: str = "development") -> dict:
    validate_manifest_shape(manifest)
    if split not in ("development", "holdout"):
        raise ValueError("unknown cluster split")
    tasks = [task for task in manifest["tasks"] if task["split"] == split]
    if not tasks:
        raise ValueError("cluster split has no tasks")
    selected = {task["id"] for task in tasks}
    cells = defaultdict(list)
    for record in records:
        if record["task_id"] in selected:
            cells[(record["task_id"], record["arm"])].append(record)
    models = {record["model"] for record in records if record["task_id"] in selected}
    if len(models) > 1:
        raise ValueError("cluster comparison mixes requested model roles")
    expected = {(task["id"], arm) for task in tasks for arm in ARMS}
    missing = sorted(expected - set(cells))
    graded = {(record["task_id"], record["arm"], record["attempt"])
              for record in records}
    ungraded = ungraded_attempts(root, tasks, graded)
    result = {"schema": "athena.self-improve.cluster-report/1",
              "manifest_sha256": fingerprint(manifest), "split": split,
              "scope": "exploratory owner-cluster inference",
              "requested_model": next(iter(models)) if models else None,
              "complete": not missing and not ungraded,
              "missing": [{"task_id": task_id, "arm": arm} for task_id, arm in missing],
              "ungraded_attempts": ungraded,
              "cost_basis": "unpriced owner cluster inference",
              "total_cost_usd": None, "arms": {}}
    for arm in ARMS:
        arm_cells = [attempts for (task_id, name), attempts in cells.items() if name == arm]
        successes = sum(any(record["gate"]["passed"] for record in attempts)
                        for attempts in arm_cells)
        elapsed = sum(record["wall_seconds"] for attempts in arm_cells for record in attempts)
        failures = Counter(record["failure_reason"] for attempts in arm_cells
                           for record in attempts if record["failure_reason"])
        result["arms"][arm] = {
            "evaluated_tasks": len(arm_cells), "verified_successes": successes,
            "attempts": sum(map(len, arm_cells)),
            "input_tokens": sum(record["input_tokens"] for attempts in arm_cells
                                for record in attempts),
            "output_tokens": sum(record["output_tokens"] for attempts in arm_cells
                                 for record in attempts),
            "total_wall_seconds": elapsed,
            "verified_success_rate": successes / len(arm_cells) if arm_cells else None,
            "success_rate_95pct_wilson": wilson(successes, len(arm_cells))
            if arm_cells else None,
            "seconds_per_verified_success": elapsed / successes if successes else None,
            "total_cost_usd": None, "cost_per_verified_success_usd": None,
            "failure_reasons": dict(sorted(failures.items())),
        }
    result["paired_comparison"] = paired_success({"tasks": tasks}, cells, *ARMS) \
        if result["complete"] else None
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "holdout"), default="development")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.root.resolve()
    report = summarize_cluster(manifest, load_records(root, manifest), root, split=args.split)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
