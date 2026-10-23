"""Project entrypoint for Athena's spec-driven task factory.

The frontier writes the contract, executable scenarios and plan in the project.
This entrypoint keeps execution in a separate Git worktree and delegates the
verdict to Athena dispatch. It never treats a generated intent as a proof.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


FRAME = pathlib.Path(__file__).resolve().parent
SLUG = re.compile(r"[a-z][a-z0-9-]*\Z")
TASK = re.compile(r"T[0-9]+(?:\.[0-9]+)+\Z")
ARTIFACTS = ("contract.md", "scenarios.md", "plan.md")


def project_root(raw: str) -> pathlib.Path:
    root = pathlib.Path(raw).resolve()
    if not root.is_dir():
        raise ValueError(f"project directory does not exist: {root}")
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    if result.returncode or pathlib.Path(result.stdout.strip()).resolve() != root:
        raise ValueError(f"project must be a Git repository root: {root}")
    return root


def feature_dir(root: pathlib.Path, slug: str) -> pathlib.Path:
    if not SLUG.fullmatch(slug):
        raise ValueError("feature must be a lowercase slug: letters, digits and hyphens")
    return root / "features" / slug


def prepare(root: pathlib.Path, slug: str, intent: str) -> pathlib.Path:
    """Record the user's intent without manufacturing a passing specification."""
    if not intent.strip():
        raise ValueError("intent cannot be empty")
    dest = feature_dir(root, slug)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "intent.md"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(f"# Intent: {slug}\n\n{intent.strip()}\n")
    return path


def readiness(root: pathlib.Path, slug: str) -> dict:
    dest = feature_dir(root, slug)
    files = {name: (dest / name).is_file() for name in ARTIFACTS}
    entry = {}
    try:
        entry = cluster_provider()
    except (OSError, ValueError, KeyError, AttributeError, TypeError):
        pass
    provider = any(m.get("id") == "agent" for m in entry.get("models", [])) and bool(entry.get("apiKey"))
    try:
        openhands = importlib.util.find_spec("openhands.sdk") is not None
    except (ImportError, ValueError):
        openhands = False
    worker = False
    try:
        worker = any(m.get("id") == "worker" for m in entry.get("models", [])) and bool(entry.get("apiKey"))
    except (AttributeError, TypeError):
        pass
    return {"project": str(root), "feature": slug, "artifacts": files,
            "artifacts_present": all(files.values()), "pi_installed": shutil.which("pi") is not None,
            "cluster_agent_configured": provider, "cluster_worker_configured": worker,
            "openhands_installed": openhands}


def cluster_provider() -> dict:
    config = pathlib.Path.home() / ".pi" / "agent" / "models.json"
    raw = json.loads(config.read_text(encoding="utf-8"))
    return raw["providers"]["k3s9b"]


def direct_cluster_env(env: dict, base_url: str) -> dict:
    """Keep the LAN gateway out of a shell's inherited HTTP proxy."""
    host = urlsplit(base_url).hostname
    if not host:
        raise ValueError("cluster provider has no valid baseUrl host")
    result = env.copy()
    entries = [x.strip() for value in (result.get("NO_PROXY", ""), result.get("no_proxy", ""))
               for x in value.split(",") if x.strip()]
    if host not in entries:
        entries.append(host)
    result["NO_PROXY"] = result["no_proxy"] = ",".join(dict.fromkeys(entries))
    return result


def linked_worktree(root: pathlib.Path, worktree: pathlib.Path) -> bool:
    result = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=root,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    if result.returncode:
        return False
    return any(pathlib.Path(line[9:]).resolve() == worktree for line in result.stdout.splitlines()
               if line.startswith("worktree "))


