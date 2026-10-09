"""Bind a candidate patch to an untouched official SWE-bench harness report."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HARNESS_VERSION = "5.0.2"


def _wsl_path(path: Path, distro: str) -> str:
    proc = subprocess.run(["wsl", "-d", distro, "--", "wslpath", "-a",
                           path.resolve().as_posix()], text=True, capture_output=True,
                          encoding="utf-8")
    if proc.returncode or not proc.stdout.strip():
        raise RuntimeError(f"cannot map path into WSL: {path}")
    return proc.stdout.strip()

def official_verdict(report: dict, task_id: str) -> bool:
    """Read a per-instance verdict or v5's single-task empty-patch result."""
    entry = report.get(task_id)
    if isinstance(entry, dict) and isinstance(entry.get("resolved"), bool):
        return entry["resolved"]
    if report.get("schema_version") == 2 and report.get("total_instances") == 1 and \
            report.get("submitted_instances") == 1 and \
            report.get("empty_patch_instances") == 1 and \
            report.get("empty_patch_ids") == [task_id] and \
            report.get("submitted_ids") == [task_id] and \
            report.get("resolved_instances") == 0 and \
            report.get("error_instances") == 0:
        return False
    raise ValueError("official report has no task verdict or verified empty patch")


def prediction(task_id: str, model_name: str, patch: bytes) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", task_id) or \
            not re.fullmatch(r"[A-Za-z0-9_.-]+", model_name):
        raise ValueError("unsafe task or model name")
    return (json.dumps({"instance_id": task_id, "model_name_or_path": model_name,
                        "model_patch": patch.decode("utf-8")}, ensure_ascii=False) + "\n").encode("utf-8")


def run_id_for(task_id: str, arm: str, attempt: int, patch: bytes) -> str:
    if attempt < 1 or not re.fullmatch(r"[A-Za-z0-9_.-]+", arm):
        raise ValueError("invalid arm or attempt")
    digest = hashlib.sha256(patch).hexdigest()[:16]
    return f"athena-{task_id}-{arm}-{attempt}-{digest}"


def validate_harness_io(workdir: Path, envelope: dict, *, task_id: str,
                        model_name: str, patch: bytes) -> None:
    """Bind the official gate's saved invocation, prediction and process output."""
    run_id = envelope["run_id"]
    files = {name: workdir / f"{run_id}.{suffix}" for name, suffix in (
        ("command", "command.json"), ("prediction", "jsonl"),
        ("stdout", "stdout.txt"), ("stderr", "stderr.txt"))}
    for name, path in files.items():
        if not path.is_file() or \
                hashlib.sha256(path.read_bytes()).hexdigest() != envelope.get(f"{name}_sha256"):
            raise ValueError(f"official harness {name} evidence changed")
    if files["prediction"].read_bytes() != prediction(task_id, model_name, patch):
        raise ValueError("official harness prediction differs from candidate")
    command = json.loads(files["command"].read_text(encoding="utf-8"))
    if not isinstance(command, list) or not all(isinstance(arg, str) for arg in command):
        raise ValueError("official harness command is invalid")
    def argument(flag: str) -> str:
        if command.count(flag) != 1:
            raise ValueError(f"official harness command has wrong {flag}")
        index = command.index(flag) + 1
        if index >= len(command):
            raise ValueError(f"official harness command has no value for {flag}")
        return command[index]
    expected = {"-m": "swebench.harness.run_evaluation",
                "--instance_ids": task_id, "--run_id": run_id,
                "--split": "test", "--max_workers": "1"}
    for flag, value in expected.items():
        if argument(flag) != value:
            raise ValueError(f"official harness command has wrong {flag}")
    for flag, suffix in (("--dataset_name", ".dataset.json"),
                         ("--predictions_path", ".jsonl")):
        if not argument(flag).endswith(run_id + suffix):
            raise ValueError(f"official harness command has wrong {flag}")
    timeout_arg = argument("--timeout")
    if not timeout_arg.isdecimal() or int(timeout_arg) < 1:
        raise ValueError("official harness command has wrong timeout")


def attest(*, task_id: str, patch: bytes, official_report: Path,
           gate_dir: Path, run_id: str, harness_version: str) -> dict:
    """Copy the official report unchanged and hash it into a separate gate envelope."""
    report = json.loads(official_report.read_text(encoding="utf-8"))
    resolved = official_verdict(report, task_id)
    gate_dir.mkdir(parents=True, exist_ok=False)
    target = gate_dir / "official_report.json"
    shutil.copyfile(official_report, target)
    envelope = {"schema": "athena.self-improve.gate/1",
                "runner": "swebench-harness", "instance_id": task_id,
                "patch_sha256": hashlib.sha256(patch).hexdigest(),
                "resolved": resolved, "run_id": run_id,
                "harness_version": harness_version,
                "official_report": target.name,
                "official_report_sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    (gate_dir / "gate.json").write_text(json.dumps(envelope, indent=2) + "\n",
                                         encoding="utf-8")
    return envelope


