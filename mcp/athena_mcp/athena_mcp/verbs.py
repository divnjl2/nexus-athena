"""
Athena MCP verbs — the planning logic behind the MCP tools (v3+v3.1).

Scope ends at a populated bd graph (implement is DEFERRED). Compiler-backed verbs
(validate/compile) are pure + toggle-aware via lib.frontend. bd-backed verbs
(export_ready/report) hand off / summarize — they NEVER execute issues. The CRISP stage
verbs + spec() return dispatch descriptors; the host runs the prompt.

v3 additions: planner_spec, planner_compile (provenance graph), planner_trace_down/up.
v3.1 additions: planner_scenarios, planner_verify, planner_trace_proof.
"""
from __future__ import annotations

import json
import pathlib
import shlex
import shutil
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
from lib.frontend import parse_source, parse_with_provenance, speckit_enabled  # noqa: E402
from lib.plan2beads import compile, CompileError, _slugify       # noqa: E402
from lib.bd_client import fetch_existing_keys, execute           # noqa: E402
from lib.seams import seam_ast_wellformed, seam_graph_materialized, SeamResult  # noqa: E402


def _seam_dict(r: SeamResult) -> dict:
    return {"name": r.name, "passed": r.passed, "issues": list(r.issues), "hash": r.artifact_hash}


def _run(argv: list[str]) -> str:
    # On Windows, `bd` is an npm `.cmd` wrapper; subprocess can't exec it by bare name
    # (WinError 2). Resolve to the full bd.CMD path via PATH (shutil.which honors PATHEXT).
    if argv and argv[0] == "bd":
        argv = [shutil.which("bd") or "bd", *argv[1:]]
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout


def _err(e: Exception) -> str:
    out = getattr(e, "stderr", "") or getattr(e, "stdout", "") or str(e)
    return (out or "").strip()[:500]


# --- compiler-backed verbs (pure; toggle-aware) --------------------------------

def validate(front_path: str, *, speckit: bool | None = None) -> dict:
    """Validate the chosen front (Spec-Kit tasks.md or canonical plan.md) before compiling."""
    sk = speckit_enabled() if speckit is None else bool(speckit)
    try:
        plan = parse_source(front_path, speckit=speckit)
        aw = seam_ast_wellformed(plan)          # seam 6 — incl. CYCLE detection
        if not aw.passed:
            return {"passed": False, "speckit": sk, "issues": list(aw.issues), "seam": _seam_dict(aw)}
        compile(plan)
        return {"passed": True, "speckit": sk, "issues": [], "seam": _seam_dict(aw)}
    except (ParseError, CompileError) as e:
        return {"passed": False, "speckit": sk, "issues": [str(e)]}
    except FileNotFoundError:
        return {"passed": False, "speckit": sk, "issues": [f"file not found: {front_path}"]}


def compile_plan(front_path: str, apply: bool = False, *, speckit: bool | None = None, run=_run) -> dict:
    # parse_with_provenance attaches sibling spec.md/scenarios.md when present so the
    # v3.1 provenance edges materialise; it falls back to a flat parse otherwise.
    plan = parse_with_provenance(front_path, speckit=speckit)
    existing = fetch_existing_keys(_slugify(plan.title), run=run) if apply else frozenset()
    res = compile(plan, existing_keys=existing)
    out = {
        "epic_keys": list(res.epic_keys),
        "issue_count": res.issue_count,
        "commands": [str(c) for c in res.commands],
        "applied": apply,
    }
    if apply:
        execute(res, run=run)
        # seam 8 — POST-CONDITION read-back: re-read bd, verify the graph matches the AST
        try:
            graph = json.loads(run(["bd", "list", "--label", "athena", "--json"]) or "[]")
        except subprocess.CalledProcessError:
            graph = []
        out["seam"] = _seam_dict(seam_graph_materialized(plan, graph, _slugify(plan.title)))
    return out


# --- bd-backed verbs (hand-off only; implement is DEFERRED) ---------------------

def export_ready(*, run=_run) -> dict:
    """Bridge to the (deferred) executor: return the ready queue. Does NOT execute."""
    try:
        items = json.loads(run(["bd", "ready", "--json"]) or "[]")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        # FileNotFoundError/OSError = bd not on PATH; return the structured error shape
        # the MCP contract promises rather than throwing through the FastMCP wrapper.
        return {"ok": False, "error": _err(e)}
    return {"ready": items, "count": len(items)}


def report(*, run=_run) -> dict:
    try:
        return {"progress": json.loads(run(["bd", "stats", "--json"]) or "{}")}
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        # FileNotFoundError/OSError = bd not on PATH; return the structured error shape
        # the MCP contract promises rather than throwing through the FastMCP wrapper.
        return {"ok": False, "error": _err(e)}


# --- v3: provenance traversal verbs --------------------------------------------

