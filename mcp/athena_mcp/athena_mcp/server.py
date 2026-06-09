"""
Athena MCP server — exposes the §6 planning verbs to Hermes over MCP (FastMCP).

Fine-grained verbs gate each QRSPI stage by tier; coarse-grained `planner_align`
runs stages 1-4 under the hood. compile/next/complete/report are backed by the
deterministic compiler + bd. Run: `python -m athena_mcp.server`.
"""
from __future__ import annotations

from fastmcp import FastMCP

from athena_mcp import verbs

mcp = FastMCP("athena")


# --- alignment stages (fine-grained) ---
@mcp.tool
def planner_question(intent: str, repo_path: str = ".") -> dict:
    """Stage 1 — surface design forks as options; autonomous mode lets Hermes answer."""
    return verbs.stage("question", intent=intent, repo_path=repo_path)


@mcp.tool
def planner_research(questions_path: str) -> dict:
    """Stage 2 — documentarian subagents gather facts; the feature ticket is hidden."""
    return verbs.stage("research", questions_path=questions_path)


@mcp.tool
def planner_design(research_path: str) -> dict:
    """Stage 3 — structural design discussion before any code is planned."""
    return verbs.stage("design", research_path=research_path)


@mcp.tool
def planner_structure(design_path: str) -> dict:
    """Stage 4 — vertical slices over horizontal layers."""
    return verbs.stage("structure", design_path=design_path)


@mcp.tool
def planner_align(intent: str, repo_path: str = ".") -> dict:
    """Coarse-grained: run alignment stages 1-4 with tier gates under the hood."""
    return verbs.align(intent, repo_path)


# --- plan / compile ---
@mcp.tool
def planner_plan(structure_path: str) -> dict:
    """Stage 5 — emit the canonical plan.md (the compiler contract)."""
    return verbs.stage("plan", structure_path=structure_path)


@mcp.tool
def planner_validate(plan_path: str) -> dict:
    """Validate plan.md format + completeness before compiling."""
    return verbs.validate(plan_path)


@mcp.tool
def planner_compile(plan_path: str, apply: bool = False) -> dict:
    """Compile plan.md into bd commands (dry-run by default; apply=True writes the graph)."""
    return verbs.compile_plan(plan_path, apply=apply)


# --- execution loop control ---
@mcp.tool
def planner_next() -> dict | None:
    """Return the top ready issue from the bd graph (or null when the queue is empty)."""
    return verbs.next_issue()


@mcp.tool
def planner_complete(issue_id: str, gate_passed: bool, log: str = "") -> dict:
    """Close an issue (gate passed) or reopen it with a note (gate failed)."""
    return verbs.complete(issue_id, gate_passed, log)


@mcp.tool
def planner_report() -> dict:
    """Return bd stats / progress summary across the epics."""
    return verbs.report()


@mcp.tool
def planner_replan(trigger: str, context: str = "") -> dict:
    """Backtrack to the right QRSPI stage given discovered-from issues / gate failures."""
    return verbs.replan(trigger, context)


if __name__ == "__main__":
    mcp.run()
