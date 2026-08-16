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
        from lib.clause_map import digests
        r = seams.seam_map_fresh(
            cmap, plan.contract, plan.scenarios,
            scenario_version=hash_text(scen.read_text(encoding="utf-8")) if scen.exists() else "",
            clause_digests=digests(cmap, _sources_of(cmap)))
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


def cmd_contract_outline(a) -> int:
    # "What are the parts of this system?" — answered from the artifacts rather than from a
    # hand-written architecture page that nobody re-derives.
    from lib.contract_report import coverage
    from lib.outline import outline, render

    c = _load_contract(a)
    cov = coverage(c, _load_scenarios(a, anchor=a.contract))
    map_path = a.map or str(pathlib.Path(a.contract).with_name("clause_map.json"))
    cmap = json.loads(_read(map_path)) if pathlib.Path(map_path).exists() else {}
    rep = outline(c, cov, cmap)
    if a.text:
        print(render(rep))
    else:
        _emit(rep)
    return 0


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
    from lib.clause_map import collect, digests, owned_lines, stale_clauses
    from lib.spec_runner import select

    contract = _load_contract(a)
    scen_path = a.scenarios or _sibling(a.contract, "scenarios.md")
    scenarios = select(_load_scenarios(a, anchor=a.contract), clause_prefix=a.clause,
                       contract=contract, skip_tags=tuple(a.skip_tag))

    # Incremental: re-derive ONLY the clauses whose owned lines moved (plus any clause the
    # map has never seen). Everything else in the map is still true, and re-running its
    # specs would buy nothing but minutes.
    base, rebuilt = {}, ()
    if a.incremental and pathlib.Path(a.out).exists():
        base = json.loads(_read(a.out))
        current = digests(base, _sources_of(base))
        drifted = set(stale_clauses(base, current))
        unseen = {c.id for c in contract.live()} - set(base.get("clauses") or {})
        rebuilt = tuple(sorted(drifted | unseen))
        scenarios = tuple(s for s in scenarios if s.requirement_key in set(rebuilt))
        if not scenarios:
            # Nothing to re-derive, but the CONTRACT pin may still have moved — a note, a
            # draft clause, any edit that owns no lines changes `contract.version` without
            # changing what anybody owns. Returning here without re-pinning left the map
            # permanently stale to `seam.map_fresh`, with no incremental way back: the only
            # cure was a full rebuild that would have derived byte-identical ownership.
            cmap = _finish_map((), contract, scen_path, base=base, rebuilt=())
            pathlib.Path(a.out).write_text(json.dumps(cmap, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
            _emit({"map": a.out, "rebuilt": [], "kept": len(cmap.get("clauses") or {}),
                   "repinned": cmap["contract_version"],
                   "note": "every clause still owns the lines it owned; re-pinned only"})
            return 0
    spec_lines = collect(scenarios, sources=tuple(a.source), workdir=a.workdir,
                         cwd=a.cwd, jobs=a.jobs)
    cmap = _finish_map(spec_lines, contract, scen_path, base=base, rebuilt=rebuilt)
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(cmap, indent=2, sort_keys=True) + "\n",
                                   encoding="utf-8")
    owned = owned_lines(cmap)
    half = cmap.get("partial") or {}
    _emit({"map": a.out, "clauses_mapped": len(cmap["clauses"]),
           "specs": len(spec_lines), "files": len(owned),
           "owned_lines": sum(len(v) for v in owned.values()),
           # Owned lines with an arm never taken: the depth signal the line count hides.
           # DISTINCT, like owned_lines. The first cut summed the per-clause counts and
           # printed 2113 next to 1694 owned — a "more than all of them" number, produced by
           # comparing a sum-with-repeats against a union. The real figure was 229.
           "half_proved_lines": len({(p, ln) for f in half.values()
                                     for p, lns in f.items() for ln in lns}),
           "clauses_with_half_proved": len(half),
           # A clause whose entry is EMPTY is not mapped, whatever the key count says. The
           # first cut tested `c.id not in cmap["clauses"]`, so 25 clauses that collected
           # no coverage at all were written as `{}` and reported as fully mapped. A spec
           # that ran and honestly touched none of the source roots is the exception, and
           # `collected` is how the map tells the two apart.
           "unmapped_clauses": sorted(
               c.id for c in contract.live()
               if not (cmap["clauses"].get(c.id) or {})
               and c.id not in set(cmap.get("collected") or ()))})
    return 0


def _sources_of(cmap: dict) -> dict:
    """Read every file the map references once: {path: text}. The digest functions are pure,
    so this is where the I/O lives."""
    out = {}
    for files in (cmap.get("clauses") or {}).values():
        for path in files:
            if path not in out and pathlib.Path(path).exists():
                out[path] = _read(path)
    return out


def _finish_map(spec_lines, contract, scen_path, *, base=None, rebuilt=()) -> dict:
    """Fold the collected lines into a map and pin each clause to the lines it owns."""
    from lib.clause_map import build, digests, merge
    from lib.versioning import hash_text
    sv = hash_text(_read(str(scen_path)))
    draft = (merge(base, spec_lines, contract_version=contract.version, scenario_version=sv,
                   rebuilt=tuple(rebuilt))
             if base else build(spec_lines, contract_version=contract.version,
                                scenario_version=sv))
    # second pass: the digests can only be computed once the final line sets are known
    return merge(draft, (), contract_version=contract.version, scenario_version=sv,
                 clause_digests=digests(draft, _sources_of(draft)))


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


def _spec_cmds(scenarios) -> dict:
    """{scenario id: (clause id, run_cmd)} — the binding both the mutation runner and the
    judge corpus need."""
    return {s.id: (s.requirement_key, s.run_cmd) for s in scenarios}


def cmd_mutate(a) -> int:
    if getattr(a, "restore", False):
        from lib.mutation import recover
        restored = recover(lock_path=a.lock)
        _emit({"restored": list(restored), "lock": a.lock})
        return 0

    # EFFECTFUL and destructive-in-flight: it rewrites source files and restores them. Runs
    # only what the map says is affected, and never touches the gates.
    import subprocess
    from lib.mutation import (default_mirror, hunt, isolate, recover, red_specs,
                              scoped_specs, snapshot, summarize, target_lines)

    contract = _load_contract(a)
    scenarios = _load_scenarios(a, anchor=a.contract)
    cmap = json.loads(_read(a.map))
    owned = target_lines(cmap, clause_prefix=a.clause, only=a.only)
    targets = {p: {"source": _read(p), "lines": sorted(lines)}
               for p, lines in sorted(owned.items())
               if p.startswith(tuple(a.source)) and pathlib.Path(p).exists()}

    # A spec that is RED on clean source cannot witness anything: its non-zero exit would
    # read as "the mutant was noticed". The rule was written down as a clause and proved in
    # the library, and then no caller passed `exclude` — so the product path never had it.
    # The ledger already records every spec's verdict, which makes the cheap answer the
    # honest one; `--baseline run` re-measures when the ledger is not trusted.
    spec_cmds = _spec_cmds(scenarios)
    excluded, unrun = (), 0
    if a.baseline == "ledger":
        led = _ledger(a) or {}
        excluded = red_specs(spec_cmds, led)
        seen = {r.get("scenario", "") for r in led.get("results", [])}
        unrun = sum(1 for sid in spec_cmds if sid not in seen)

    def runner(cmd):
        try:
            return subprocess.run(cmd.split(), cwd=a.cwd, capture_output=True, text=True,
                                  timeout=a.timeout).returncode
        except subprocess.TimeoutExpired:
            return 124

    def writer(path, text):
        pathlib.Path(path).write_text(text, encoding="utf-8")

    # The harness does not mutate the working tree. Two runs were killed mid-mutation and
    # left a mutant in lib/ despite `finally`, so everything happens in a mirror: the worst
    # a kill can leave behind now is a temp folder.
    mirror = isolate(".", a.mirror or default_mirror(".")) if a.isolate else "."
    if a.isolate:
        def writer(path, text):                                   # noqa: F811
            (pathlib.Path(mirror) / path).write_text(text, encoding="utf-8")

        def runner(cmd):                                          # noqa: F811
            try:
                return subprocess.run(cmd.split(), cwd=mirror, capture_output=True,
                                      text=True, timeout=a.timeout).returncode
            except subprocess.TimeoutExpired:
                return 124
    else:
        snapshot(targets, lock_path=a.lock)
    try:
        if a.baseline == "run":
            from lib.mutation import baseline as measure_baseline
            candidates = {c for path, spec in targets.items() for ln in spec["lines"]
                          for c in scoped_specs(cmap, spec_cmds, path, ln)}
            excluded = measure_baseline(spec_cmds, sorted(candidates), runner=runner)
        res = hunt(cmap, spec_cmds, targets, runner=runner, writer=writer,
                   limit_per_line=a.per_line, max_mutants=a.max_mutants,
                   max_specs=a.max_specs, exclude=tuple(excluded))
    finally:
        if not a.isolate:
            recover(lock_path=a.lock)
    rep = summarize(res)
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n",
                                       encoding="utf-8")
    _emit({k: rep[k] for k in ("mutants", "killed", "survived", "score")}
          | {"survivors": [f"{s['path']}:{s['line']} ({s['kind']})" for s in rep["survivors"]][:20],
             "out": a.out})
    return 0


