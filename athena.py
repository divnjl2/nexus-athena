#!/usr/bin/env python
"""
Athena CLI — shell-exec entrypoint for cex-Hermes workflows (and local use).

Hermes `dispatcher: script` shell-execs subcommands here; each prints a JSON line and
exits 0/non-0 so it can be a workflow step or a quality_gate. Subcommands:
  validate <front>        -> seam.ast_wellformed (parse + cycle/dup/missing-check)
  compile  <front>        -> dry-run bd command list + counts
  hermes-plan <front> -o  -> emit a cex-Hermes master-plan .md (the bridge)
  seam <name> <front>     -> run one named seam as a fail-closed gate

Toggle: --speckit {on,off,auto}; auto reads ATHENA_SPECKIT (default on).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from lib.ast import ParseError                              # noqa: E402
from lib.frontend import parse_source, parse_with_provenance  # noqa: E402
from lib.plan2beads import compile, CompileError, _slugify  # noqa: E402
from lib.hermes_plan import render_master_plan              # noqa: E402
from lib import seams                                       # noqa: E402

__version__ = "0.1.0"                                       # repair: claurst added --version referencing this but never defined it


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _speckit(arg: str) -> bool | None:
    return {"on": True, "off": False, "auto": None}[arg]


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))


def cmd_validate(a) -> int:
    plan = parse_source(a.front, speckit=_speckit(a.speckit))
    r = seams.seam_ast_wellformed(plan)
    _emit({"seam": r.name, "passed": r.passed, "issues": list(r.issues), "hash": r.artifact_hash})
    return 0 if r.passed else 1


def cmd_compile(a) -> int:
    # parse_with_provenance attaches sibling spec.md/scenarios.md when present so the
    # v3.1 provenance edges materialise; it falls back to a flat parse otherwise.
    plan = parse_with_provenance(a.front, speckit=_speckit(a.speckit))
    res = compile(plan)
    _emit({"epics": len(res.epic_keys), "issues": res.issue_count, "commands": len(res.commands)})
    return 0


def cmd_stats(a) -> int:
    plan = parse_source(a.front, speckit=_speckit(a.speckit))
    res = compile(plan)
    _emit({"epics": len(res.epic_keys), "issues": res.issue_count,
           "tasks": sum(len(p.tasks) for p in plan.phases)})
    return 0


def cmd_hermes_plan(a) -> int:
    # Hermes dispatcher execs (no shell). The engine expands ${CEX_HERMES_INPUT_*} only
    # when inputs declare the env: mapping; we ALSO read the env directly so this works
    # either way. Explicit args win.
    front = a.front or _env("CEX_HERMES_INPUT_FRONT")
    out = a.out or _env("CEX_HERMES_INPUT_OUT")
    speckit = a.speckit if a.speckit != "auto" else _env("CEX_HERMES_INPUT_SPECKIT", "auto")
    if speckit not in ("on", "off", "auto"):
        speckit = "auto"
    if not front or not out:
        _emit({"error": "front and out required (args or CEX_HERMES_INPUT_FRONT/OUT)"})
        return 2
    plan = parse_source(front, speckit=_speckit(speckit))
    aw = seams.seam_ast_wellformed(plan)
    if not aw.passed:
        _emit({"seam": aw.name, "passed": False, "issues": list(aw.issues)})
        return 1
    try:
        compile(plan)  # determinism + compile-time validation (e.g. empty slug) before emit
    except CompileError as e:
        _emit({"error": f"compile: {e}"})
        return 1
    pid = a.plan_id or _slugify(plan.title)
    pathlib.Path(out).write_text(render_master_plan(plan, plan_id=pid, created=a.created or ""),
                                 encoding="utf-8")
    _emit({"out": out, "tasks": sum(len(p.tasks) for p in plan.phases), "plan_id": pid})
    return 0


def cmd_seam(a) -> int:
    front = a.front or _env("CEX_HERMES_INPUT_FRONT")
    name = a.name.removeprefix("seam.")
    if name == "speckit_schema":
        # runtime schema conformance: does this front parse under the PINNED Spec-Kit schema?
        from lib.speckit_parser import parse as sk_parse, SpecKitParseError
        try:
            sk_parse(pathlib.Path(front).read_text(encoding="utf-8"))
            _emit({"seam": "seam.speckit_schema", "passed": True, "issues": []})
            return 0
        except (SpecKitParseError, FileNotFoundError) as e:
            _emit({"seam": "seam.speckit_schema", "passed": False, "issues": [str(e)]})
            return 1
    if name == "map_fresh":
        # v3.3 gate: refuse a clause->file:line map that no longer describes this contract.
        # Reads the sibling contract/scenarios of the front, exactly like contract_bound.
        from lib.clause_map import staleness  # noqa: F401  (imported by the seam)
        from lib.versioning import hash_text
        plan = parse_with_provenance(front, speckit=_speckit(a.speckit))
        if plan.contract is None:
            _emit({"seam": "seam.map_fresh", "passed": False,
                   "issues": [f"no contract.md next to {front}"]})
            return 1
        map_path = a.map or ".athena/clause_map.json"
        try:
            cmap = json.loads(pathlib.Path(map_path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            cmap = {}
        scen = pathlib.Path(front).parent / "scenarios.md"
        r = seams.seam_map_fresh(
            cmap, plan.contract, plan.scenarios,
            scenario_version=hash_text(scen.read_text(encoding="utf-8")) if scen.exists() else "")
        _emit({"seam": r.name, "passed": r.passed, "issues": list(r.issues),
               "hash": r.artifact_hash, "map": map_path})
        return 0 if r.passed else 1

    if name == "contract_bound":
        # v3.3 gate: every live clause proved by >=1 spec, no spec pointing at a clause
        # the contract does not define. Needs the sibling contract.md + scenarios.md, so
        # it reads the front through parse_with_provenance (not the flat parse).
        plan = parse_with_provenance(front, speckit=_speckit(a.speckit))
        if plan.contract is None:
            _emit({"seam": "seam.contract_bound", "passed": False,
                   "issues": [f"no contract.md next to {front}"]})
            return 1
        r = seams.seam_contract_bound(plan.contract, plan.scenarios)
        _emit({"seam": r.name, "passed": r.passed, "issues": list(r.issues),
               "hash": r.artifact_hash})
        return 0 if r.passed else 1

    plan = parse_source(front, speckit=_speckit(a.speckit))
    if name == "ast_wellformed":
        r = seams.seam_ast_wellformed(plan)
    elif name == "compile_pure":
        r = seams.seam_compile_pure(compile, plan)
    elif name == "coverage_backed":
        from lib.coverage_backed import parse_coverage
        cov_path = a.coverage or _env("CEX_HERMES_INPUT_COVERAGE")
        if not cov_path:
            _emit({"error": "seam coverage_backed needs --coverage <coverage.xml>"})
            return 2
        cov = parse_coverage(pathlib.Path(cov_path).read_text(encoding="utf-8"))
        r = seams.seam_coverage_backed(plan, cov)
    else:
        _emit({"error": f"unknown seam: {a.name}"})
        return 2
    _emit({"seam": r.name, "passed": r.passed, "issues": list(r.issues), "hash": r.artifact_hash})
    return 0 if r.passed else 1


# --- v3.3: the contract layer (numbered clauses + executable specs) ---------------

def _read(path: str) -> str:
    return pathlib.Path(path).read_text(encoding="utf-8")


def _sibling(path: str, name: str) -> str:
    return str(pathlib.Path(path).parent / name)


def _load_contract(a):
    from lib.contract import parse as parse_contract
    return parse_contract(_read(a.contract))


def _load_scenarios(a, *, anchor: str):
    """Scenarios come from --scenarios, else the sibling scenarios.md of the anchor file."""
    from lib.scenario_parser import parse as parse_scenarios
    path = getattr(a, "scenarios", "") or _sibling(anchor, "scenarios.md")
    return parse_scenarios(_read(path))


def _ledger(a) -> dict:
    from lib.spec_runner import load_ledger
    return load_ledger(getattr(a, "ledger", "") or ".athena/spec_ledger.json")


def _report_out(a, report: dict, *, title: str) -> None:
    if getattr(a, "text", False):
        from lib.contract_report import render
        print(render(report, title=title))
    else:
        _emit(report)


def cmd_contract_lint(a) -> int:
    # Two passes, deliberately separate: `lint` judges the WIRING (ids, refs, cycles) and is
    # always a hard error; `critique` judges the WORDING (atomicity, vagueness, duplication)
    # and is advisory unless --strict, because a human may knowingly keep a clause it dislikes.
    from lib.contract import critique, lint
    c = _load_contract(a)
    issues = lint(c)
    warnings = critique(c)
    failed = bool(issues) or (bool(warnings) and a.strict)
    _emit({"seam": "contract.lint", "passed": not failed, "issues": list(issues),
           "warnings": [f"{w['clause']}: {w['code']} — {w['detail']}" for w in warnings],
           "clauses": len(c.clauses), "live": len(c.live()), "version": c.version})
    return 1 if failed else 0


def cmd_contract_coverage(a) -> int:
    from lib.contract_report import coverage
    c = _load_contract(a)
    rep = coverage(c, _load_scenarios(a, anchor=a.contract))
    _report_out(a, rep, title="contract coverage")
    return 0 if rep["passed"] or not a.gate else 1


def cmd_contract_todo(a) -> int:
    from lib.contract_report import todo
    c = _load_contract(a)
    rep = todo(c, _load_scenarios(a, anchor=a.contract), _ledger(a))
    _report_out(a, rep, title="what is left to implement")
    return 0


def cmd_contract_drift(a) -> int:
    from lib.contract_report import drift
    c = _load_contract(a)
    rep = drift(c, _load_scenarios(a, anchor=a.contract), _ledger(a))
    _report_out(a, rep, title="requirement <-> spec <-> proof drift")
    return 0 if rep["in_sync"] or not a.gate else 1


def cmd_contract_pin(a) -> int:
    from lib.contract import pin_scenarios
    c = _load_contract(a)
    path = a.scenarios or _sibling(a.contract, "scenarios.md")
    new_text, stats = pin_scenarios(_read(path), c)
    if a.write:
        pathlib.Path(path).write_text(new_text, encoding="utf-8")
    else:
        stats["dry_run"] = True
    _emit({"scenarios": path, **stats})
    return 0


def cmd_contract_import(a) -> int:
    # migration: an existing spec.md already carries numbered EARS criteria. Import keeps
    # the ids VERBATIM, so every `verifies:` already written keeps resolving.
    from lib.contract import import_from_spec, lint, render
    c = import_from_spec(_read(a.spec), section=a.section, title=a.title)
    text = render(c)
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    _emit({"clauses": len(c.clauses), "version": c.version, "out": a.out,
           "issues": list(lint(c))})
    return 0


def cmd_spec_run(a) -> int:
    # THE effectful one: run every executable spec, roll the verdicts up per clause.
    import datetime
    from lib.contract import parse as parse_contract
    from lib.spec_runner import make_ledger, run_specs, select, write_ledger
    from lib.versioning import hash_text

    scen_path = a.scenarios
    scenarios = _load_scenarios(a, anchor=scen_path)
    contract = None
    cpath = a.contract or _sibling(scen_path, "contract.md")
    if pathlib.Path(cpath).exists():
        contract = parse_contract(_read(cpath))

    picked = select(scenarios, clause_prefix=a.clause, scenario_prefix=a.spec_id,
                    contract=contract, skip_tags=tuple(a.skip_tag), only_tags=tuple(a.only_tag))
    # --env KEY=VALUE (repeatable): pinned over the inherited environment. The measured use
    # case is PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 — on a box with many pytest plugins installed
    # their autoload dominates a spec's runtime (10.3s of 10.8s here).
    env = dict(kv.split("=", 1) for kv in a.env if "=" in kv) or None
    results = run_specs(picked, cwd=a.cwd, timeout=a.timeout, jobs=a.jobs, env=env)
    ledger = make_ledger(
        results, contract=contract,
        scenario_version=hash_text(_read(scen_path)),
        ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    out = write_ledger(ledger, a.out)
    _emit({"ledger": str(out), **ledger["totals"],
           "red": [r["scenario"] for r in ledger["results"] if not r["passed"]]})
    return 0 if ledger["totals"]["failed"] == 0 else 1


def cmd_contract_map(a) -> int:
    # EFFECTFUL: run each spec ALONE under coverage so its lines can be attributed to the
    # clause it proves. This is the artifact that upgrades the reverse leg from file-level
    # ("this contract claims lib/seams.py") to line-level ("it owns these 40 lines of it").
    from lib.clause_map import build, collect, owned_lines
    from lib.spec_runner import select
    from lib.versioning import hash_text

    contract = _load_contract(a)
    scen_path = a.scenarios or _sibling(a.contract, "scenarios.md")
    scenarios = select(_load_scenarios(a, anchor=a.contract), clause_prefix=a.clause,
                       contract=contract, skip_tags=tuple(a.skip_tag))
    spec_lines = collect(scenarios, sources=tuple(a.source), workdir=a.workdir,
                         cwd=a.cwd, jobs=a.jobs)
    cmap = build(spec_lines, contract_version=contract.version,
                 scenario_version=hash_text(_read(scen_path)))
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(cmap, indent=2, sort_keys=True) + "\n",
                                   encoding="utf-8")
    owned = owned_lines(cmap)
    _emit({"map": a.out, "clauses_mapped": len(cmap["clauses"]),
           "specs": len(spec_lines), "files": len(owned),
           "owned_lines": sum(len(v) for v in owned.values()),
           "unmapped_clauses": sorted(c.id for c in contract.live()
                                      if c.id not in cmap["clauses"])})
    return 0


def cmd_contract_owners(a) -> int:
    # The query a developer actually has: "I am about to change this line — which
    # requirements am I allowed to break?"
    from lib.clause_map import owners
    cmap = json.loads(_read(a.map))
    path, _, line = a.target.rpartition(":")
    contract = _load_contract(a) if pathlib.Path(a.contract).exists() else None
    ids = owners(cmap, path, int(line))
    _emit({"target": a.target, "owners": list(ids),
           "text": {i: (contract.by_id(i).text if contract and contract.by_id(i) else "")
                    for i in ids}})
    return 0


def cmd_trace_coverage(a) -> int:
    # v3.2 third trace axis: is each requirement's code actually covered, and is there
    # code no scenario exercises (spec_gap). Deterministic report; feeds planner_replan.
    from lib.coverage_backed import parse_coverage, trace_coverage
    plan = parse_source(a.front, speckit=_speckit(a.speckit))
    cov = parse_coverage(pathlib.Path(a.coverage).read_text(encoding="utf-8"))
    _emit(trace_coverage(plan, cov))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="athena")
    p.add_argument("--version", action="version", version=f"athena {__version__}")
    p.add_argument("--speckit", choices=("on", "off", "auto"), default="auto")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate"); v.add_argument("front"); v.set_defaults(fn=cmd_validate)
    c = sub.add_parser("compile"); c.add_argument("front"); c.set_defaults(fn=cmd_compile)
    st = sub.add_parser("stats"); st.add_argument("front"); st.set_defaults(fn=cmd_stats)
    h = sub.add_parser("hermes-plan")
    h.add_argument("front", nargs="?", default=""); h.add_argument("-o", "--out", default="")
    h.add_argument("--plan-id", dest="plan_id", default=""); h.add_argument("--created", default="")
    h.set_defaults(fn=cmd_hermes_plan)
    s = sub.add_parser("seam"); s.add_argument("name"); s.add_argument("front", nargs="?", default="")
    s.add_argument("--coverage", default="")
    s.add_argument("--map", default="", help="clause map for seam.map_fresh "
                                             "(default .athena/clause_map.json)")
    s.set_defaults(fn=cmd_seam)
    tc = sub.add_parser("trace-coverage"); tc.add_argument("front")
    tc.add_argument("--coverage", required=True)
    tc.set_defaults(fn=cmd_trace_coverage)

    # --- v3.3: contract (numbered clauses) + executable-spec ledger ---
    ct = sub.add_parser("contract", help="query the requirement contract")
    csub = ct.add_subparsers(dest="contract_cmd", required=True)

    def _rep(name, fn, *, gate=False):
        sp = csub.add_parser(name)
        sp.add_argument("contract", nargs="?", default="contract.md")
        sp.add_argument("--scenarios", default="")
        sp.add_argument("--ledger", default="")
        sp.add_argument("--text", action="store_true", help="human table instead of JSON")
        if gate:
            sp.add_argument("--gate", action="store_true",
                            help="exit 1 when the report is not clean (CI use)")
        else:
            sp.set_defaults(gate=False)
        sp.set_defaults(fn=fn)
        return sp

    cl = csub.add_parser("lint"); cl.add_argument("contract", nargs="?", default="contract.md")
    cl.add_argument("--strict", action="store_true",
                    help="fail on wording warnings too (non-atomic, vague, duplicated)")
    cl.set_defaults(fn=cmd_contract_lint)
    _rep("coverage", cmd_contract_coverage, gate=True)
    _rep("todo", cmd_contract_todo)
    _rep("drift", cmd_contract_drift, gate=True)

    cp = csub.add_parser("pin")
    cp.add_argument("scenarios", nargs="?", default="")
    cp.add_argument("--contract", default="contract.md")
    cp.add_argument("--write", action="store_true", help="edit scenarios.md in place")
    cp.set_defaults(fn=cmd_contract_pin)

    cm = csub.add_parser("map", help="derive the per-clause file:line map by running each "
                                     "spec alone under coverage")
    cm.add_argument("contract", nargs="?", default="contract.md")
    cm.add_argument("--scenarios", default="")
    cm.add_argument("--source", action="append", default=["lib"],
                    metavar="PKG", help="coverage source root (repeatable)")
    cm.add_argument("--clause", default="", help="map only this clause prefix")
    cm.add_argument("--skip-tag", dest="skip_tag", action="append", default=[])
    cm.add_argument("--cwd", default=".")
    cm.add_argument("--jobs", type=int, default=0)
    cm.add_argument("--workdir", default=".athena/clause_map")
    cm.add_argument("-o", "--out", default=".athena/clause_map.json")
    cm.set_defaults(fn=cmd_contract_map)

    co = csub.add_parser("owners", help="which clauses own a file:line")
    co.add_argument("target", metavar="FILE:LINE")
    co.add_argument("--map", default=".athena/clause_map.json")
    co.add_argument("--contract", default="contract.md")
    co.set_defaults(fn=cmd_contract_owners)

    ci = csub.add_parser("import"); ci.add_argument("spec")
    ci.add_argument("-o", "--out", default="")
    ci.add_argument("--section", default="EARS Acceptance Criteria")
    ci.add_argument("--title", default="")
    ci.set_defaults(fn=cmd_contract_import)

    sr = sub.add_parser("spec", help="run the executable specs")
    srsub = sr.add_subparsers(dest="spec_cmd", required=True)
    srun = srsub.add_parser("run")
    srun.add_argument("scenarios", nargs="?", default="scenarios.md")
    srun.add_argument("--contract", default="")
    srun.add_argument("--clause", default="", help="only specs whose clause id starts with this")
    srun.add_argument("--spec-id", dest="spec_id", default="", help="only specs with this id prefix")
    srun.add_argument("--skip-tag", dest="skip_tag", action="append", default=[],
                      metavar="TAG", help="skip specs whose CLAUSE carries this tag "
                                          "(repeatable) — e.g. --skip-tag slow")
    srun.add_argument("--only-tag", dest="only_tag", action="append", default=[],
                      metavar="TAG", help="run only specs whose clause carries this tag")
    srun.add_argument("--cwd", default=".")
    srun.add_argument("--jobs", type=int, default=0, help="0 = one worker per logical core")
    srun.add_argument("--env", action="append", default=[], metavar="KEY=VALUE",
                      help="pin an env var for the spec processes (repeatable), e.g. "
                           "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1")
    srun.add_argument("--timeout", type=int, default=120)
    srun.add_argument("-o", "--out", default=".athena/spec_ledger.json")
    srun.set_defaults(fn=cmd_spec_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # gates must fail-closed with STRUCTURED output, never a raw traceback
    try:
        return args.fn(args)
    except ParseError as e:
        _emit({"passed": False, "error": f"parse: {e}"})
        return 1
    except FileNotFoundError as e:
        _emit({"passed": False, "error": f"file: {e}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