def run_harness(*, task_id: str, arm: str, attempt: int, model_name: str,
                patch: bytes, row: dict, workdir: Path, gate_dir: Path,
                timeout: int = 1800, wsl_distro: str | None = None,
                harness_python: str | None = None) -> dict:
    """Run the official harness once; an absent report stays unproved."""
    gate_start = time.monotonic()
    if gate_dir.exists():
        raise FileExistsError(gate_dir)
    run_id = run_id_for(task_id, arm, attempt, patch)
    started_path = gate_dir.parent / "gate_started.json"
    with started_path.open("x", encoding="utf-8") as stream:
        json.dump({"schema": "athena.self-improve.gate-start/1",
                   "task_id": task_id, "arm": arm, "attempt": attempt,
                   "run_id": run_id}, stream)
        stream.write("\n")
    prediction_bytes = prediction(task_id, model_name, patch)
    workdir.mkdir(parents=True, exist_ok=True)
    dataset_path = workdir / f"{run_id}.dataset.json"
    with dataset_path.open("x", encoding="utf-8") as stream:
        json.dump([row], stream, ensure_ascii=False)
        stream.write("\n")
    prediction_path = workdir / f"{run_id}.jsonl"
    with prediction_path.open("xb") as stream:
        stream.write(prediction_bytes)
    if wsl_distro:
        if not harness_python or not harness_python.startswith("/"):
            raise ValueError("WSL harness needs an absolute Linux Python path")
        prefix = ["wsl", "-d", wsl_distro, "--cd", _wsl_path(workdir, wsl_distro),
                  "--", harness_python]
        dataset_arg = _wsl_path(dataset_path, wsl_distro)
        prediction_arg = _wsl_path(prediction_path, wsl_distro)
        cwd = None
    else:
        prefix = [harness_python or sys.executable]
        dataset_arg = str(dataset_path.resolve())
        prediction_arg = str(prediction_path.resolve())
        cwd = workdir
    version_cmd = [*prefix, "-c", "import importlib.metadata as m; print(m.version('swebench'))"]
    version_proc = subprocess.run(version_cmd, cwd=cwd, text=True, capture_output=True)
    installed_version = version_proc.stdout.strip()
    if version_proc.returncode or installed_version != HARNESS_VERSION:
        raise RuntimeError(f"SWE-bench {HARNESS_VERSION} required; found {installed_version or 'none'}")
    command = [*prefix, "-m", "swebench.harness.run_evaluation",
               "--dataset_name", dataset_arg, "--split", "test",
               "--predictions_path", prediction_arg,
               "--instance_ids", task_id, "--max_workers", "1",
               "--timeout", str(timeout), "--run_id", run_id]
    (workdir / f"{run_id}.command.json").write_text(json.dumps(command, indent=2) + "\n",
                                                    encoding="utf-8")
    stdout_path = workdir / f"{run_id}.stdout.txt"
    stderr_path = workdir / f"{run_id}.stderr.txt"
    with stdout_path.open("xb") as stdout_file, stderr_path.open("xb") as stderr_file:
        proc = subprocess.run(command, cwd=cwd, stdout=stdout_file,
                              stderr=stderr_file, timeout=timeout + 1800)
    report_path = workdir / "logs" / "evaluation" / run_id / model_name / task_id / "report.json"
    if not patch and not report_path.is_file():
        report_path = workdir / "logs" / "evaluation" / run_id / "results.json"
    if not report_path.is_file():
        raise RuntimeError(f"official harness produced no per-instance report (exit {proc.returncode})")
    envelope = attest(task_id=task_id, patch=patch, official_report=report_path,
                      gate_dir=gate_dir, run_id=run_id, harness_version=installed_version)
    envelope["dataset_sha256"] = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    for name, path in (("command", workdir / f"{run_id}.command.json"),
                       ("prediction", prediction_path),
                       ("stdout", stdout_path),
                       ("stderr", stderr_path)):
        envelope[f"{name}_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    envelope["gate_wall_seconds"] = time.monotonic() - gate_start
    (gate_dir / "gate.json").write_text(json.dumps(envelope, indent=2) + "\n",
                                         encoding="utf-8")
    return envelope