def cmd_judge_corpus(a) -> int:
    # Builds the LABELLED set from pairs this repo already proves, plus mechanical
    # degradations. No model is involved in producing the ground truth (step 1).
    import re as _re
    from lib.judge import Pair, build_corpus, spec_function

    contract = _load_contract(a)
    scenarios = _load_scenarios(a, anchor=a.contract)
    pairs = []
    for s in scenarios:
        clause = contract.by_id(s.requirement_key)
        node = next((tok for tok in s.run_cmd.split() if "::" in tok), "")
        path, _, func = node.partition("::")
        if not (clause and path and func and pathlib.Path(path).exists()):
            continue
        src = spec_function(_read(path), _re.sub(r"\[.*", "", func))
        if not src:
            continue
        pairs.append(Pair(id=f"{clause.id}/{s.id}", clause_id=clause.id,
                          clause_text=clause.text, spec_id=s.id, spec_source=src,
                          label="proves"))
    corpus = build_corpus(tuple(pairs))
    payload = {"schema": "athena.judge_corpus/1", "contract_version": contract.version,
               "pairs": [vars(p) for p in corpus]}
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False,
                                              sort_keys=True) + "\n", encoding="utf-8")
    from collections import Counter
    _emit({"corpus": a.out, "pairs": len(corpus),
           "proves": sum(1 for p in corpus if p.label == "proves"),
           "vacuous": sum(1 for p in corpus if p.label == "vacuous"),
           "by_defect": dict(Counter(p.defect for p in corpus if p.defect))})
    return 0