def run(root: pathlib.Path, slug: str, task: str, executor: str, iterations: int) -> tuple[int, pathlib.Path]:
    """Dispatch committed specifications in a fresh worktree; leave it for review."""
    dest = feature_dir(root, slug)
    if not TASK.fullmatch(task):
        raise ValueError("task must be a plan id such as T1.1")
    if executor not in ("pi-cluster-agent", "pi-cluster-worker", "openhands", "claude"):
        raise ValueError("executor must be pi-cluster-agent, pi-cluster-worker, openhands or claude")
    if iterations < 1:
        raise ValueError("iterations must be positive")
    if not all((dest / name).is_file() for name in ARTIFACTS):
        raise ValueError("write contract.md, scenarios.md and plan.md before dispatch")
    status = subprocess.run(["git", "status", "--porcelain", "--", str(dest.relative_to(root))],
                            cwd=root, capture_output=True, text=True, timeout=15)
    if status.returncode or status.stdout.strip():
        raise ValueError("feature artifacts must be committed before dispatch")
    child_env = os.environ.copy()
    extra = []
    if executor in ("pi-cluster-agent", "pi-cluster-worker", "openhands"):
        provider = cluster_provider()
        role = "worker" if executor == "pi-cluster-worker" else "agent"
        if not any(model.get("id") == role for model in provider.get("models", [])):
            raise ValueError(f"cluster provider does not register the {role} role")
        child_env = direct_cluster_env(child_env, provider["baseUrl"])
    if executor == "openhands":
        if not readiness(root, slug)["openhands_installed"]:
            raise ValueError("openhands-sdk is not installed in this Python interpreter")
        if not provider.get("apiKey"):
            raise ValueError("cluster provider has no API key")
        child_env["LITELLM_LOCAL_KEY"] = provider["apiKey"]
        extra = ["--model", "openai/agent", "--base-url", provider["baseUrl"].rstrip("/")]
    worktree = root.parent / f"{root.name}-athena-{slug}-{task.lower().replace('.', '-')}"
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                          text=True, timeout=15)
    if base.returncode:
        raise ValueError("project has no HEAD commit")
    stamp = worktree / ".athena" / "factory_run.json"
    if worktree.exists():
        if not linked_worktree(root, worktree) or not stamp.is_file():
            raise ValueError(f"existing path is not this task's factory worktree: {worktree}")
        saved = json.loads(stamp.read_text(encoding="utf-8"))
        if saved != {"feature": slug, "task": task, "base": base.stdout.strip()}:
            raise ValueError("project HEAD changed since this worktree was created; review it before retrying")
    else:
        created = subprocess.run(["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
                                 cwd=root, capture_output=True, text=True, timeout=60)
        if created.returncode:
            raise RuntimeError(created.stderr.strip() or "git worktree add failed")
        stamp.parent.mkdir(exist_ok=True)
        stamp.write_text(json.dumps({"feature": slug, "task": task, "base": base.stdout.strip()}),
                         encoding="utf-8")
    cmd = [sys.executable, str(FRAME / "athena.py"), "dispatch",
           f"features/{slug}/contract.md", "--front", f"features/{slug}/plan.md",
           "--task", task, "--executor", executor, "--workspace", str(worktree),
           "--iterations", str(iterations), "--text", *extra]
    completed = subprocess.run(cmd, cwd=worktree, env=child_env)
    return completed.returncode, worktree


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Athena entrypoint for a project task")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="record a new intent for frontier specification")
    prep.add_argument("project"); prep.add_argument("feature"); prep.add_argument("intent")
    doc = sub.add_parser("doctor", help="check feature artifacts and local harness availability")
    doc.add_argument("project"); doc.add_argument("feature")
    launch = sub.add_parser("run", help="execute a committed task in an isolated worktree")
    launch.add_argument("project"); launch.add_argument("feature"); launch.add_argument("task")
    launch.add_argument("--executor", choices=("pi-cluster-agent", "pi-cluster-worker", "openhands", "claude"), default="pi-cluster-worker")
    launch.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        root = project_root(args.project)
        if args.command == "prepare":
            path = prepare(root, args.feature, args.intent)
            print(json.dumps({"intent": str(path), "state": "awaiting_frontier_spec"}, ensure_ascii=False))
        elif args.command == "doctor":
            print(json.dumps(readiness(root, args.feature), ensure_ascii=False))
        else:
            code, worktree = run(root, args.feature, args.task, args.executor, args.iterations)
            print(json.dumps({"dispatch_exit": code, "worktree": str(worktree)}, ensure_ascii=False))
            return code
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
