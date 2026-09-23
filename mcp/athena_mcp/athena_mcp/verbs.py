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


def planner_trace_coverage(front_path: str, coverage_path: str, *, speckit=None) -> dict:
    """Coverage axis (v3.2): walk `satisfies` and confirm each scenario actually covers its
    task's source, then list orphan branches (`spec_gaps`). Reads a coverage.xml from a
    scenario run. Deterministic, no bd — feeds planner_replan(trigger='spec_gap')."""
    from lib.coverage_backed import parse_coverage, trace_coverage
    import xml.etree.ElementTree as ET
    try:
        plan = parse_source(front_path, speckit=speckit)
        cov = parse_coverage(pathlib.Path(coverage_path).read_text(encoding="utf-8"))
    except (ParseError, FileNotFoundError, OSError, ET.ParseError) as e:
        return {"ok": False, "error": _err(e)}
    return trace_coverage(plan, cov)


def _contract_inputs(contract_path: str, scenarios_path: str = "", ledger_path: str = ""):
    """v3.3: load (contract, scenarios, ledger). Scenarios default to the contract sibling."""
    from lib.contract import parse as parse_contract
    from lib.scenario_parser import parse as parse_scenarios
    from lib.spec_runner import load_ledger
    cp = pathlib.Path(contract_path)
    sp = pathlib.Path(scenarios_path) if scenarios_path else cp.parent / "scenarios.md"
    contract = parse_contract(cp.read_text(encoding="utf-8"))
    scenarios = parse_scenarios(sp.read_text(encoding="utf-8"))
    return contract, scenarios, load_ledger(ledger_path or ".athena/spec_ledger.json")


