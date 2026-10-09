"""Plan and prepare isolated task-arm Git worktrees for the pilot."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .corpus import ARMS

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def cells(manifest: dict, *, stage: str) -> list[dict]:
    if stage not in ("baseline", "optimizer"):
        raise ValueError("stage must be baseline or optimizer")
    arms = ARMS[:2] if stage == "baseline" else ARMS[2:]
    return [{"task_id": task["id"], "repo": task["repo"],
             "base_commit": task["base_commit"], "split": task["split"], "arm": arm}
            for task in manifest["tasks"] for arm in arms]


def paths(root: Path, cell: dict, attempt: int) -> tuple[Path, Path]:
    repo, task_id, arm = cell["repo"], cell["task_id"], cell["arm"]
    if not _REPO.fullmatch(repo) or not _ID.fullmatch(task_id) or arm not in ARMS or attempt < 1:
        raise ValueError("unsafe task, repository, arm or attempt")
    if cell["split"] not in ("development", "holdout"):
        raise ValueError("unknown split")
    root = root.resolve()
    cache = root / "repos" / (repo.replace("/", "__") + ".git")
    workspace = root / "workspaces" / cell["split"] / task_id / arm / str(attempt)
    if not cache.is_relative_to(root) or not workspace.is_relative_to(root):
        raise ValueError("workspace escaped experiment root")
    return cache, workspace


def _git(args: list[str], *, cwd: Path | None = None) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def prepare(cell: dict, *, attempt: int, root: Path, remote: str | None = None) -> Path:
    """Create one fresh worktree at the pinned base commit; never reuse an attempt."""
    cache, workspace = paths(root, cell, attempt)
    if workspace.exists():
        raise FileExistsError(workspace)
    cache.parent.mkdir(parents=True, exist_ok=True)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        source = remote or f"https://github.com/{cell['repo']}.git"
        _git(["clone", "--bare", "--filter=blob:none", source, str(cache)])
    commit = cell["base_commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("base commit must be a full Git SHA")
    _git(["--git-dir", str(cache), "cat-file", "-e", f"{commit}^{{commit}}"])
    _git(["--git-dir", str(cache), "worktree", "add", "--detach", str(workspace), commit])
    head = _git(["rev-parse", "HEAD"], cwd=workspace)
    if head != commit:
        raise RuntimeError("worktree did not land on the pinned base commit")
    return workspace
