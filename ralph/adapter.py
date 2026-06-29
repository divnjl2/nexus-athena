"""Agent-agnostic executor adapters — one plan, many executors, one provenance contract.

The planner stops at a populated bd graph (`ralph/INTERFACE.md`). EXECUTION is pluggable:
Claude Code, OpenCode, OpenHands, or Hermes can each drive a single issue to done. They are
interchangeable behind one `ExecutorAdapter` contract, and — crucially — they ALL close the
loop through the SAME `close_with_provenance()`, so the bidirectional code<->spec link
(v4: the `implements` edge + version labels on the commit) is written identically no matter
which agent did the work. Swap the agent; the provenance graph is unchanged.

Contract per issue (unchanged from INTERFACE.md):
    bd ready --json -> claim -> adapter.run_issue() -> external gate -> close_with_provenance()

The external gate (the issue's success_check) stays AUTHORITATIVE; an adapter's self-report
never closes an issue on its own.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Issue:
    """The slice of a bd issue an executor needs."""
    key: str                       # external key, e.g. athena:plan:T1.1
    title: str
    success_check: str             # the gate command — exit 0 == done
    files: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()   # carries autonomy:* / agent:* routing hints


@dataclass(frozen=True)
class ExecResult:
    agent: str
    commit_sha: str                # filled by the executor after it commits its work
    passed: bool                   # the EXTERNAL gate verdict (not the agent's self-report)
    notes: str = ""


@runtime_checkable
class ExecutorAdapter(Protocol):
    """One executor agent. `command()` is pure (testable); `run_issue()` executes it."""
    name: str

    def command(self, issue: Issue, workdir: str) -> list[str]:
        """The CLI argv that drives this agent on ONE issue. Pure — no side effects."""
        ...

    def run_issue(self, issue: Issue, *, workdir: str, timeout: int = 1800) -> ExecResult:
        ...


# --- concrete adapters (thin; each documents its real CLI shape) ----------------

@dataclass(frozen=True)
class ClaudeCodeAdapter:
    name: str = "claude_code"
    bin: str = "claude"

    def command(self, issue: Issue, workdir: str) -> list[str]:
        return [self.bin, "-p", _issue_prompt(issue),
                "--output-format", "json", "--dangerously-skip-permissions"]

    def run_issue(self, issue: Issue, *, workdir: str, timeout: int = 1800) -> ExecResult:
        return _run_cli(self, issue, workdir, timeout)


@dataclass(frozen=True)
class OpenCodeAdapter:
    name: str = "opencode"
    bin: str = "opencode"

    def command(self, issue: Issue, workdir: str) -> list[str]:
        # opencode run -p "<task>"  (headless one-shot in the workdir)
        return [self.bin, "run", "-p", _issue_prompt(issue)]

    def run_issue(self, issue: Issue, *, workdir: str, timeout: int = 1800) -> ExecResult:
        return _run_cli(self, issue, workdir, timeout)


@dataclass(frozen=True)
class OpenHandsAdapter:
    name: str = "openhands"
    bin: str = "openhands"
    max_iterations: int = 30

    def command(self, issue: Issue, workdir: str) -> list[str]:
        # sandboxed Docker agent — preferred for autonomy:high issues
        return [self.bin, "--task", _issue_prompt(issue),
                "--max-iterations", str(self.max_iterations), "--workdir", workdir]

    def run_issue(self, issue: Issue, *, workdir: str, timeout: int = 1800) -> ExecResult:
        return _run_cli(self, issue, workdir, timeout)


@dataclass(frozen=True)
class HermesAdapter:
    name: str = "hermes"
    profile: str = "cex-ops"

    def command(self, issue: Issue, workdir: str) -> list[str]:
        # the autonomous swarm drives the issue via a chat session (loads MCP/tools)
        return ["hermes", "-p", self.profile, "chat", "-q", _issue_prompt(issue), "--yolo"]

    def run_issue(self, issue: Issue, *, workdir: str, timeout: int = 1800) -> ExecResult:
        return _run_cli(self, issue, workdir, timeout)


ADAPTERS: dict[str, ExecutorAdapter] = {
    a.name: a for a in (ClaudeCodeAdapter(), OpenCodeAdapter(), OpenHandsAdapter(), HermesAdapter())
}


def select_adapter(issue: Issue, *, default: str = "claude_code") -> ExecutorAdapter:
    """Route an issue to an executor. Precedence: explicit `agent:<name>` label >
    `autonomy:high` -> sandboxed OpenHands > the configured default."""
    for lb in issue.labels:
        if lb.startswith("agent:"):
            name = lb.split(":", 1)[1]
            if name in ADAPTERS:
                return ADAPTERS[name]
    if "autonomy:high" in issue.labels:
        return ADAPTERS["openhands"]
    return ADAPTERS[default]


# --- the ONE place the code<->spec link is written (agent-agnostic) -------------

def close_commands(issue_key: str, commit_sha: str, *, spec_version: str,
                   scenario_version: str, agent: str) -> list[tuple[str, ...]]:
    """Pure: the bd commands that fill the `implements` link + version pins, then close.

    `implements` is NOT a native bd link type (blocks|tracks|related|parent-child|
    discovered-from), so the edge is recorded as LABELS on the implemented issue — which is
    exactly what `trace_up(commit)` / the drift detector query via `bd list --label`. Same
    output for every agent: that is what keeps the bidirectional link agent-independent."""
    labels = [
        "implements",
        f"commit:{commit_sha}",
        f"spec_version:{spec_version}",
        f"scenario_version:{scenario_version}",
        f"agent:{agent}",
    ]
    cmds = [("bd", "label", "add", lb, issue_key) for lb in labels]
    cmds.append(("bd", "close", issue_key))
    return cmds


def close_with_provenance(issue_key: str, result: ExecResult, *, spec_version: str,
                          scenario_version: str, run) -> list[tuple[str, ...]]:
    """Execute the close+link commands via `run(argv)`. ONLY on a passed external gate —
    a failed gate leaves the issue open (livelock guard lives in the loop, INTERFACE.md).
    Returns the commands applied (for logging/idempotency)."""
    if not result.passed:
        raise ValueError(f"refusing to close {issue_key}: external gate did not pass")
    cmds = close_commands(issue_key, result.commit_sha, spec_version=spec_version,
                          scenario_version=scenario_version, agent=result.agent)
    for argv in cmds:
        run(list(argv))
    return cmds


# --- helpers --------------------------------------------------------------------

def _issue_prompt(issue: Issue) -> str:
    files = f"\nFiles in scope: {', '.join(issue.files)}" if issue.files else ""
    return (f"Implement issue {issue.key}: {issue.title}.{files}\n"
            f"Done means this passes: {issue.success_check}\n"
            f"Make the change, run the check, then commit with the issue key {issue.key} "
            f"in the commit message (Beads links the commit to the issue by that key).")


def _run_cli(adapter: ExecutorAdapter, issue: Issue, workdir: str, timeout: int) -> ExecResult:
    """Invoke the agent CLI, then read the gate + the commit it produced. The gate decision
    and SHA extraction are deployment-specific (the gate is external & authoritative); this
    default runs the command and reports a non-committal result the caller's gate finalises."""
    proc = subprocess.run(adapter.command(issue, workdir), cwd=workdir,
                          capture_output=True, text=True, timeout=timeout)
    return ExecResult(agent=adapter.name, commit_sha="", passed=False,
                      notes=f"rc={proc.returncode}; gate runs externally then commit_sha is filled")