def planner_contract_coverage(contract_path: str = "contract.md",
                              scenarios_path: str = "") -> dict:
    """Q1: which contract clauses have NO executable spec (plus orphan + redirected specs).
    Pure + linear in the clause count — cheap enough to ask on every planning turn."""
    from lib.contract_report import coverage
    try:
        contract, scenarios, _ = _contract_inputs(contract_path, scenarios_path)
    except (ParseError, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": _err(e)}
    return coverage(contract, scenarios)


def planner_contract_todo(contract_path: str = "contract.md", scenarios_path: str = "",
                          ledger_path: str = "") -> dict:
    """Q2: what is left to implement — every live clause in exactly one of unspecified /
    red / unrun / stale / done, with draft clauses as backlog. Reads the spec ledger."""
    from lib.contract_report import todo
    try:
        contract, scenarios, ledger = _contract_inputs(contract_path, scenarios_path, ledger_path)
    except (ParseError, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": _err(e)}
    return todo(contract, scenarios, ledger)


def planner_contract_drift(contract_path: str = "contract.md", scenarios_path: str = "",
                           ledger_path: str = "") -> dict:
    """Q3: where requirement, spec and proof diverged — spec_drift / stale_proof /
    missing_spec / extra_spec. `in_sync` is the one-bit answer a gate can read."""
    from lib.contract_report import drift
    try:
        contract, scenarios, ledger = _contract_inputs(contract_path, scenarios_path, ledger_path)
    except (ParseError, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": _err(e)}
    return drift(contract, scenarios, ledger)


def planner_spec_run(scenarios_path: str = "scenarios.md", contract_path: str = "",
                     out_path: str = ".athena/spec_ledger.json", clause: str = "",
                     jobs: int = 8, timeout: int = 120, cwd: str = ".", ts: str = "") -> dict:
    """EFFECTFUL: run the executable specs and write the red/green ledger the two reports
    above read. `clause` narrows the run to one area (the fast inner loop)."""
    import datetime
    from lib.contract import parse as parse_contract
    from lib.scenario_parser import parse as parse_scenarios
    from lib.spec_runner import make_ledger, run_specs, select, write_ledger
    from lib.versioning import hash_text
    try:
        text = pathlib.Path(scenarios_path).read_text(encoding="utf-8")
        scenarios = parse_scenarios(text)
        cp = (pathlib.Path(contract_path) if contract_path
              else pathlib.Path(scenarios_path).parent / "contract.md")
        contract = parse_contract(cp.read_text(encoding="utf-8")) if cp.exists() else None
    except (ParseError, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": _err(e)}
    results = run_specs(select(scenarios, clause_prefix=clause), cwd=cwd,
                        timeout=timeout, jobs=jobs)
    stamp = ts or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    ledger = make_ledger(results, contract=contract, scenario_version=hash_text(text), ts=stamp)
    write_ledger(ledger, out_path)
    return {"ok": ledger["totals"]["failed"] == 0, "ledger": out_path, **ledger["totals"],
            "red": [r["scenario"] for r in ledger["results"] if not r["passed"]]}


def planner_contract_pin(scenarios_path: str = "scenarios.md",
                         contract_path: str = "contract.md", write: bool = False) -> dict:
    """Bind each spec to the clause VERSION it was written against (drift instrumentation).
    Dry-run unless write=True."""
    from lib.contract import parse as parse_contract
    from lib.contract import pin_scenarios
    try:
        contract = parse_contract(pathlib.Path(contract_path).read_text(encoding="utf-8"))
        text = pathlib.Path(scenarios_path).read_text(encoding="utf-8")
    except (ParseError, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": _err(e)}
    new_text, stats = pin_scenarios(text, contract)
    if write:
        pathlib.Path(scenarios_path).write_text(new_text, encoding="utf-8")
    return {"ok": True, "written": bool(write), **stats}


def planner_contract_gate(front_path: str, *, speckit=None) -> dict:
    """seam.contract_bound: fail-closed before compiling — no live clause without a spec,
    no spec naming a clause the contract does not define (drafts exempt)."""
    from lib.seams import seam_contract_bound
    try:
        plan = parse_with_provenance(front_path, speckit=speckit)
    except (ParseError, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": _err(e)}
    if plan.contract is None:
        return {"ok": False, "error": f"no contract.md next to {front_path}"}
    return _seam_dict(seam_contract_bound(plan.contract, plan.scenarios))


def planner_close_task(front_path: str, task_id: str, commit_sha: str, *,
                       checks_passed: bool = True, executor: str = "",
                       speckit=None, run=_run) -> dict:
    """v4 executor port: pin the `implements` edge (commit->task, REAL sha) into the graph and
    close the task if its checks passed. Executor-AGNOSTIC — the caller already ran Hermes /
    OpenHands / Claude Code / Ralph and hands us only the ExecutorResult. Athena never looks
    inside the executor; it only guarantees a real sha reached the graph (validated here)."""
    from lib.executor import ExecutorResult, implements_commands, validate_results
    try:
        plan = parse_source(front_path, speckit=speckit)
    except (ParseError, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": _err(e)}
    res = ExecutorResult(task_id, commit_sha, checks_passed, executor)
    issues = validate_results([res])
    if issues:
        return {"ok": False, "error": "; ".join(issues)}
    cmds = implements_commands([res], slug=_slugify(plan.title))
    try:
        for c in cmds:
            run(c)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        return {"ok": False, "error": _err(e)}
    return {"ok": True, "task": task_id, "commit": commit_sha[:12], "executor": executor,
            "closed": checks_passed, "commands": len(cmds)}


def planner_trace_implements(front_path: str, *, speckit=None, run=_run) -> dict:
    """v4: which tasks have a real `implements` commit pinned, which are still open. Feeds
    planner_replan(trigger='implements_missing')."""
    try:
        plan = parse_source(front_path, speckit=speckit)
        edges = json.loads(run(["bd", "list", "--label", "implements", "--json"]) or "[]")
    except (ParseError, FileNotFoundError, OSError, subprocess.CalledProcessError) as e:
        return {"ok": False, "error": _err(e)}
    all_tasks = [t.id for ph in plan.phases for t in ph.tasks]
    implemented = {str(e.get("target", "")).split(":")[-1] for e in edges}
    unimplemented = [t for t in all_tasks if t not in implemented]
    return {
        "total": len(all_tasks),
        "implemented": [t for t in all_tasks if t in implemented],
        "unimplemented": unimplemented,
        "replan_trigger": "implements_missing" if unimplemented else None,
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
    if "spec_gap" in t:
        # v3.2: a code branch no scenario exercises — spec lags code (mirror of scenario_failed)
        return {
            "trigger": trigger,
            "context": context,
            "fork": {
                "dead_code": "remove: neither a requirement nor one that should exist",
                "lost_requirement": "backedge: code -> /specify, add requirement, bump spec_version",
            },
            "note": "diagnose dead-code vs lost-requirement before acting",
        }
    if "satisfies_unproven" in t:
        # v3.2: satisfies edge declared but the scenario does not cover the task's source
        return {
            "trigger": trigger,
            "context": context,
            "reopen": "task's scenario does not exercise its source; fix the test or the binding",
            "note": "the satisfies edge is false until coverage proves it",
        }
    if "implements_missing" in t:
        # v4: task has no commit pinned — hand off to an executor adapter, then close with the sha
        return {
            "trigger": trigger,
            "context": context,
            "handoff": "export_ready -> executor adapter (hermes|openhands|claude_code|ralph)",
            "then": "planner_close_task(front, task_id, commit_sha) pins the implements edge",
            "note": "Athena is executor-agnostic; the port only needs a real commit sha back",
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
