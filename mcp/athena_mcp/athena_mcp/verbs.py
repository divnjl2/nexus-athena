"""
Athena MCP verbs — the planning/execution logic behind the MCP tools.

Two concrete, testable layers:
  * compiler-backed: validate / compile_plan  (pure, deterministic, no bd needed)
  * bd-backed:       next_issue / complete / report  (subprocess to `bd`; `run` injected)
The QRSPI stage verbs (question..structure, align, replan) return dispatch
descriptors — the HOST executes the QRSPI command prompt in a fresh context; in
autonomous mode Hermes answers Question-stage forks (closes RPI failure mode #1).
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

# make the repo-root `lib` package importable without installing it.
# anchor on a sentinel file rather than a fixed parents[N] so moving the package
# deeper fails loudly instead of importing `lib` from the wrong root.
_REPO = next(
    (p for p in pathlib.Path(__file__).resolve().parents if (p / "lib" / "plan_parser.py").exists()),
    None,
)
if _REPO is None:
    raise RuntimeError("cannot locate repo root containing lib/plan_parser.py")
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from lib.plan_parser import parse, PlanParseError          # noqa: E402
from lib.plan2beads import compile, CompileError, _slugify  # noqa: E402
from lib.bd_client import fetch_existing_keys, execute       # noqa: E402


def _run(argv: list[str]) -> str:
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout


# --- compiler-backed verbs (pure; no bd) ---------------------------------------

def validate(plan_path: str) -> dict:
    """Validate plan.md against the canonical format + compile-time checks."""
    try:
        compile(parse(pathlib.Path(plan_path).read_text(encoding="utf-8")))
        return {"passed": True, "issues": []}
    except (PlanParseError, CompileError) as e:
        return {"passed": False, "issues": [str(e)]}
    except FileNotFoundError:
        return {"passed": False, "issues": [f"file not found: {plan_path}"]}


def compile_plan(plan_path: str, apply: bool = False, *, run=_run) -> dict:
    """Compile plan.md -> bd commands. Dry-run by default; apply writes the graph."""
    plan = parse(pathlib.Path(plan_path).read_text(encoding="utf-8"))
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


# --- bd-backed verbs (subprocess; run injected for tests) ----------------------

def _err(e: Exception) -> str:
    out = getattr(e, "stderr", "") or getattr(e, "stdout", "") or str(e)
    return (out or "").strip()[:500]


def next_issue(*, run=_run) -> dict | None:
    try:
        items = json.loads(run(["bd", "ready", "--json", "--limit", "1"]) or "[]")
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": _err(e)}
    return {"issue": items[0]} if items else None


def complete(issue_id: str, gate_passed: bool, log: str = "", *, run=_run) -> dict:
    try:
        if gate_passed:
            run(["bd", "close", issue_id])
            run(["bd", "sync"])
        else:
            run(["bd", "update", issue_id, "--status", "open", "--note", log or "gate failed"])
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": _err(e)}
    return {"ok": True}


def report(*, run=_run) -> dict:
    try:
        return {"progress": json.loads(run(["bd", "stats", "--json"]) or "{}")}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": _err(e)}


# --- QRSPI stage dispatch (host executes the prompt; metadata only here) --------

_STAGE_ARTIFACT = {
    "question": "questions.md",
    "research": "research.md",
    "design": "design.md",
    "structure": "structure.md",
    "plan": "plan.md",
}
_STAGE_GATE = {
    "question": "dense", "research": "dense", "design": "dense",
    "structure": "spot", "plan": "spot",
}


def stage(name: str, **inputs) -> dict:
    """Dispatch descriptor for one QRSPI stage. The host runs the command prompt."""
    return {
        "stage": name,
        "command": f"/qrspi/{name}",
        "inputs": inputs,
        "artifact": _STAGE_ARTIFACT.get(name),
        "tier_gate": _STAGE_GATE.get(name),
        "note": "host runs the prompt in fresh context; autonomous mode -> Hermes answers forks",
    }


def align(intent: str, repo_path: str = ".") -> dict:
    """Coarse-grained: run alignment stages 1-4 under their tier gates."""
    seq = ["question", "research", "design", "structure"]
    return {
        "sequence": seq,
        "tier_gates": {s: _STAGE_GATE[s] for s in seq},
        "inputs": {"intent": intent, "repo_path": repo_path},
        "note": "drives question->research(ticket hidden)->design->structure; Hermes answers Question forks in autonomous mode",
    }


def replan(trigger: str, context: str = "") -> dict:
    """Backtrack to the right QRSPI stage inferred from the trigger text."""
    t = trigger.lower()
    for name in ("research", "design", "structure", "plan", "question"):
        if name in t:
            return stage(name, trigger=trigger, context=context)
    return stage("design", trigger=trigger, context=context)  # default: re-discuss design