def planner_trace_down(spec_version: str, *, run=_run) -> dict:
    """Traverse derived-from chain from spec_version downward.

    Returns design, epics, and tasks that derive from the given spec version.
    """
    try:
        nodes = json.loads(
            run(["bd", "list", "--label", f"athena:spec:{spec_version}", "--json"]) or "[]"
        )
        design_nodes = json.loads(
            run(["bd", "list", "--label", f"athena:design:", "--json"]) or "[]"
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        # FileNotFoundError/OSError = bd not on PATH; return the structured error shape
        # the MCP contract promises rather than throwing through the FastMCP wrapper.
        return {"ok": False, "error": _err(e)}
    return {
        "spec_version": spec_version,
        "spec_nodes": nodes,
        "design_nodes": design_nodes,
    }


def planner_trace_up(task_label: str, *, run=_run) -> dict:
    """Traverse from a task/issue label upward to its spec root.

    Returns the chain: task -> epic -> design -> spec.
    """
    try:
        items = json.loads(
            run(["bd", "list", "--label", task_label, "--json"]) or "[]"
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        # FileNotFoundError/OSError = bd not on PATH; return the structured error shape
        # the MCP contract promises rather than throwing through the FastMCP wrapper.
        return {"ok": False, "error": _err(e)}
    return {"task_label": task_label, "chain": items,
            "note": "traverse .parent fields upward to reach kind:spec node"}


# --- v3.1: scenario verbs ------------------------------------------------------

def planner_scenarios(spec_path: str = "spec.md") -> dict:
    """Dispatch descriptor: derive executable GWT scenarios from spec EARS criteria.

    Returns a dispatch descriptor — the host (Hermes) runs the prompt.
    """
    spec_exists = pathlib.Path(spec_path).exists()
    return {
        "command": "/athena.scenarios",
        "spec_path": spec_path,
        "spec_found": spec_exists,
        "artifact": "thoughts/scenarios/<spec_version>/scenarios.md",
        "note": (
            "Read spec.md EARS criteria, derive one Scenario per criterion. "
            "No Gherkin. Store under thoughts/scenarios/<spec_version>/. "
            "Pin output_version to seams.jsonl."
        ),
    }


def planner_verify(scenarios_path: str, *, run=_run) -> dict:
    """Run the scenario harness — execute each scenario's run_cmd, aggregate pass/fail.

    scenarios_path: path to scenarios.md (or a JSON list of Scenario dicts).
    Returns {requirement: str, passed: bool, failed: list[str]} per scenario.
    """
    path = pathlib.Path(scenarios_path)
    if not path.exists():
        return {"ok": False, "error": f"scenarios file not found: {scenarios_path}"}

    results = []
    # Parse run_cmd lines from scenarios.md (format: "run_cmd: <cmd>")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("run_cmd:"):
            continue
        cmd = line[len("run_cmd:"):].strip()
        # run_cmd is LLM-generated; NEVER shell=True (arbitrary command injection).
        # Tokenize and run shell-less. Reject shell metacharacters outright.
        if any(ch in cmd for ch in (";", "|", "&", "`", "$", ">", "<", "\n")):
            results.append({"cmd": cmd, "passed": False, "error": "rejected: shell metachar"})
            continue
        try:
            argv = shlex.split(cmd)
        except ValueError as e:
            results.append({"cmd": cmd, "passed": False, "error": f"unparseable: {e}"})
            continue
        if not argv:
            continue
        try:
            proc = subprocess.run(
                argv, shell=False, capture_output=True, text=True, timeout=60,
            )
            results.append({
                "cmd": cmd,
                "passed": proc.returncode == 0,
                "stdout": proc.stdout.strip()[:200],
                "stderr": proc.stderr.strip()[:200],
            })
        except subprocess.TimeoutExpired:
            results.append({"cmd": cmd, "passed": False, "error": "timeout"})
        except (FileNotFoundError, OSError) as e:
            results.append({"cmd": cmd, "passed": False, "error": str(e)})

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "results": results,
    }


def planner_trace_proof(spec_version: str, *, run=_run) -> dict:
    """Traverse verifies/satisfies axes to answer 'is requirement X currently satisfied?'

    Returns per-requirement coverage: which scenarios verify it, which tasks satisfy them,
    and whether all scenarios are currently passing (requires planner_verify to have run).
    """
    try:
        scenario_nodes = json.loads(
            run(["bd", "list", "--label", "kind:scenario", "--json"]) or "[]"
        )
        verifies_edges = json.loads(
            run(["bd", "list", "--label", "verifies", "--json"]) or "[]"
        )
        satisfies_edges = json.loads(
            run(["bd", "list", "--label", "satisfies", "--json"]) or "[]"
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        # FileNotFoundError/OSError = bd not on PATH; return the structured error shape
        # the MCP contract promises rather than throwing through the FastMCP wrapper.
        return {"ok": False, "error": _err(e)}

    uncovered: list[str] = []
    covered: list[dict] = []
    for node in scenario_nodes:
        req_key = node.get("requirement_key") or node.get("title", "")
        satisfiers = [e for e in satisfies_edges if e.get("target") == node.get("id")]
        verifiers = [e for e in verifies_edges if e.get("source") == node.get("id")]
        entry = {"scenario": node.get("id"), "requirement": req_key,
                 "satisfiers": len(satisfiers), "verifiers": len(verifiers)}
        if satisfiers:
            covered.append(entry)
        else:
            uncovered.append(req_key)

    return {
        "spec_version": spec_version,
        "covered": covered,
        "uncovered": uncovered,
        "coverage_pct": (len(covered) / max(len(scenario_nodes), 1)) * 100,
    }


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
    if "scenario_failed" in t:
        # v3.1: scenario failure may mean code drift (reopen task) or spec drift (backedge)
        return {
            "trigger": trigger,
            "context": context,
            "fork": {
                "code_not_ready": "reopen task; another executor iteration",
                "spec_drift": "backedge: research/scenario -> /specify, bump spec_version",
            },
            "note": "diagnose which branch applies before acting",
        }
    if "spec_invalid" in t:
        # v3: backedge research -> /specify bumps spec_version
        return {
            "trigger": trigger,
            "pipeline": ["refines_edge", "specify", "scenarios", "design", "compile"],
            "note": "bump spec_version; re-derive scenarios + design from new spec",
        }
    for name in ("research", "design", "structure", "plan", "question"):
        if name in t:
            return stage(name, trigger=trigger, context=context)
    return stage("design", trigger=trigger, context=context)
