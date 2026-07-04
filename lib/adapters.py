"""v4 executor ADAPTERS — reference conformers to the `Executor` port (lib/executor.py).

Athena stays executor-AGNOSTIC: it only needs an `ExecutorResult` back. These adapters show the
shape. `GitCommitAdapter` is REAL — it reads a repo's actual HEAD sha, so an implements edge can
be pinned from any workflow that leaves a commit. Hermes / OpenHands / Claude Code / Ralph
adapters are the same three-line shape wrapped around their own run-and-commit machinery; the
frame never sees inside them.
"""
from __future__ import annotations

import subprocess

from lib.executor import ExecutorResult


def _git(argv) -> str:
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout


class GitCommitAdapter:
    """The executor already wrote code and committed in `repo`; this adapter pins the REAL HEAD
    sha into an ExecutorResult. Conforms to the `Executor` port: {name, implement(task)}."""
    name = "git"

    def __init__(self, repo: str, *, checks_passed: bool = True, run=_git):
        self.repo = repo
        self.checks_passed = checks_passed
        self._run = run

    def implement(self, task) -> ExecutorResult:
        sha = self._run(["git", "-C", self.repo, "rev-parse", "HEAD"]).strip()
        return ExecutorResult(task.id, sha, self.checks_passed, self.name)


# --- shape of the other adapters (thin — each wraps its own run+commit machinery) ----------
#
# class ClaudeCodeAdapter:      # Hermes swarm / OpenHands sandbox / Ralph loop are identical
#     name = "claude_code"
#     def implement(self, task) -> ExecutorResult:
#         sha, passed = self._drive(task)   # HOW it writes code + commits + checks is ITS business
#         return ExecutorResult(task.id, sha, passed, self.name)
#
# The frame swaps executors by swapping the adapter — zero changes to the graph, seams, or verbs.
