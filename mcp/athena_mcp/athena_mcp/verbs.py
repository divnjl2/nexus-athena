"""
Athena MCP verbs — the planning logic behind the MCP tools (v2, §7).

Scope ends at a populated bd graph (implement is DEFERRED). Compiler-backed verbs
(validate/compile) are pure + toggle-aware via lib.frontend. bd-backed verbs
(export_ready/report) hand off / summarize — they NEVER execute issues. The CRISP stage
verbs + spec() return dispatch descriptors; the host runs the prompt.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

# anchor on a sentinel file so moving the package fails loudly, not silently
_REPO = next(
    (p for p in pathlib.Path(__file__).resolve().parents if (p / "lib" / "plan_parser.py").exists()),
    None,
)
if _REPO is None:
    raise RuntimeError("cannot locate repo root containing lib/plan_parser.py")
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from lib.ast import ParseError                                   # noqa: E402
from lib.frontend import parse_source, speckit_enabled           # noqa: E402
from lib.plan2beads import compile, CompileError, _slugify       # noqa: E402
from lib.bd_client import fetch_existing_keys, execute           # noqa: E402


def _run(argv: list[str]) -> str:
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout


def _err(e: Exception) -> str:
    out = getattr(e, "stderr", "") or getattr(e, "stdout", "") or str(e)
    return (out or "").strip()[:500]


# --- compiler-backed verbs (pure; toggle-aware) --------------------------------

def validate(front_path: str, *, speckit: bool | None = None) -> dict:
    """Validate the chosen front (Spec-Kit tasks.md or canonical plan.md) before compiling."""
    sk = speckit_enabled() if speckit is None else bool(speckit)
    try:
        compile(parse_source(front_path, speckit=speckit))
        return {"passed": True, "speckit": sk, "issues": []}
    except (ParseError, CompileError) as e:
        return {"passed": False, "speckit": sk, "issues": [str(e)]}
    except FileNotFoundError:
        return {"passed": False, "speckit": sk, "issues": [f"file not found: {front_path}"]}


def compile_plan(front_path: str, apply: bool = False, *, speckit: bool | None = None, run=_run) -> dict:
    plan = parse_source(front_path, speckit=speckit)
    existing = fetch_existing_keys(_slugify(plan.title), run=run) if apply else frozenset()
    res = compile(plan, existing_keys=existing)
    if apply:
        execute(res, run=run)
    return {
        "epic_keys": list(res.epic_keys),
        "issue_count": res.issue_count,
        "commands": [str(c) for c in res.commands],
        "applied": apply,
    }


# --- bd-backed verbs (hand-off only; implement is DEFERRED) ---------------------

def export_ready(*, run=_run) -> dict:
    """Bridge to the (deferred) executor: return the ready queue. Does NOT execute."""
    try:
        items = json.loads(run(["bd", "ready", "--json"]) or "[]")
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": _err(e)}
    return {"ready": items, "count": len(items)}


def report(*, run=_run) -> dict:
    try:
        return {"progress": json.loads(run(["bd", "stats", "--json"]) or "{}")}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": _err(e)}


# --- CRISP / Spec-Kit stage dispatch (host executes the prompt) -----------------

_STAGE_ARTIFACT = {"question": "questions.md", "research": "research.md",
                   "design": "design.md", "structure": "structure.md", "plan": "plan.md"}
_STAGE_GATE = {"question": "dense", "research": "dense", "design": "dense",
               "structure": "spot", "plan": "spot"}


def stage(name: str, **inputs) -> dict:
    return {"stage": name, "command": f"/crisp.{name}", "inputs": inputs,
            "artifact": _STAGE_ARTIFACT.get(name), "tier_gate": _STAGE_GATE.get(name),
            "note": "host runs the prompt in fresh context; autonomous mode -> Hermes answers forks"}


def align(intent: str, repo_path: str = ".") -> dict:
    seq = ["question", "research", "design", "structure"]
    return {"sequence": seq, "tier_gates": {s: _STAGE_GATE[s] for s in seq},
            "inputs": {"intent": intent, "repo_path": repo_path},
            "note": "CRISP align 1-4; Hermes answers Question forks in autonomous mode"}


def spec(intent: str = "") -> dict:
    """Spec-Kit pipeline (ATHENA_SPECKIT=on): seed -> specify/clarify/plan/tasks/analyze -> tasks.md."""
    return {"pipeline": ["specify", "clarify", "plan", "tasks", "analyze"],
            "artifact": "tasks.md", "tier_gates": {"analyze": "dense"},
            "inputs": {"intent": intent},
            "note": "seed Spec-Kit phase-by-phase from CRISP (speckit/seed.md); preset injects success_check"}


def replan(trigger: str, context: str = "") -> dict:
    t = trigger.lower()
    for name in ("research", "design", "structure", "plan", "question"):
        if name in t:
            return stage(name, trigger=trigger, context=context)
    return stage("design", trigger=trigger, context=context)
