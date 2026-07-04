"""v4 — executor PORT: Athena records the `implements` edge (commit -> task) from ANY executor.

The frame does NOT depend on WHO writes the code. Hermes, OpenHands, Claude Code, Ralph — each
is an ADAPTER that conforms to the `Executor` protocol; Athena only ever sees an
`ExecutorResult` ({task_id, commit_sha, checks_passed}). This is the last leg of the loop:
v3.1 proved spec->scenario (top), v3.2 proved code->spec by coverage (bottom), v4 pins the REAL
commit that implemented each task into the graph. Deterministic edge emission — no LLM, no I/O
here; running the executor and the bd writes happen at the verb layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

EXTERNAL_KEY_PREFIX = "athena"
_HEX = set("0123456789abcdefABCDEF")


@dataclass(frozen=True)
class ExecutorResult:
    task_id: str
    commit_sha: str            # the REAL sha the `implements` edge pins (>=7 hex chars)
    checks_passed: bool        # did the task's success_check exit 0
    executor: str = ""         # provenance: "hermes" | "openhands" | "claude_code" | "ralph" | ...


@runtime_checkable
class Executor(Protocol):
    """The port. An adapter takes a ready task and returns where/whether it landed. HOW it
    writes code and commits is entirely the adapter's business — Athena never looks inside.
    Adapters (thin): HermesAdapter, OpenHandsAdapter, ClaudeCodeAdapter, RalphAdapter."""
    name: str

    def implement(self, task) -> ExecutorResult:
        ...


def validate_results(results) -> list[str]:
    """Port contract guard: every result must carry a task id and a REAL commit sha (>=7 hex).
    An empty/fake sha would make the `implements` edge a lie — reject it here."""
    issues: list[str] = []
    for r in results:
        if not r.task_id.strip():
            issues.append("result with empty task_id")
            continue
        sha = r.commit_sha.strip()
        if not sha:
            issues.append(f"{r.task_id}: empty commit_sha (implements needs a REAL sha)")
        elif len(sha) < 7 or any(c not in _HEX for c in sha):
            issues.append(f"{r.task_id}: commit_sha is not a real hash: {sha!r}")
    return issues


def implements_commands(results, *, slug: str) -> list[list[str]]:
    """Deterministic: ExecutorResult[] -> bd commands that pin `implements` (commit->task) and
    close tasks whose success_check passed. Document order (sorted by task_id). Mirrors the
    plan2beads freeze-line — pure, no I/O."""
    cmds: list[list[str]] = []
    for r in sorted(results, key=lambda x: x.task_id):
        sha = r.commit_sha.strip()
        if not sha:
            continue
        commit_key = f"{EXTERNAL_KEY_PREFIX}:{slug}:commit:{sha[:12]}"
        task_key = f"{EXTERNAL_KEY_PREFIX}:{slug}:{r.task_id}"
        cmds.append(["bd", "create", "--title", f"commit:{sha[:12]}",
                     "--label", commit_key, "--label", EXTERNAL_KEY_PREFIX,
                     "--label", "kind:commit", "--label", f"{EXTERNAL_KEY_PREFIX}:commit:{sha}",
                     *(["--label", f"executor:{r.executor}"] if r.executor else [])])
        cmds.append(["bd", "dep", "add", commit_key, task_key, "--type", "implements"])
        if r.checks_passed:
            cmds.append(["bd", "close", task_key])
    return cmds