def cmd_judge_eval(a) -> int:
    # Scores a judge's decisions against the labelled corpus and the fixed thresholds.
    # ADVISORY by construction: it prints eligibility, it never wires anything (step 0).
    from lib.judge import Pair, is_gate_eligible, score
    payload = json.loads(_read(a.corpus))
    corpus = tuple(Pair(**p) for p in payload["pairs"])
    decisions = json.loads(_read(a.decisions)) if a.decisions else {}
    rep = score(corpus, decisions)
    _emit({**rep, "gate_eligible": is_gate_eligible(rep),
           "note": "advisory only — no gate reads this"})
    return 0 if rep["passes"] else 1


def _parse_front_auto(front: str, speckit_arg: str):
    """Read plan.md OR tasks.md without making the user know which parser to ask for.

    `init` scaffolds a canonical plan.md while the toggle defaults to Spec-Kit, so the two
    quick-start lines contradicted each other and the second one failed. Auto-detect: try the
    toggle, fall back to the other front on a parse error.
    """
    try:
        return parse_with_provenance(front, speckit=_speckit(speckit_arg))
    except ParseError:
        return parse_with_provenance(front, speckit=not (_speckit(speckit_arg) is not False))


def cmd_init(a) -> int:
    """Scaffold a feature already wired clause -> spec -> task, so the first check PASSES."""
    from lib.scaffold import next_steps, render_files
    dest = pathlib.Path(a.path)
    dest.mkdir(parents=True, exist_ok=True)
    files = render_files(title=a.title or dest.name.replace("-", " ").title(),
                         run_cmd=a.run_cmd, files=a.files,
                         dir_hint=str(dest).replace("\\", "/"))
    written = []
    for name, text in sorted(files.items()):
        target = dest / name
        if target.exists() and not a.force:
            continue                      # never clobber a real contract by accident
        target.write_text(text, encoding="utf-8")
        written.append(str(target))
    print(next_steps(str(dest), len(written)))
    _emit({"created": written, "skipped": sorted(set(str(dest / n) for n in files) - set(written))})
    return 0


