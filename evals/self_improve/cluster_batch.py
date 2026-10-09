"""Resume a bounded two-arm development comparison on owner-cluster inference.

Only official, revalidated records are skipped. A preserved complete candidate
can be graded; a partial candidate, executor error or partial gate stops work
for review. No attempt is silently retried.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .baseline_batch import frozen_commit
from .cluster_pilot import ARMS, bridge_url as normalize_bridge_url, run_candidate, run_gate
from .cluster_report import load_records, summarize_cluster
from .corpus import load_pinned, verify


REQUIRED_CANDIDATE = ("candidate.json", "candidate.patch", "attempt.json",
                      "input.json", "prompt.txt", "invocation.json",
                      "route_probe.json", "trace.jsonl", "stderr.txt")


def cell_action(task: dict, arm: str, known: set[tuple[str, str]], root: Path) -> str:
    """Choose a safe continuation without reusing an attempt number."""
    key = (task["id"], arm)
    parent = root / "artifacts" / task["split"] / task["id"] / arm
    existing = [path for path in parent.iterdir() if path.is_dir() and
                path.name.isdecimal()] if parent.is_dir() else []
    if key in known:
        if any(path.name != "1" for path in existing):
            raise RuntimeError(f"ungraded extra attempt requires review: {task['id']} {arm}")
        return "skip"
    if not existing:
        return "candidate"
    if len(existing) != 1 or existing[0].name != "1":
        raise RuntimeError(f"multiple or renumbered attempts require review: {task['id']} {arm}")
    attempt_dir = existing[0]
    if not all((attempt_dir / name).is_file() for name in REQUIRED_CANDIDATE):
        raise RuntimeError(f"partial candidate artifacts require review: {task['id']} {arm}")
    if (attempt_dir / "gate").exists() or (attempt_dir / "gate_started.json").exists():
        raise RuntimeError(f"unfinished gate requires review: {task['id']} {arm}")
    candidate = json.loads((attempt_dir / "candidate.json").read_text(encoding="utf-8"))
    if candidate.get("candidate_status") not in ("empty_patch", "unverified_candidate") or \
            candidate.get("executor_failure"):
        raise RuntimeError(f"executor error requires review: {task['id']} {arm}")
    return "gate"


def write_report(manifest: dict, root: Path) -> dict:
    report = summarize_cluster(manifest, load_records(root, manifest), root)
    output = root / "reports" / "development.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return report


def run_batch(*, manifest: dict, rows: list[dict], root: Path, athena_root: Path,
              athena_commit: str, model: str, bridge_url: str, key_file: Path,
              probe_report: Path, context_window: int, candidate_timeout: int,
              gate_timeout: int, wsl_distro: str, harness_python: str,
              max_pairs: int = 1) -> dict:
    verify(manifest, rows)
    frozen_commit(athena_root, athena_commit)
    if max_pairs < 1:
        raise ValueError("max_pairs must be positive")
    bridge_url = normalize_bridge_url(bridge_url)
    source = {row["instance_id"]: row for row in rows}
    records = load_records(root, manifest)
    known = {(record["task_id"], record["arm"]) for record in records}
    for record in records:
        task = next(task for task in manifest["tasks"] if task["id"] == record["task_id"])
        invocation = json.loads((root / "artifacts" / task["split"] / task["id"] /
                                 record["arm"] / str(record["attempt"]) /
                                 "invocation.json").read_text(encoding="utf-8"))
        if record["model"] != model or record["bridge_url"] != bridge_url or \
                invocation["context_window"] != context_window or \
                (record["arm"] == "codex_athena" and
                 record["athena_commit"] != athena_commit):
            raise ValueError("existing cluster records use another fixed configuration")
    tasks = [task for task in manifest["tasks"] if task["split"] == "development"]
    write_report(manifest, root)
    started_pairs = 0
    for task in tasks:
        if all((task["id"], arm) in known for arm in ARMS):
            for arm in ARMS:
                cell_action(task, arm, known, root)
            continue
        if started_pairs >= max_pairs:
            break
        started_pairs += 1
        for arm in ARMS:
            action = cell_action(task, arm, known, root)
            if action == "skip":
                continue
            print(json.dumps({"task_id": task["id"], "arm": arm,
                              "action": action}), flush=True)
            if action == "candidate":
                result = run_candidate(manifest=manifest, rows=rows,
                                       task_id=task["id"], arm=arm, attempt=1,
                                       root=root, athena_root=athena_root, model=model,
                                       base_url=bridge_url, key_file=key_file,
                                       probe_report=probe_report,
                                       context_window=context_window,
                                       timeout=candidate_timeout)
                if result["candidate_status"] not in ("empty_patch", "unverified_candidate"):
                    raise RuntimeError(f"cluster executor error: {task['id']} {arm}")
            record = run_gate(manifest=manifest, row=source[task["id"]],
                              task_id=task["id"], arm=arm, attempt=1, root=root,
                              timeout=gate_timeout, wsl_distro=wsl_distro,
                              harness_python=harness_python)
            known.add((task["id"], arm))
            print(json.dumps({"task_id": task["id"], "arm": arm,
                              "resolved": record["gate"]["passed"],
                              "cost_usd": None}), flush=True)
        write_report(manifest, root)
    return write_report(manifest, root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--athena-root", type=Path, required=True)
    parser.add_argument("--athena-commit", required=True)
    parser.add_argument("--model", default="agent")
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8777/v1")
    parser.add_argument("--client-key-file", type=Path, required=True)
    parser.add_argument("--probe-report", type=Path, required=True)
    parser.add_argument("--context-window", type=int, default=65536)
    parser.add_argument("--candidate-timeout", type=int, default=900)
    parser.add_argument("--gate-timeout", type=int, default=1800)
    parser.add_argument("--wsl-distro", required=True)
    parser.add_argument("--harness-python", required=True)
    parser.add_argument("--max-pairs", type=int, default=1)
    args = parser.parse_args()
    result = run_batch(manifest=json.loads(args.manifest.read_text(encoding="utf-8")),
                       rows=load_pinned(), root=args.root.resolve(),
                       athena_root=args.athena_root.resolve(),
                       athena_commit=args.athena_commit, model=args.model,
                       bridge_url=args.bridge_url, key_file=args.client_key_file,
                       probe_report=args.probe_report,
                       context_window=args.context_window,
                       candidate_timeout=args.candidate_timeout,
                       gate_timeout=args.gate_timeout, wsl_distro=args.wsl_distro,
                       harness_python=args.harness_python, max_pairs=args.max_pairs)
    print(json.dumps({"complete": result["complete"],
                      "missing_cells": len(result["missing"]),
                      "ungraded_attempts": len(result["ungraded_attempts"])}), flush=True)
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
