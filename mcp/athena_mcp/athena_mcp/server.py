"""
Athena MCP server — exposes the v2 §7 planning verbs to Hermes over MCP (FastMCP).

Scope = three planning layers -> a populated bd graph. Execution is DEFERRED: there is
NO planner_next/complete; the queue is handed off via planner_export_ready. Run:
`python -m athena_mcp.server`.
"""
from __future__ import annotations

from fastmcp import FastMCP

from athena_mcp import verbs

mcp = FastMCP("athena")


# --- CRISP alignment stages (layer ①) ---
@mcp.tool
def planner_question(intent: str, repo_path: str = ".") -> dict:
    """CRISP stage 1 — surface design forks as options; autonomous mode lets Hermes answer."""
    return verbs.stage("question", intent=intent, repo_path=repo_path)


@mcp.tool
def planner_research(questions_path: str) -> dict:
    """CRISP stage 2 — documentarian subagents gather facts; the feature ticket is hidden."""
    return verbs.stage("research", questions_path=questions_path)


@mcp.tool
def planner_design(research_path: str) -> dict:
    """CRISP stage 3 — structural design discussion before any code is planned."""
    return verbs.stage("design", research_path=research_path)


@mcp.tool
def planner_structure(design_path: str) -> dict:
    """CRISP stage 4 — vertical slices over horizontal layers."""
    return verbs.stage("structure", design_path=design_path)


@mcp.tool
def planner_align(intent: str, repo_path: str = ".") -> dict:
    """Coarse-grained: run CRISP alignment stages 1-4 with tier gates."""
    return verbs.align(intent, repo_path)


# --- layer ② Spec-Kit (on) / CRISP plan (off) ---
@mcp.tool
def planner_spec(intent: str = "") -> dict:
    """(ATHENA_SPECKIT=on) seed -> specify/clarify/plan/tasks/analyze -> tasks.md."""
    return verbs.spec(intent)


@mcp.tool
def planner_plan(structure_path: str) -> dict:
    """(ATHENA_SPECKIT=off) CRISP stage 5 — emit the canonical plan.md fallback."""
    return verbs.stage("plan", structure_path=structure_path)


# --- compile (layer ③) ---
@mcp.tool
def planner_validate(front_path: str) -> dict:
    """Validate the chosen front (tasks.md or plan.md, by ATHENA_SPECKIT) before compiling."""
    return verbs.validate(front_path)


@mcp.tool
def planner_compile(front_path: str, apply: bool = False) -> dict:
    """Compile the front -> bd graph (dry-run by default; apply=True writes). Toggle-aware."""
    return verbs.compile_plan(front_path, apply=apply)


# --- control / hand-off (NO execution — implement is deferred) ---
@mcp.tool
def planner_report() -> dict:
    """Return bd stats / progress summary across the epics."""
    return verbs.report()


@mcp.tool
def planner_replan(trigger: str, context: str = "") -> dict:
    """Backtrack to the right stage given discovered-from issues / analyze failures."""
    return verbs.replan(trigger, context)


@mcp.tool
def planner_export_ready() -> dict:
    """Bridge to the (deferred) executor: return `bd ready` — hands off the queue, does NOT execute."""
    return verbs.export_ready()


if __name__ == "__main__":
    mcp.run()
