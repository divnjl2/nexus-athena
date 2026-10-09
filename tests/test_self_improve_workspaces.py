"""Executable specs for isolated pilot workspaces."""
import subprocess

import pytest

from evals.self_improve.workspaces import cells, paths, prepare


def _git(*args, cwd):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def test_stage_plans_original_arms_before_optimizer():
    """C-3.1: baseline and optimizer have distinct fixed task-arm cells."""
    manifest = {"tasks": [{"id": "org__repo-1", "repo": "org/repo", "base_commit": "a"*40,
                            "split": "development"}]}
    baseline = cells(manifest, stage="baseline")
    optimizer = cells(manifest, stage="optimizer")
    assert [c["arm"] for c in baseline] == ["codex", "codex_athena"]
    assert [c["arm"] for c in optimizer] == ["codex_athena_optimizer"]
    with pytest.raises(ValueError):
        cells(manifest, stage="final")


def test_worktree_is_fresh_and_pinned_to_the_source_commit(tmp_path):
    """C-3.2: every attempt starts in a separate worktree at the task base commit."""
    source = tmp_path / "source"
    source.mkdir()
    _git("init", "-q", cwd=source)
    _git("config", "user.email", "pilot@example.invalid", cwd=source)
    _git("config", "user.name", "Pilot", cwd=source)
    (source / "app.py").write_text("original\n")
    _git("add", "app.py", cwd=source)
    _git("commit", "-qm", "base", cwd=source)
    commit = _git("rev-parse", "HEAD", cwd=source)
    cell = {"task_id": "org__repo-1", "repo": "org/repo", "base_commit": commit,
            "split": "development", "arm": "codex"}
    root = tmp_path / "pilot"
    first = prepare(cell, attempt=1, root=root, remote=str(source))
    (first / "app.py").write_text("changed\n")
    second = prepare(cell, attempt=2, root=root, remote=str(source))
    assert (second / "app.py").read_text() == "original\n"
    assert _git("rev-parse", "HEAD", cwd=second) == commit
    with pytest.raises(FileExistsError):
        prepare(cell, attempt=1, root=root, remote=str(source))


def test_workspace_paths_reject_untrusted_identifiers(tmp_path):
    """C-3.3: dataset identifiers cannot route Git worktrees outside the pilot root."""
    cell = {"task_id": "../escape", "repo": "org/repo", "split": "holdout", "arm": "codex"}
    with pytest.raises(ValueError):
        paths(tmp_path, cell, 1)
