"""v4 executor adapters — any conformer plugs into the same port (executor-agnostic)."""
from dataclasses import dataclass

from lib.ast import Plan, Phase, Task
from lib.executor import Executor, ExecutorResult
from lib.adapters import GitCommitAdapter
from lib.seams import seam_implements_backed


@dataclass
class _Task:
    id: str
    success_check: str = "run"


def test_git_adapter_conforms_to_port():
    assert isinstance(GitCommitAdapter("."), Executor)


def test_git_adapter_pins_real_head_sha():
    a = GitCommitAdapter("/repo", run=lambda argv: "a1b2c3d4e5f6\n")
    r = a.implement(_Task("T1.1"))
    assert isinstance(r, ExecutorResult)
    assert r.task_id == "T1.1" and r.commit_sha == "a1b2c3d4e5f6"
    assert r.executor == "git" and r.checks_passed is True


def test_git_adapter_reads_the_right_repo():
    seen = {}

    def fake(argv):
        seen["argv"] = argv
        return "deadbeef1234\n"

    GitCommitAdapter("/some/repo", run=fake).implement(_Task("T2.1"))
    assert seen["argv"] == ["git", "-C", "/some/repo", "rev-parse", "HEAD"]


def test_adapter_result_passes_seam_11():
    a = GitCommitAdapter("/repo", run=lambda argv: "a1b2c3d4e5\n")
    r = a.implement(_Task("T1.1"))
    plan = Plan("Demo Feature", "", (),
                (Phase("phase1", "p", "g", (), "", (Task("T1.1", "x", "run"),)),))
    assert seam_implements_backed(plan, [r]).passed is True


def test_failed_check_adapter_flows_through_port():
    a = GitCommitAdapter("/repo", checks_passed=False, run=lambda argv: "a1b2c3d4\n")
    r = a.implement(_Task("T1.1"))
    assert r.checks_passed is False and r.commit_sha == "a1b2c3d4"
