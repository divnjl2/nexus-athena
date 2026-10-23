"""Executable checks for the project-facing factory entrypoint."""
from __future__ import annotations

import pathlib
import subprocess

import pytest

import factory
from lib.executors import pi_command, resolve


def _git(root: pathlib.Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "product"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "factory@example.invalid")
    _git(root, "config", "user.name", "Factory Test")
    (root / "README.md").write_text("product\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-qm", "base")
    return root


def test_prepare_records_intent_once_without_claiming_a_pass(tmp_path):
    """C-1.1 — a request enters the project as an intent, not a green example test."""
    root = _repo(tmp_path)
    path = factory.prepare(factory.project_root(str(root)), "telegram-auth", "Allow known Telegram IDs")
    assert path.read_text(encoding="utf-8").endswith("Allow known Telegram IDs\n")
    assert not (path.parent / "contract.md").exists()
    with pytest.raises(FileExistsError):
        factory.prepare(root, "telegram-auth", "different intent")
    with pytest.raises(ValueError):
        factory.prepare(root, "../outside", "bad")


def test_run_requires_committed_proofs_and_keeps_project_tree_untouched(tmp_path, monkeypatch):
    """C-1.2 — an executor sees committed inputs in its own Git worktree."""
    root = _repo(tmp_path)
    feature = root / "features" / "telegram-auth"
    feature.mkdir(parents=True)
    for name in factory.ARTIFACTS:
        (feature / name).write_text(name, encoding="utf-8")
    with pytest.raises(ValueError, match="committed"):
        factory.run(root, "telegram-auth", "T1.1", "claude", 1)
    _git(root, "add", "features")
    _git(root, "commit", "-qm", "spec")
    fake_frame = tmp_path / "frame"
    fake_frame.mkdir()
    (fake_frame / "athena.py").write_text(
        "from pathlib import Path\nPath('executor-made.txt').write_text('worktree only')\n",
        encoding="utf-8")
    monkeypatch.setattr(factory, "FRAME", fake_frame)
    code, worktree = factory.run(root, "telegram-auth", "T1.1", "claude", 1)
    assert code == 0
    assert (worktree / "executor-made.txt").read_text() == "worktree only"
    assert not (root / "executor-made.txt").exists()
    assert _git(root, "status", "--porcelain") == ""
    code_again, same_worktree = factory.run(root, "telegram-auth", "T1.1", "claude", 1)
    assert code_again == 0 and same_worktree == worktree


def test_cluster_agent_uses_role_based_gateway_in_pi_harness():
    """C-1.3 — task execution addresses gateway roles, not fixed GPU lanes."""
    assert resolve("pi-cluster-agent")["model"] == "agent"
    argv = pi_command("pi-cluster-agent", "task", pi_bin="pi")["argv"]
    assert argv[argv.index("--provider") + 1] == "k3s9b"
    assert argv[argv.index("--model") + 1] == "agent"
    worker = pi_command("pi-cluster-worker", "task", pi_bin="pi")["argv"]
    assert worker[worker.index("--provider") + 1] == "k3s9b"
    assert worker[worker.index("--model") + 1] == "worker"


def test_doctor_reports_capabilities_without_emitting_a_key(tmp_path, monkeypatch):
    """C-1.4 — the readout names missing artifacts and never exposes credentials."""
    root = _repo(tmp_path)
    home = tmp_path / "home"
    config = home / ".pi" / "agent" / "models.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"providers":{"k3s9b":{"apiKey":"secret-test-value",'
                      '"models":[{"id":"agent"}]}}}', encoding="utf-8")
    monkeypatch.setattr(pathlib.Path, "home", lambda: home)
    report = factory.readiness(root, "telegram-auth")
    assert report["cluster_agent_configured"] is True
    assert report["artifacts_present"] is False
    assert "secret-test-value" not in str(report)


def test_cluster_gateway_bypasses_the_inherited_desktop_proxy():
    """C-1.5 — the Pi harness reaches the LAN gateway even with a desktop HTTP proxy."""
    child = factory.direct_cluster_env({"HTTP_PROXY": "http://proxy.invalid:8080",
                                        "NO_PROXY": "localhost"}, "http://192.168.1.136:30400/v1")
    assert "192.168.1.136" in child["NO_PROXY"].split(",")
    assert child["no_proxy"] == child["NO_PROXY"]
    assert child["HTTP_PROXY"] == "http://proxy.invalid:8080"
