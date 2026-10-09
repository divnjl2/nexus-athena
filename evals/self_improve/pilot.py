"""Plan the pilot or run one isolated, unverified Codex candidate.

The separate official SWE-bench harness must judge candidate.patch afterwards.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from .codex_driver import run_codex
from .corpus import ARMS, acceptance, fingerprint, inputs, load_pinned, verify
from .evidence import file_sha256, validate_attempt
from .gate_adapter import run_harness
from .workspaces import cells, prepare

BASE_PROMPT = """Fix the GitHub issue below in this repository checkout.
Do the needed code and test changes, run relevant local checks, and stop when done.
The independent benchmark will judge the resulting patch. Your final claim is not
an acceptance result.

Repository: {repo}
Issue:
{problem_statement}
{hints}
"""

ATHENA_PREFIX = """Use the Athena engineering workflow for this task. Read the
framework CORE.md and CLAUDE.md at {athena_root}; use
`python {athena_root}/athena.py` for its contract, scenario, plan and check commands.
Create task-specific contract and executable scenarios in this checkout, implement
the issue, and run the relevant Athena checks. Do not edit the framework's CORE.md
or AGENTS.md. Existing requirements and independent tests remain binding.

"""


def prompt_for(row: dict, arm: str, *, athena_root: Path,
               optimizer_instructions: str = "") -> str:
    if arm not in ARMS:
        raise ValueError("unknown arm")
    issue = inputs(row)
    base = BASE_PROMPT.format(repo=row["repo"],
                              problem_statement=issue["problem_statement"],
                              hints=("Maintainer hints:\n" + issue["hints_text"])
                              if issue["hints_text"] else "")
    if arm == "codex":
        if optimizer_instructions:
            raise ValueError("optimizer instructions cannot enter the baseline arm")
        return base
    prefix = ATHENA_PREFIX.format(athena_root=athena_root.as_posix())
    if arm == "codex_athena":
        if optimizer_instructions:
            raise ValueError("optimizer instructions cannot enter the Athena baseline arm")
        return prefix + base
    if not optimizer_instructions.strip():
        raise ValueError("optimizer arm requires frozen candidate instructions")
    return prefix + optimizer_instructions.strip() + "\n\n" + base


def authorize_split(manifest: dict, task: dict, arm: str,
                    optimizer_instructions: str, promotion: dict | None,
                    evidence_root: Path) -> None:
    """A holdout optimizer run needs a frozen, matching candidate decision."""
    if arm != "codex_athena_optimizer" or task["split"] != "holdout":
        return
    expected = {"schema": "athena.self-improve.promotion/1",
                "manifest_sha256": fingerprint(manifest),
                "instructions_sha256": hashlib.sha256(
                    optimizer_instructions.encode("utf-8")).hexdigest()}
    if not isinstance(promotion, dict) or any(promotion.get(k) != v for k, v in expected.items()):
        raise ValueError("holdout requires a matching frozen optimizer promotion")
    expected_reports = (("baseline", "athena.self-improve.report/1"),
                        ("development", "athena.self-improve.development/1"))
    for name, schema in expected_reports:
        relative = Path(promotion.get(f"{name}_report", ""))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe {name} report path")
        path = (evidence_root / relative).resolve()
        if not path.is_relative_to(evidence_root.resolve()) or not path.is_file():
            raise ValueError(f"missing {name} report")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != promotion.get(f"{name}_report_sha256"):
            raise ValueError(f"altered {name} report")
        report = json.loads(data)
        if report.get("schema") != schema or not report.get("complete") or \
                report.get("manifest_sha256") != expected["manifest_sha256"]:
            raise ValueError(f"{name} report is incomplete or for another corpus")
        if name == "baseline" and report.get("stage") != "baseline":
            raise ValueError("baseline evidence is from the wrong stage")
        if name == "development" and report.get("instructions_sha256") != expected["instructions_sha256"]:
            raise ValueError("development evidence is for another candidate")


def run_one(*, manifest: dict, rows: list[dict], task_id: str, arm: str,
            attempt: int, root: Path, athena_root: Path, model: str,
            timeout: int, rates: dict[str, float], optimizer_instructions: str = "",
            promotion: dict | None = None) -> dict:
    """Run exactly one candidate; no acceptance data enters its workspace or prompt."""
    verify(manifest, rows)
    tasks = {task["id"]: task for task in manifest["tasks"]}
    source = {row["instance_id"]: row for row in rows}
    if task_id not in tasks or arm not in ARMS:
        raise ValueError("task or arm is outside the frozen matrix")
    task = tasks[task_id]
    authorize_split(manifest, task, arm, optimizer_instructions, promotion,
                    root / "reports")
    athena_version = None
    if arm != "codex":
        status = subprocess.run(["git", "status", "--porcelain"], cwd=athena_root,
                                capture_output=True, text=True, check=True)
        if status.stdout.strip():
            raise ValueError("Athena source tree must be clean before a comparison run")
        athena_version = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=athena_root, text=True).strip()
    cell = {"task_id": task_id, "repo": task["repo"],
            "base_commit": task["base_commit"], "split": task["split"], "arm": arm}
    prompt = prompt_for(source[task_id], arm, athena_root=athena_root,
                        optimizer_instructions=optimizer_instructions)
    workspace = prepare(cell, attempt=attempt, root=root)
    artifacts = root / "artifacts" / task["split"] / task_id / arm / str(attempt)
    result = run_codex(workspace, prompt=prompt, model=model, timeout=timeout,
                       artifacts=artifacts, rates=rates)
    (artifacts / "input.json").write_text(json.dumps(inputs(source[task_id]),
                                               ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    (artifacts / "attempt.json").write_text(json.dumps({
        "task_id": task_id, "arm": arm, "attempt": attempt,
        "dataset_revision": manifest["revision"],
        "manifest_sha256": fingerprint(manifest),
        "base_commit": task["base_commit"], "input_sha256": task["input_sha256"],
        "acceptance_sha256": task["acceptance_sha256"],
        "athena_commit": athena_version, "seed": None,
        "candidate_status": result["candidate_status"]}, indent=2) + "\n", encoding="utf-8")
    return {"task_id": task_id, "arm": arm, "attempt": attempt,
            "workspace": str(workspace), "artifacts": str(artifacts), **result}


def gate_one(*, manifest: dict, row: dict, task_id: str, arm: str, attempt: int,
             root: Path, timeout: int = 1800, wsl_distro: str | None = None,
             harness_python: str | None = None) -> dict:
    """Use official harness outside the agent workspace and freeze one attempt record."""
    tasks = {task["id"]: task for task in manifest["tasks"]}
    if task_id not in tasks or arm not in ARMS or attempt < 1:
        raise ValueError("task, arm or attempt is outside the frozen matrix")
    task = tasks[task_id]
    if row.get("instance_id") != task_id or row.get("base_commit") != task["base_commit"] or \
            fingerprint(inputs(row)) != task["input_sha256"] or \
            fingerprint(acceptance(row)) != task["acceptance_sha256"]:
        raise ValueError("acceptance row differs from the frozen corpus")
    artifacts_root = root / "artifacts"
    attempt_dir = artifacts_root / task["split"] / task_id / arm / str(attempt)
    candidate = json.loads((attempt_dir / "candidate.json").read_text(encoding="utf-8"))
    metadata = json.loads((attempt_dir / "attempt.json").read_text(encoding="utf-8"))
    patch = (attempt_dir / "candidate.patch").read_bytes()
    if candidate["patch_sha256"] != hashlib.sha256(patch).hexdigest():
        raise ValueError("candidate patch is altered")
    if file_sha256(attempt_dir / "prompt.txt") != candidate.get("prompt_sha256"):
        raise ValueError("candidate prompt bytes are altered")
    for name, key in (("trace.jsonl", "trace_sha256"),
                      ("stderr.txt", "stderr_sha256")):
        if file_sha256(attempt_dir / name) != candidate.get(key):
            raise ValueError(f"candidate {name} bytes are altered")
    expected_status = "unverified_candidate" if patch else "empty_patch"
    if candidate.get("candidate_status") != expected_status or candidate.get("executor_failure"):
        raise ValueError("candidate status disagrees with patch")
    if metadata["manifest_sha256"] != fingerprint(manifest) or \
            metadata["task_id"] != task_id or metadata["arm"] != arm:
        raise ValueError("candidate metadata is for another task or corpus")
    model_name = f"{arm}_{attempt}"
    envelope = run_harness(task_id=task_id, arm=arm, attempt=attempt,
                           model_name=model_name, patch=patch, row=row,
                           workdir=root / "harness", gate_dir=attempt_dir / "gate",
                           timeout=timeout, wsl_distro=wsl_distro,
                           harness_python=harness_python)
    gate_path = attempt_dir / "gate" / "gate.json"
    record = {"schema": "athena.self-improve.attempt/1",
              "run_id": envelope["run_id"], "task_id": task_id, "arm": arm,
              "attempt": attempt, "manifest_sha256": fingerprint(manifest),
              "base_commit": task["base_commit"],
              "input_sha256": task["input_sha256"],
              "acceptance_sha256": task["acceptance_sha256"],
              "dataset_revision": manifest["revision"],
              "model": candidate["model"], "model_version": candidate["model"],
              "model_resolution": "requested_identifier",
              "codex_cli_version": candidate["codex_cli_version"],
              "athena_commit": metadata["athena_commit"],
              "cost_basis": candidate["cost_basis"],
              "prompt_sha256": candidate["prompt_sha256"],
              "trace_sha256": candidate["trace_sha256"],
              "stderr_sha256": candidate["stderr_sha256"],
              "config_sha256": candidate["config_sha256"],
              "seed": metadata["seed"],
              "started_at": candidate["started_at"],
              "ended_at": candidate["ended_at"],
              "input_tokens": candidate["usage"]["input_tokens"],
              "output_tokens": candidate["usage"]["output_tokens"],
              "wall_seconds": candidate["wall_seconds"],
              "gate_wall_seconds": envelope["gate_wall_seconds"],
              "total_wall_seconds": candidate["wall_seconds"] + envelope["gate_wall_seconds"],
              "cost_usd": candidate["cost_usd"],
              "patch_sha256": candidate["patch_sha256"],
              "failure_reason": None if envelope["resolved"] else
                                ("empty patch" if not patch else "official harness unresolved"),
              "gate": {"runner": "swebench-harness",
                       "artifact": str(gate_path.relative_to(artifacts_root)).replace("\\", "/"),
                       "sha256": file_sha256(gate_path),
                       "passed": envelope["resolved"]}}
    validate_attempt(record, manifest, artifacts_root)
    record_dir = root / "records"
    record_dir.mkdir(parents=True, exist_ok=True)
    with (record_dir / f"{record['run_id']}.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "candidate", "gate"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--stage", choices=("baseline", "optimizer"), default="baseline")
    parser.add_argument("--task")
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--athena-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--price-card", type=Path)
    parser.add_argument("--optimizer-instructions", type=Path)
    parser.add_argument("--promotion", type=Path,
                        help="frozen candidate decision required for optimizer holdout runs")
    parser.add_argument("--wsl-distro", help="run the pinned official harness in this WSL distro")
    parser.add_argument("--harness-python", help="Python executable with SWE-bench 5.0.2")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows = load_pinned()
    verify(manifest, rows)
    if args.action == "plan":
        planned = cells(manifest, stage=args.stage)
        print(json.dumps({"stage": args.stage, "cells": planned}, indent=2))
        return 0
    if args.action == "gate":
        if not all((args.task, args.arm, args.root)):
            parser.error("gate requires --task --arm --root")
        source = {row["instance_id"]: row for row in rows}
        if args.task not in source:
            parser.error("task is outside the pinned source dataset")
        record = gate_one(manifest=manifest, row=source[args.task],
                          task_id=args.task, arm=args.arm,
                          attempt=args.attempt, root=args.root, timeout=args.timeout,
                          wsl_distro=args.wsl_distro,
                          harness_python=args.harness_python)
        print(json.dumps(record, indent=2))
        return 0 if record["gate"]["passed"] else 1
    if not all((args.task, args.arm, args.root, args.model, args.price_card)):
        parser.error("candidate requires --task --arm --root --model --price-card")
    allowed = {cell["arm"] for cell in cells(manifest, stage=args.stage)}
    if args.arm not in allowed:
        parser.error("arm is outside the requested stage")
    optimizer_text = (args.optimizer_instructions.read_text(encoding="utf-8")
                      if args.optimizer_instructions else "")
    result = run_one(manifest=manifest, rows=rows, task_id=args.task, arm=args.arm,
                     attempt=args.attempt, root=args.root, athena_root=args.athena_root,
                     model=args.model, timeout=args.timeout,
                     rates=json.loads(args.price_card.read_text(encoding="utf-8")),
                     optimizer_instructions=optimizer_text,
                     promotion=(json.loads(args.promotion.read_text(encoding="utf-8"))
                                if args.promotion else None))
    print(json.dumps(result, indent=2))
    return 0 if result["candidate_status"] in ("empty_patch", "unverified_candidate") else 1


if __name__ == "__main__":
    raise SystemExit(main())
