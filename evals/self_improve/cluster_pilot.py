"""Run one isolated SWE-bench task through the owner's inference cluster.

This lane has its own schema and artifact root. Cluster inference has no measured
USD cost yet, so it cannot silently enter the priced Codex baseline matrix.
Only the official SWE-bench harness can mark a candidate as resolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .codex_driver import candidate_patch, executor_failure, usage_from_trace
from .corpus import acceptance, fingerprint, inputs, load_pinned, verify
from .evidence import file_sha256
from .gate_adapter import official_verdict, run_harness
from .pilot import prompt_for
from .workspaces import prepare


CLUSTER_SCHEMA = "athena.self-improve.cluster-attempt/1"
ARMS = ("codex", "codex_athena")


def _contained_file(base: Path, name: str) -> Path:
    relative = Path(name)
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe cluster evidence path")
    result = (base / relative).resolve()
    if not result.is_relative_to(base.resolve()) or not result.is_file():
        raise ValueError("cluster evidence file missing or outside artifact root")
    return result


def bridge_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or \
            parsed.path.rstrip("/") != "/v1" or parsed.username or parsed.password or \
            parsed.query or parsed.fragment:
        raise ValueError("cluster Codex provider must use a loopback /v1 bridge")
    return base_url.rstrip("/")


def cluster_argv(codex_bin: str, workspace: Path, *, model: str,
                 base_url: str, context_window: int, platform: str | None = None) -> list[str]:
    """Keep a custom provider and its context separate from the cloud baseline."""
    base_url = bridge_url(base_url)
    if not model or context_window < 8192:
        raise ValueError("model and context window of at least 8192 are required")
    compact = context_window * 3 // 4
    cmd = [codex_bin, "exec", "--json", "--ephemeral", "--ignore-user-config",
           "-c", 'model_provider="athena_cluster_bridge"',
           "-c", 'model_providers.athena_cluster_bridge.name="Athena Cluster Bridge"',
           "-c", f'model_providers.athena_cluster_bridge.base_url={json.dumps(base_url)}',
           "-c", 'model_providers.athena_cluster_bridge.env_key="ATHENA_BRIDGE_CLIENT_KEY"',
           "-c", 'model_providers.athena_cluster_bridge.wire_api="responses"',
           "-c", "model_providers.athena_cluster_bridge.supports_websockets=false",
           "-c", f"model_context_window={context_window}",
           "-c", f"model_auto_compact_token_limit={compact}"]
    if (platform or os.name) == "nt":
        cmd.extend(["-c", "windows.sandbox=elevated"])
    return [*cmd, "--sandbox", "workspace-write", "--model", model,
            "--cd", str(workspace), "-"]


def _qualifying_probe(path: Path, model: str, base_url: str) -> tuple[bytes, dict]:
    data = path.read_bytes()
    report = json.loads(data)
    checked = datetime.fromisoformat(report["checked_at"])
    if checked.tzinfo is None:
        raise ValueError("cluster route probe has no timezone")
    age = datetime.now(timezone.utc) - checked
    if age > timedelta(hours=24) or age < -timedelta(minutes=5):
        raise ValueError("cluster route probe is stale")
    if report.get("schema") != "athena.cluster-probe/1" or \
            report.get("passed") is not True or report.get("requested_model") != model or \
            report.get("gateway") != base_url or \
            not all(report.get("checks", {}).get(key) is True for key in
                    ("sse_terminal", "text", "function_call", "replayed_tool_result")):
        raise ValueError("cluster route probe does not qualify this provider")
    return data, report


def run_candidate(*, manifest: dict, rows: list[dict], task_id: str, arm: str,
                  attempt: int, root: Path, athena_root: Path, model: str,
                  base_url: str, key_file: Path, probe_report: Path,
                  context_window: int = 65536, timeout: int = 900,
                  codex_bin: str = "codex") -> dict:
    """Capture a cluster candidate without assigning an acceptance verdict."""
    verify(manifest, rows)
    tasks = {task["id"]: task for task in manifest["tasks"]}
    source = {row["instance_id"]: row for row in rows}
    if task_id not in tasks or arm not in ARMS or attempt < 1 or timeout < 1:
        raise ValueError("task, arm, attempt or timeout is outside the cluster lane")
    base_url = bridge_url(base_url)
    probe_bytes, probe_evidence = _qualifying_probe(probe_report, model, base_url)
    key = key_file.read_text(encoding="utf-8").strip()
    if not key:
        raise ValueError("bridge client key is empty")
    task = tasks[task_id]
    athena_commit = None
    if arm == "codex_athena":
        status = subprocess.run(["git", "status", "--porcelain"], cwd=athena_root,
                                capture_output=True, text=True, check=True)
        if status.stdout.strip():
            raise ValueError("Athena source tree must be clean")
        athena_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=athena_root, text=True).strip()
    cell = {"task_id": task_id, "repo": task["repo"],
            "base_commit": task["base_commit"], "split": task["split"], "arm": arm}
    prompt = prompt_for(source[task_id], arm, athena_root=athena_root)
    workspace = prepare(cell, attempt=attempt, root=root)
    artifacts = root / "artifacts" / task["split"] / task_id / arm / str(attempt)
    artifacts.mkdir(parents=True, exist_ok=False)
    (artifacts / "prompt.txt").write_bytes(prompt.encode("utf-8"))
    (artifacts / "input.json").write_text(json.dumps(inputs(source[task_id]),
                                               ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
    (artifacts / "route_probe.json").write_bytes(probe_bytes)
    resolved_bin = shutil.which(codex_bin) or codex_bin
    version = subprocess.run([resolved_bin, "--version"], capture_output=True,
                             text=True, check=False).stdout.strip()
    cmd = cluster_argv(resolved_bin, workspace, model=model, base_url=base_url,
                       context_window=context_window)
    config = {"argv": cmd, "cwd": str(workspace), "timeout_seconds": timeout,
              "provider": "athena_cluster_bridge", "bridge_url": base_url,
              "context_window": context_window, "probe_sha256": hashlib.sha256(probe_bytes).hexdigest()}
    (artifacts / "invocation.json").write_text(json.dumps(config, indent=2) + "\n",
                                                  encoding="utf-8")
    env = os.environ.copy()
    env["ATHENA_BRIDGE_CLIENT_KEY"] = key
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    trace_path = artifacts / "trace.jsonl"
    stderr_path = artifacts / "stderr.txt"
    with trace_path.open("wb") as trace_stream, stderr_path.open("wb") as stderr_stream:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=trace_stream,
                                stderr=stderr_stream, cwd=workspace, env=env)
        try:
            proc.communicate(input=prompt.encode("utf-8"), timeout=timeout)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            exit_code = 124
    elapsed = time.monotonic() - start
    ended_at = datetime.now(timezone.utc).isoformat()
    stdout = trace_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    patch = candidate_patch(workspace)
    (artifacts / "candidate.patch").write_bytes(patch)
    failure = executor_failure(stdout, stderr, exit_code, len(patch))
    try:
        usage = usage_from_trace(stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        usage = {"error": str(exc)}
    candidate = {"schema": "athena.cluster-candidate/1", "task_id": task_id,
                 "arm": arm, "attempt": attempt, "model": model,
                 "model_resolution": "requested_identifier",
                 "codex_cli_version": version, "provider": "athena_cluster_bridge",
                 "bridge_url": base_url, "route_probe_sha256": config["probe_sha256"],
                 "probe_checked_at": probe_evidence["checked_at"],
                 "probe_reported_models": probe_evidence.get("reported_models"),
                 "config_sha256": fingerprint(config),
                 "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                 "patch_sha256": hashlib.sha256(patch).hexdigest(),
                 "trace_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
                 "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
                 "patch_bytes": len(patch), "usage": usage,
                 "wall_seconds": elapsed, "started_at": started_at,
                 "ended_at": ended_at, "exit_code": exit_code,
                 "cost_usd": None, "cost_basis": "unpriced owner cluster inference",
                 "executor_failure": failure,
                 "candidate_status": ("executor_error" if failure else
                                      "empty_patch" if not patch else "unverified_candidate"),
                 "verified": False}
    (artifacts / "candidate.json").write_text(json.dumps(candidate, indent=2) + "\n",
                                                 encoding="utf-8")
    (artifacts / "attempt.json").write_text(json.dumps({
        "task_id": task_id, "arm": arm, "attempt": attempt,
        "manifest_sha256": fingerprint(manifest),
        "base_commit": task["base_commit"], "input_sha256": task["input_sha256"],
        "acceptance_sha256": task["acceptance_sha256"],
        "dataset_revision": manifest["revision"], "athena_commit": athena_commit,
        "seed": None}, indent=2) + "\n", encoding="utf-8")
    return {"workspace": str(workspace), "artifacts": str(artifacts), **candidate}


def run_gate(*, manifest: dict, row: dict, task_id: str, arm: str,
             attempt: int, root: Path, timeout: int = 1800,
             wsl_distro: str | None = None, harness_python: str | None = None) -> dict:
    """Grade one preserved cluster patch with the unchanged official harness."""
    tasks = {task["id"]: task for task in manifest["tasks"]}
    if task_id not in tasks or arm not in ARMS or attempt < 1:
        raise ValueError("task, arm or attempt outside cluster lane")
    task = tasks[task_id]
    if row.get("instance_id") != task_id or row.get("base_commit") != task["base_commit"] or \
            fingerprint(inputs(row)) != task["input_sha256"] or \
            fingerprint(acceptance(row)) != task["acceptance_sha256"]:
        raise ValueError("acceptance row differs from frozen corpus")
    artifacts_root = root / "artifacts"
    attempt_dir = artifacts_root / task["split"] / task_id / arm / str(attempt)
    candidate = json.loads((attempt_dir / "candidate.json").read_text(encoding="utf-8"))
    metadata = json.loads((attempt_dir / "attempt.json").read_text(encoding="utf-8"))
    patch = (attempt_dir / "candidate.patch").read_bytes()
    if candidate.get("schema") != "athena.cluster-candidate/1" or \
            candidate.get("task_id") != task_id or candidate.get("arm") != arm or \
            candidate.get("attempt") != attempt or \
            candidate.get("patch_sha256") != hashlib.sha256(patch).hexdigest() or \
            candidate.get("executor_failure") or \
            candidate.get("candidate_status") != ("unverified_candidate" if patch else "empty_patch"):
        raise ValueError("cluster candidate is incomplete or altered")
    prompt_bytes = (attempt_dir / "prompt.txt").read_bytes()
    invocation = json.loads((attempt_dir / "invocation.json").read_text(encoding="utf-8"))
    if candidate.get("prompt_sha256") != hashlib.sha256(prompt_bytes).hexdigest() or \
            candidate.get("config_sha256") != fingerprint(invocation) or \
            candidate.get("provider") != invocation.get("provider") or \
            candidate.get("bridge_url") != invocation.get("bridge_url") or \
            candidate.get("cost_usd", "missing") is not None:
        raise ValueError("cluster prompt, configuration or cost basis changed")
    trace = (attempt_dir / "trace.jsonl").read_text(encoding="utf-8")
    stderr = (attempt_dir / "stderr.txt").read_text(encoding="utf-8")
    if candidate.get("trace_sha256") != hashlib.sha256(trace.encode("utf-8")).hexdigest() or \
            candidate.get("stderr_sha256") != hashlib.sha256(stderr.encode("utf-8")).hexdigest() or \
            candidate.get("usage") != usage_from_trace(trace) or \
            executor_failure(trace, stderr, candidate.get("exit_code"), len(patch)) is not None:
        raise ValueError("cluster executor trace or usage changed")
    if metadata.get("manifest_sha256") != fingerprint(manifest) or \
            metadata.get("base_commit") != task["base_commit"] or \
            metadata.get("task_id") != task_id or metadata.get("arm") != arm or \
            metadata.get("attempt") != attempt:
        raise ValueError("cluster candidate metadata is for another task or corpus")
    probe_path = attempt_dir / "route_probe.json"
    if file_sha256(probe_path) != candidate["route_probe_sha256"]:
        raise ValueError("cluster route probe changed after the candidate")
    if fingerprint(inputs(row)) != fingerprint(json.loads(
            (attempt_dir / "input.json").read_text(encoding="utf-8"))):
        raise ValueError("cluster issue input changed after the candidate")
    envelope = run_harness(task_id=task_id, arm="cluster_" + arm, attempt=attempt,
                           model_name=f"cluster_{arm}_{attempt}", patch=patch, row=row,
                           workdir=root / "harness", gate_dir=attempt_dir / "gate",
                           timeout=timeout, wsl_distro=wsl_distro,
                           harness_python=harness_python)
    gate_path = attempt_dir / "gate" / "gate.json"
    official = attempt_dir / "gate" / envelope["official_report"]
    resolved = official_verdict(json.loads(official.read_text(encoding="utf-8")), task_id)
    record = {"schema": CLUSTER_SCHEMA, "task_id": task_id, "arm": arm,
              "attempt": attempt, "run_id": envelope["run_id"],
              "manifest_sha256": fingerprint(manifest),
              "base_commit": task["base_commit"],
              "input_sha256": task["input_sha256"],
              "acceptance_sha256": task["acceptance_sha256"],
              "dataset_revision": manifest["revision"],
              "athena_commit": metadata["athena_commit"],
              "model": candidate["model"], "model_resolution": "requested_identifier",
              "provider": candidate["provider"], "bridge_url": candidate["bridge_url"],
              "route_probe_sha256": candidate["route_probe_sha256"],
              "probe_checked_at": candidate["probe_checked_at"],
              "probe_reported_models": candidate["probe_reported_models"],
              "codex_cli_version": candidate["codex_cli_version"],
              "prompt_sha256": candidate["prompt_sha256"],
              "config_sha256": candidate["config_sha256"],
              "trace_sha256": candidate["trace_sha256"],
              "patch_sha256": candidate["patch_sha256"],
              "input_tokens": candidate["usage"]["input_tokens"],
              "output_tokens": candidate["usage"]["output_tokens"],
              "wall_seconds": candidate["wall_seconds"],
              "cost_usd": None, "cost_basis": candidate["cost_basis"],
              "started_at": candidate["started_at"], "ended_at": candidate["ended_at"],
              "seed": metadata["seed"],
              "failure_reason": None if resolved else
                                ("empty patch" if not patch else "official harness unresolved"),
              "gate": {"runner": "swebench-harness",
                       "artifact": str(gate_path.relative_to(artifacts_root)).replace("\\", "/"),
                       "sha256": file_sha256(gate_path), "passed": resolved}}
    validate_cluster_attempt(record, manifest, root)
    record_dir = root / "records"
    record_dir.mkdir(parents=True, exist_ok=True)
    with (record_dir / f"{record['run_id']}.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    return record


def validate_cluster_attempt(record: dict, manifest: dict, root: Path) -> None:
    """Re-read source, candidate, and official gate bytes before trusting a cell."""
    tasks = {task["id"]: task for task in manifest["tasks"]}
    task_id, arm, attempt = record.get("task_id"), record.get("arm"), record.get("attempt")
    if record.get("schema") != CLUSTER_SCHEMA or task_id not in tasks or \
            arm not in ARMS or type(attempt) is not int or attempt < 1:
        raise ValueError("unknown cluster attempt schema, task or arm")
    task = tasks[task_id]
    for field, expected in (("manifest_sha256", fingerprint(manifest)),
                            ("base_commit", task["base_commit"]),
                            ("input_sha256", task["input_sha256"]),
                            ("acceptance_sha256", task["acceptance_sha256"]),
                            ("dataset_revision", manifest["revision"]),
                            ("model_resolution", "requested_identifier"),
                            ("provider", "athena_cluster_bridge"),
                            ("cost_basis", "unpriced owner cluster inference")):
        if record.get(field) != expected:
            raise ValueError(f"cluster record has wrong {field}")
    if record.get("cost_usd", "missing") is not None:
        raise ValueError("cluster record cannot invent a USD cost")
    for field in ("input_tokens", "output_tokens", "wall_seconds"):
        value = record.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or \
                not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid cluster {field}")
    for field in ("started_at", "ended_at"):
        if not isinstance(record.get(field), str):
            raise ValueError(f"missing cluster {field}")
    started = datetime.fromisoformat(record["started_at"])
    ended = datetime.fromisoformat(record["ended_at"])
    if started.tzinfo is None or ended.tzinfo is None or ended < started:
        raise ValueError("invalid cluster attempt interval")
    artifacts = root / "artifacts"
    attempt_dir = artifacts / task["split"] / task_id / arm / str(attempt)
    candidate = json.loads(_contained_file(attempt_dir, "candidate.json").read_text(encoding="utf-8"))
    metadata = json.loads(_contained_file(attempt_dir, "attempt.json").read_text(encoding="utf-8"))
    invocation = json.loads(_contained_file(attempt_dir, "invocation.json").read_text(encoding="utf-8"))
    patch = _contained_file(attempt_dir, "candidate.patch").read_bytes()
    trace = _contained_file(attempt_dir, "trace.jsonl").read_text(encoding="utf-8")
    stderr = _contained_file(attempt_dir, "stderr.txt").read_text(encoding="utf-8")
    prompt = _contained_file(attempt_dir, "prompt.txt").read_bytes()
    probe = _contained_file(attempt_dir, "route_probe.json")
    source = json.loads(_contained_file(attempt_dir, "input.json").read_text(encoding="utf-8"))
    if metadata.get("manifest_sha256") != record["manifest_sha256"] or \
            metadata.get("base_commit") != task["base_commit"] or \
            metadata.get("input_sha256") != task["input_sha256"] or \
            metadata.get("acceptance_sha256") != task["acceptance_sha256"] or \
            metadata.get("dataset_revision") != manifest["revision"] or \
            metadata.get("athena_commit") != record.get("athena_commit") or \
            metadata.get("task_id") != task_id or metadata.get("arm") != arm or \
            metadata.get("attempt") != attempt or \
            fingerprint(source) != task["input_sha256"]:
        raise ValueError("cluster candidate input or framework revision changed")
    for field, expected in (("patch_sha256", hashlib.sha256(patch).hexdigest()),
                            ("prompt_sha256", hashlib.sha256(prompt).hexdigest()),
                            ("trace_sha256", hashlib.sha256(trace.encode()).hexdigest()),
                            ("stderr_sha256", hashlib.sha256(stderr.encode()).hexdigest()),
                            ("config_sha256", fingerprint(invocation)),
                            ("route_probe_sha256", file_sha256(probe))):
        if candidate.get(field) != expected or (field != "stderr_sha256" and
                                              record.get(field) != expected):
            raise ValueError(f"cluster {field} evidence changed")
    probe_report = json.loads(probe.read_text(encoding="utf-8"))
    if probe_report.get("schema") != "athena.cluster-probe/1" or \
            probe_report.get("passed") is not True or \
            probe_report.get("requested_model") != record.get("model") or \
            probe_report.get("gateway") != record.get("bridge_url") or \
            not all(probe_report.get("checks", {}).get(key) is True for key in
                    ("sse_terminal", "text", "function_call", "replayed_tool_result")):
        raise ValueError("cluster route probe does not establish the recorded model")
    if candidate.get("probe_checked_at") != probe_report.get("checked_at") or \
            record.get("probe_checked_at") != probe_report.get("checked_at") or \
            candidate.get("probe_reported_models") != probe_report.get("reported_models") or \
            record.get("probe_reported_models") != probe_report.get("reported_models"):
        raise ValueError("cluster probe model observation changed")
    if candidate.get("schema") != "athena.cluster-candidate/1" or \
            candidate.get("model_resolution") != record["model_resolution"] or \
            candidate.get("provider") != record["provider"] or \
            candidate.get("codex_cli_version") != record.get("codex_cli_version") or \
            candidate.get("wall_seconds") != record["wall_seconds"] or \
            candidate.get("started_at") != record["started_at"] or \
            candidate.get("ended_at") != record["ended_at"] or \
            candidate.get("patch_bytes") != len(patch) or \
            candidate.get("verified") is not False or \
            invocation.get("probe_sha256") != record["route_probe_sha256"] or \
            invocation.get("context_window", 0) < 8192:
        raise ValueError("cluster candidate provenance or timing changed")
    if candidate.get("usage") != usage_from_trace(trace) or \
            record["input_tokens"] != candidate["usage"]["input_tokens"] or \
            record["output_tokens"] != candidate["usage"]["output_tokens"] or \
            candidate.get("cost_usd", "missing") is not None or \
            candidate.get("cost_basis") != record["cost_basis"] or \
            executor_failure(trace, stderr, candidate.get("exit_code"), len(patch)) is not None:
        raise ValueError("cluster usage, cost basis or executor status changed")
    if candidate.get("candidate_status") != ("unverified_candidate" if patch else "empty_patch") or \
            candidate.get("task_id") != task_id or candidate.get("arm") != arm or \
            candidate.get("attempt") != attempt or \
            record.get("model") != candidate.get("model") or \
            record.get("bridge_url") != candidate.get("bridge_url") or \
            invocation.get("provider") != record["provider"] or \
            invocation.get("bridge_url") != record["bridge_url"]:
        raise ValueError("cluster candidate identity changed")
    gate = record.get("gate")
    if not isinstance(gate, dict) or gate.get("runner") != "swebench-harness":
        raise ValueError("independent cluster gate is required")
    gate_path = _contained_file(artifacts, gate.get("artifact", ""))
    if file_sha256(gate_path) != gate.get("sha256"):
        raise ValueError("cluster gate envelope changed")
    envelope = json.loads(gate_path.read_text(encoding="utf-8"))
    if envelope.get("schema") != "athena.self-improve.gate/1" or \
            envelope.get("runner") != "swebench-harness" or \
            envelope.get("instance_id") != task_id or \
            envelope.get("patch_sha256") != record["patch_sha256"] or \
            envelope.get("run_id") != record.get("run_id") or \
            envelope.get("harness_version") != "5.0.2":
        raise ValueError("cluster gate does not bind task, patch and harness")
    official = _contained_file(gate_path.parent, envelope.get("official_report", ""))
    if file_sha256(official) != envelope.get("official_report_sha256"):
        raise ValueError("official cluster report changed")
    resolved = official_verdict(json.loads(official.read_text(encoding="utf-8")), task_id)
    if gate.get("passed") is not resolved or envelope.get("resolved") is not resolved or \
            (record.get("failure_reason") is None) is not resolved:
        raise ValueError("cluster gate verdict or failure reason changed")
    dataset_path = _contained_file(root / "harness", f"{record['run_id']}.dataset.json")
    if file_sha256(dataset_path) != envelope.get("dataset_sha256"):
        raise ValueError("cluster official dataset snapshot changed")
    snapshot = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, list) or len(snapshot) != 1 or \
            snapshot[0].get("instance_id") != task_id or \
            fingerprint(inputs(snapshot[0])) != task["input_sha256"] or \
            fingerprint(acceptance(snapshot[0])) != task["acceptance_sha256"]:
        raise ValueError("cluster gate used a different frozen task row")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("candidate", "gate"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--task", required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--athena-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--model", default="agent")
    parser.add_argument("--bridge-url", default="http://127.0.0.1:8777/v1")
    parser.add_argument("--client-key-file", type=Path)
    parser.add_argument("--probe-report", type=Path)
    parser.add_argument("--context-window", type=int, default=65536)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--wsl-distro")
    parser.add_argument("--harness-python")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows = load_pinned()
    verify(manifest, rows)
    root = args.root.resolve()
    if args.action == "candidate":
        if not args.client_key_file or not args.probe_report:
            parser.error("candidate needs --client-key-file and --probe-report")
        result = run_candidate(manifest=manifest, rows=rows, task_id=args.task,
                               arm=args.arm, attempt=args.attempt, root=root,
                               athena_root=args.athena_root.resolve(), model=args.model,
                               base_url=args.bridge_url, key_file=args.client_key_file,
                               probe_report=args.probe_report,
                               context_window=args.context_window, timeout=args.timeout)
        print(json.dumps(result, indent=2))
        return 0 if result["candidate_status"] in ("empty_patch", "unverified_candidate") else 2
    source = {row["instance_id"]: row for row in rows}
    if args.task not in source:
        parser.error("task is outside pinned dataset")
    result = run_gate(manifest=manifest, row=source[args.task], task_id=args.task,
                      arm=args.arm, attempt=args.attempt, root=root, timeout=args.timeout,
                      wsl_distro=args.wsl_distro, harness_python=args.harness_python)
    print(json.dumps(result, indent=2))
    return 0 if result["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