def cmd_check(a) -> int:
    """The product surface: the whole loop, one verdict, one exit code.

    Order is upstream-first — a broken contract makes every downstream report meaningless,
    so it fails there and says so instead of drowning the user in consequences.
    """
    import datetime
    from lib.check import build, render
    from lib.contract import critique, lint
    from lib.contract_report import coverage as cov_report, drift as drift_report, todo as todo_report
    from lib.spec_runner import load_ledger, make_ledger, run_specs, select, write_ledger
    from lib.versioning import hash_text

    contract = _load_contract(a)
    scen_path = a.scenarios or _sibling(a.contract, "scenarios.md")
    scenarios = _load_scenarios(a, anchor=a.contract)

    # A path the user NAMED but that is absent is an error; a path the tool GUESSED and did
    # not find simply means that step cannot run. An audit showed --map with a typo printing
    # "verdict: PASS" having checked nothing, so the two cases are now distinguished here.
    named = [p for p in ((a.ledger if not a.run else None), a.map, a.judge or None,
                         a.front or None) if p]
    missing = [p for p in named if not pathlib.Path(p).exists()]
    # Guessed defaults live NEXT TO THE CONTRACT, not in the current directory. An audit ran
    # `check` on a scaffolded project from inside this repo and the reverse leg silently
    # judged it against THIS repo's .athena/clause_map.json — a gate answering about the
    # wrong codebase is worse than one that does not run.
    here = pathlib.Path(a.contract).resolve().parent
    ledger_path = a.ledger or str(here / ".athena" / "spec_ledger.json")
    map_path = a.map or str(here / ".athena" / "clause_map.json")

    ledger = load_ledger(ledger_path) if pathlib.Path(ledger_path).exists() else {}
    if a.run:
        picked = select(scenarios, contract=contract, skip_tags=tuple(a.skip_tag))
        env = dict(kv.split("=", 1) for kv in a.env if "=" in kv) or None
        results = run_specs(picked, cwd=a.cwd, timeout=a.timeout, jobs=a.jobs, env=env)
        ledger = make_ledger(results, contract=contract,
                             scenario_version=hash_text(_read(scen_path)),
                             ts=datetime.datetime.now(datetime.timezone.utc)
                             .isoformat(timespec="seconds"))
        write_ledger(ledger, ledger_path)

    gates = {}
    if a.front and pathlib.Path(a.front).exists():
        plan = _parse_front_auto(a.front, a.speckit)
        if plan.contract is not None:
            r = seams.seam_contract_bound(plan.contract, plan.scenarios)
            gates["contract_bound"] = {"passed": r.passed, "issues": list(r.issues)}
            # compile is part of the loop: a front that names a retired spec raises here,
            # and before this step `check` reported PASS while `compile` was broken.
            try:
                compile(plan)
                gates["compile"] = {"passed": True, "issues": []}
            except CompileError as e:
                gates["compile"] = {"passed": False, "issues": [str(e)]}
            if pathlib.Path(map_path).exists():
                from lib.clause_map import digests
                cmap = json.loads(_read(map_path))
                scen = pathlib.Path(a.front).parent / "scenarios.md"
                mr = seams.seam_map_fresh(
                    cmap, plan.contract, plan.scenarios,
                    scenario_version=hash_text(scen.read_text(encoding="utf-8"))
                    if scen.exists() else "",
                    clause_digests=digests(cmap, _sources_of(cmap)))
                gates["map_fresh"] = {"passed": mr.passed, "issues": list(mr.issues)}

    mutation = None
    if a.deep and pathlib.Path(map_path).exists():
        mutation = _deep_mutation(a, contract, scenarios)

    judge = None
    if a.judge and pathlib.Path(a.judge).exists():
        from lib.judge import Pair, score
        payload = json.loads(_read(a.judge))
        decisions = json.loads(_read(a.judge_decisions)) if a.judge_decisions else {}
        judge = score(tuple(Pair(**p) for p in payload["pairs"]),
                      decisions.get("decisions", decisions))

    report = build(missing_inputs=tuple(missing), allow_partial=a.allow_partial,
                   lint_issues=lint(contract), critique_warnings=critique(contract),
                   coverage=cov_report(contract, scenarios),
                   ledger_totals=ledger.get("totals") if ledger else None,
                   todo=todo_report(contract, scenarios, ledger),
                   drift=drift_report(contract, scenarios, ledger),
                   gates=gates, mutation=mutation, judge=judge,
                   strict_wording=a.strict)
    print(render(report) if a.text else json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["passed"] else 1


def _deep_mutation(a, contract, scenarios) -> dict:
    """Mutation over the clauses that DRIFTED — the sweep nobody can afford whole-repo."""
    import subprocess
    from lib.clause_map import digests, stale_clauses
    from lib.mutation import default_mirror, hunt, isolate, summarize

    cmap = json.loads(_read(a.map or ".athena/clause_map.json"))
    drifted = set(stale_clauses(cmap, digests(cmap, _sources_of(cmap))))
    if not drifted:
        # Nothing moved, so there is nothing new to re-prove. Falling back to a full sweep
        # here is the expensive-default trap: 1541 owned lines, up to 129 specs per mutant,
        # and it looked like diligence. A whole-repo sweep is an explicit choice.
        if not a.deep_all:
            return {"mutants": 0, "killed": 0, "survived": 0, "survivors": [],
                    "blocking": a.strict, "scope": [],
                    "note": "no clause drifted — nothing to re-prove (use --deep-all to sweep)"}
        drifted = {c.id for c in contract.live()}
    owned: dict = {}
    for cid, files in (cmap.get("clauses") or {}).items():
        if cid not in drifted:
            continue
        for p, lines in files.items():
            owned[p] = sorted(set(owned.get(p, ())) | set(lines))
    targets = {p: {"source": _read(p), "lines": lines} for p, lines in sorted(owned.items())
               if pathlib.Path(p).exists()}
    if not targets:
        return {"mutants": 0, "killed": 0, "survived": 0, "survivors": [],
                "blocking": a.strict, "scope": sorted(drifted)[:10]}
    mirror = isolate(".", a.mirror or default_mirror("."))

    def runner(cmd):
        try:
            return subprocess.run(cmd.split(), cwd=mirror, capture_output=True, text=True,
                                  timeout=a.timeout).returncode
        except subprocess.TimeoutExpired:
            return 124

    def writer(path, text):
        (pathlib.Path(mirror) / path).write_text(text, encoding="utf-8")

    res = hunt(cmap, _spec_cmds(scenarios), targets, runner=runner, writer=writer,
               max_mutants=a.max_mutants, max_specs=a.max_specs)
    return {**summarize(res), "blocking": a.strict, "scope": sorted(drifted)[:10]}


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
    cm.add_argument("--incremental", action="store_true",
                    help="re-derive only the clauses whose owned lines moved")
    cm.set_defaults(fn=cmd_contract_map)

    cot = csub.add_parser("outline", help="the shape of the system, derived: what each "
                                          "clause group guarantees and which modules it owns")
    cot.add_argument("contract", nargs="?", default="contract.md")
    cot.add_argument("--scenarios", default="")
    cot.add_argument("--map", default="", help="clause map (default: beside the contract)")
    cot.add_argument("--text", action="store_true")
    cot.set_defaults(fn=cmd_contract_outline)

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

    ini = sub.add_parser("init", help="scaffold contract/scenarios/plan for a new feature")
    ini.add_argument("path")
    ini.add_argument("--title", default="")
    ini.add_argument("--run-cmd", dest="run_cmd", default="",
                     help="the command that proves the first clause (default: the example "
                          "test the scaffold writes next to it)")
    ini.add_argument("--files", default="")
    ini.add_argument("--force", action="store_true", help="overwrite existing files")
    ini.set_defaults(fn=cmd_init)

    ck = sub.add_parser("check", help="the whole loop: one verdict, one exit code")
    ck.add_argument("contract", nargs="?", default="contract.md")
    ck.add_argument("--scenarios", default="")
    ck.add_argument("--front", default="", help="plan.md, to also run the fail-closed gates")
    # default=None distinguishes "the user named this path" from "the tool guessed one".
    # A NAMED path that is absent is an error; a guessed one that is absent simply means the
    # step cannot run, and the leg is reported INCOMPLETE rather than green.
    ck.add_argument("--ledger", default=None)
    ck.add_argument("--map", default=None)
    ck.add_argument("--run", action="store_true", help="run the specs now instead of reading a ledger")
    ck.add_argument("--deep", action="store_true", help="also mutate the drifted clauses")
    ck.add_argument("--deep-all", dest="deep_all", action="store_true",
                    help="mutate EVERY live clause, not only the drifted ones (slow: minutes "
                         "to hours; this is the sweep, not the loop)")
    ck.add_argument("--strict", action="store_true", help="wording + mutation findings block too")
    ck.add_argument("--judge", default="", help="judge corpus, to fold in an advisory score")
    ck.add_argument("--judge-decisions", dest="judge_decisions", default="")
    ck.add_argument("--skip-tag", dest="skip_tag", action="append", default=[])
    ck.add_argument("--env", action="append", default=[], metavar="KEY=VALUE")
    ck.add_argument("--jobs", type=int, default=0)
    ck.add_argument("--timeout", type=int, default=400)
    ck.add_argument("--max-mutants", dest="max_mutants", type=int, default=20)
    ck.add_argument("--max-specs", dest="max_specs", type=int, default=12,
                    help="spec budget per mutant; exceeding it reports UNDETERMINED, never "
                         "'survived' (0 = no budget)")
    ck.add_argument("--mirror", default="")
    ck.add_argument("--cwd", default=".")
    ck.add_argument("--text", action="store_true")
    ck.add_argument("--allow-partial", dest="allow_partial", action="store_true",
                    help="accept a run where a whole leg produced no evidence (fast lane)")
    ck.set_defaults(fn=cmd_check)

    mu = sub.add_parser("mutate", help="break the lines a clause owns; do its specs notice?")
    mu.add_argument("contract", nargs="?", default="contract.md")
    mu.add_argument("--scenarios", default="")
    mu.add_argument("--map", default=".athena/clause_map.json")
    mu.add_argument("--clause", default="", help="only clauses with this id prefix")
    mu.add_argument("--source", action="append", default=["lib"])
    mu.add_argument("--per-line", dest="per_line", type=int, default=1)
    mu.add_argument("--max-specs", dest="max_specs", type=int, default=0)
    mu.add_argument("--only", default="all", metavar="FILTER[+FILTER]",
                    help="which owned lines to attack: all | exclusive (owned by exactly "
                         "one clause) | half-proved (an arm nothing took). Compose with "
                         "'+', e.g. exclusive+half-proved for the sharpest sweep")
    mu.add_argument("--baseline", default="ledger", choices=("ledger", "run", "none"),
                    help="how to find specs that are red BEFORE mutating (they cannot be "
                         "witnesses): read the ledger, re-run them, or skip the check")
    mu.add_argument("--ledger", default="")
    mu.add_argument("--max-mutants", dest="max_mutants", type=int, default=0,
                    help="stop after N mutants (0 = no cap)")
    mu.add_argument("--lock", default=".athena/mutation_lock.json")
    mu.add_argument("--mirror", default="",
                    help="scratch tree the mutation runs in (default: a temp mirror)")
    mu.add_argument("--in-place", dest="isolate", action="store_false", default=True,
                    help="mutate the working tree itself (NOT recommended; uses the lock)")
    mu.add_argument("--restore", action="store_true",
                    help="put back sources left behind by a killed run, then exit")
    mu.add_argument("--cwd", default="."); mu.add_argument("--timeout", type=int, default=180)
    mu.add_argument("-o", "--out", default="")
    mu.set_defaults(fn=cmd_mutate)

    ju = sub.add_parser("judge", help="the judge PILOT: corpus + scoring, never a gate")
    jsub = ju.add_subparsers(dest="judge_cmd", required=True)
    jc = jsub.add_parser("corpus"); jc.add_argument("contract", nargs="?", default="contract.md")
    jc.add_argument("--scenarios", default="")
    jc.add_argument("-o", "--out", default=".athena/judge_corpus.json")
    jc.set_defaults(fn=cmd_judge_corpus)
    je = jsub.add_parser("eval"); je.add_argument("corpus", nargs="?",
                                                  default=".athena/judge_corpus.json")
    je.add_argument("--decisions", default="")
    je.set_defaults(fn=cmd_judge_eval)

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
