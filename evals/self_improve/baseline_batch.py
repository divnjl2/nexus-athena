"""Resume the frozen two-arm baseline one task at a time.

Only completed, independently validated records are skipped. An interrupted
candidate is gated from its preserved patch; a partial candidate or an
infrastructure error stops the batch for review instead of silently retrying.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .corpus import load_pinned, verify
from .evidence import load_attempts, summarize
from .pilot import gate_one, run_one
from .workspaces import cells


def cell_action(cell: dict, known: set[tuple[str, str]], root: Path) -> str:
    key = (cell["task_id"], cell["arm"])
    parent = root / "artifacts" / cell["split"] / cell["task_id"] / cell["arm"]
    existing = [path for path in parent.iterdir() if path.is_dir() and
                path.name.isdecimal()] if parent.is_dir() else []
    if key in known:
        if any(path.name != "1" for path in existing):
            raise RuntimeError(f"ungraded extra attempt requires review: {cell['task_id']} {cell['arm']}")
        return "skip"
    if not existing:
        return "candidate"
    if len(existing) != 1 or existing[0].name != "1":
        raise RuntimeError(f"multiple or renumbered attempts require review: {cell['task_id']} {cell['arm']}")
    candidate = existing[0]
    required = ("candidate.json", "candidate.patch", "attempt.json", "input.json",
                "prompt.txt", "invocation.json", "trace.jsonl", "stderr.txt")
    if all((candidate / name).is_file() for name in required):
        if (candidate / "gate").exists() or (candidate / "gate_started.json").exists():
            raise RuntimeError(f"unfinished gate requires review: {cell['task_id']} {cell['arm']}")
        saved = json.loads((candidate / "candidate.json").read_text(encoding="utf-8"))
        if saved.get("candidate_status") not in ("empty_patch", "unverified_candidate") or \
                saved.get("executor_failure"):
            raise RuntimeError(f"executor error requires review: {cell['task_id']} {cell['arm']}")
        return "gate"
    raise RuntimeError(f"partial candidate artifacts require review: {cell['task_id']} {cell['arm']}")


def frozen_commit(root: Path, expected: str) -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root,
                                   text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=root,
                                     text=True).strip()
    if head != expected or status:
        raise ValueError("Athena reference must be clean at the frozen commit")


def write_report(manifest: dict, root: Path) -> dict:
    records_dir = root / "records"
    records = load_attempts(records_dir, manifest, root / "artifacts") \
        if records_dir.is_dir() else []
    report = summarize(manifest, records, root / "artifacts", stage="baseline")
    destination = root / "reports" / "partial-baseline.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def run_batch(*, manifest: dict, rows: list[dict], root: Path, athena_root: Path,
              athena_commit: str, model: str, rates: dict[str, float],
              candidate_timeout: int, gate_timeout: int, wsl_distro: str,
              harness_python: str, max_pairs: int | None = None) -> dict:
    verify(manifest, rows)
    frozen_commit(athena_root, athena_commit)
    source = {row["instance_id"]: row for row in rows}
    records = load_attempts(root / "records", manifest, root / "artifacts") \
        if (root / "records").is_dir() else []
    known = {(record["task_id"], record["arm"]) for record in records}
    for record in records:
        if record["model"] != model or (record["arm"] != "codex" and
                                        record["athena_commit"] != athena_commit):
            raise ValueError("existing baseline records use another model or Athena commit")
    planned = cells(manifest, stage="baseline")
    write_report(manifest, root)
    task_ids = list(dict.fromkeys(cell["task_id"] for cell in planned))
    started_pairs = 0
    for task_id in task_ids:
        pair = [cell for cell in planned if cell["task_id"] == task_id]
        if all((task_id, cell["arm"]) in known for cell in pair):
            for cell in pair:
                cell_action(cell, known, root)
            continue
        if max_pairs is not None and started_pairs >= max_pairs:
            break
        started_pairs += 1
        for cell in pair:
            arm = cell["arm"]
            action = cell_action(cell, known, root)
            if action == "skip":
                continue
            print(json.dumps({"task_id": task_id, "arm": arm,
                              "action": action}), flush=True)
            try:
                if action == "candidate":
                    result = run_one(manifest=manifest, rows=rows, task_id=task_id,
                                     arm=arm, attempt=1, root=root,
                                     athena_root=athena_root, model=model,
                                     timeout=candidate_timeout, rates=rates)
                    if result["candidate_status"] not in ("empty_patch", "unverified_candidate"):
                        raise RuntimeError(f"candidate executor error: {task_id} {arm}")
                record = gate_one(manifest=manifest, row=source[task_id],
                                  task_id=task_id, arm=arm, attempt=1, root=root,
                                  timeout=gate_timeout, wsl_distro=wsl_distro,
                                  harness_python=harness_python)
            except Exception:
                write_report(manifest, root)
                raise
            known.add((task_id, arm))
            print(json.dumps({"task_id": task_id, "arm": arm,
                              "resolved": record["gate"]["passed"],
                              "cost_usd": record["cost_usd"],
                              "wall_seconds": record["wall_seconds"]}), flush=True)
        report = write_report(manifest, root)
        print(json.dumps({"evaluated_pairs": report["arms"]["codex_athena"]["evaluated_tasks"],
                          "missing_cells": len(report["missing"])}), flush=True)
    return write_report(manifest, root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--athena-root", type=Path, required=True)
    parser.add_argument("--athena-commit", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--price-card", type=Path, required=True)
    parser.add_argument("--candidate-timeout", type=int, default=900)
    parser.add_argument("--gate-timeout", type=int, default=600)
    parser.add_argument("--wsl-distro", required=True)
    parser.add_argument("--harness-python", required=True)
    parser.add_argument("--max-pairs", type=int)
    args = parser.parse_args()
    if args.max_pairs is not None and args.max_pairs < 1:
        parser.error("--max-pairs must be positive")
    report = run_batch(manifest=json.loads(args.manifest.read_text(encoding="utf-8")),
                       rows=load_pinned(), root=args.root.resolve(),
                       athena_root=args.athena_root.resolve(),
                       athena_commit=args.athena_commit, model=args.model,
                       rates=json.loads(args.price_card.read_text(encoding="utf-8")),
                       candidate_timeout=args.candidate_timeout,
                       gate_timeout=args.gate_timeout, wsl_distro=args.wsl_distro,
                       harness_python=args.harness_python, max_pairs=args.max_pairs)
    print(json.dumps({"complete": report["complete"],
                      "missing_cells": len(report["missing"])}), flush=True)
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
