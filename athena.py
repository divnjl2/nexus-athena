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
import re
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


def _scan_markers(roots, cwd: str = "."):
    """EFFECTFUL: (markers, {path: text}) for every source file under the given roots."""
    from lib.markers import scan
    base = pathlib.Path(cwd)
    found, sources = [], {}
    for root in roots:
        rp = base / root
        files = [rp] if rp.is_file() else sorted(rp.rglob("*.py")) if rp.exists() else []
        for f in files:
            rel = f.relative_to(base).as_posix() if f.is_relative_to(base) else f.as_posix()
            text = _read(str(f))
            hits = scan(text, path=rel)
            if hits:
                sources[rel] = text
                found.extend(hits)
    return tuple(found), sources


def cmd_contract_markers(a) -> int:
    # `@relation(C-9.22, scope=function)` — StrictDoc's notation, verified against OUR map:
    # an annotation nobody can back with executed lines is decoration, not traceability.
    from lib.markers import check
    contract = _load_contract(a)
    map_path = a.map or str(pathlib.Path(a.contract).with_name("clause_map.json"))
    cmap = json.loads(_read(map_path)) if pathlib.Path(map_path).exists() else {"clauses": {}}
    markers, sources = _scan_markers(a.source or ["lib"], cwd=a.cwd)
    rep = check(markers, contract, cmap, sources)
    _report_out(a, rep, title="code -> clause markers")
    return 0 if rep["passed"] or not a.gate else 1


def cmd_contract_export(a) -> int:
    # Publish the clause index so ANOTHER repository can reference these requirements
    # without a checkout. Shapes are borrowed (sphinx-needs, OpenFastTrace) on purpose.
    from lib.contract_report import coverage
    from lib.export import render_needs, to_needs, to_oft

    contract = _load_contract(a)
    scen = _load_scenarios(a, anchor=a.contract)
    map_path = a.map or str(pathlib.Path(a.contract).with_name("clause_map.json"))
    cmap = json.loads(_read(map_path)) if pathlib.Path(map_path).exists() else {}

    if a.format == "oft":
        text = to_oft(contract, doc_id=a.project or contract.title)
    else:
        text = render_needs(to_needs(contract, project=a.project, version=a.version,
                                     coverage=coverage(contract, scen), clause_map=cmap))
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
        _emit({"export": a.out, "format": a.format, "clauses": len(contract.clauses),
               "project": a.project or contract.title})
    else:
        print(text, end="")
    return 0


def cmd_contract_refs(a) -> int:
    # Clause -> DOCUMENT links, checked the way Doorstop checks them: a link carries the
    # fingerprint of what was reviewed, and a moved target is a SUSPECT LINK, not a failure
    # of the code. Targets resolve relative to the CONTRACT, never to the caller's cwd.
    from lib.docrefs import apply_repin, check, repin, targets

    contract = _load_contract(a)
    base = pathlib.Path(a.contract).resolve().parent
    sources = {}
    for tgt in targets(contract):
        path = (base / tgt)
        sources[tgt] = _read(str(path)) if path.exists() else None

    if a.write:
        edits = repin(contract, sources)
        text, applied = apply_repin(_read(a.contract), edits)
        if applied:
            pathlib.Path(a.contract).write_text(text, encoding="utf-8")
        _emit({"contract": a.contract, "repinned": applied,
               "clauses": sorted(edits), "note": "re-pinning is REVIEWING: read the diff"})
        return 0

    rep = check(contract, sources)
    _report_out(a, rep, title="clause -> document references")
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
    results = run_specs(picked, cwd=a.cwd, timeout=a.timeout, jobs=a.jobs, env=env,
                        batch=not a.no_batch, contract=contract)
    ledger = make_ledger(
        results, contract=contract,
        scenario_version=hash_text(_read(scen_path)),
        ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )
    out = write_ledger(ledger, a.out)
    _append_run(ledger, pathlib.Path(cpath if contract is not None else scen_path).parent)
    _emit({"ledger": str(out), **ledger["totals"],
           "red": [r["scenario"] for r in ledger["results"] if not r["passed"]]})
    return 0 if ledger["totals"]["failed"] == 0 else 1


def _append_run(ledger: dict, feature_dir: pathlib.Path) -> pathlib.Path:
    """EFFECTFUL: one line per spec run in `<feature>/.athena/runs.jsonl` (team-layer C-6.2).
    The record metrics are read from, never remembered."""
    from lib.metrics import record
    path = feature_dir / ".athena" / "runs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record(ledger.get("totals", {}), ts=ledger.get("ts", "")),
                            ensure_ascii=False) + "\n")
    return path


def cmd_contract_map(a) -> int:
    # EFFECTFUL: run each spec ALONE under coverage so its lines can be attributed to the
    # clause it proves. This is the artifact that upgrades the reverse leg from file-level
    # ("this contract claims lib/seams.py") to line-level ("it owns these 40 lines of it").
    from lib.clause_map import (collect, digests, owned_lines, spec_digests,
                                stale_clauses, stale_specs)
    from lib.spec_runner import select

    contract = _load_contract(a)
    scen_path = a.scenarios or _sibling(a.contract, "scenarios.md")
    scenarios = select(_load_scenarios(a, anchor=a.contract), clause_prefix=a.clause,
                       contract=contract, skip_tags=tuple(a.skip_tag))
    # the incremental branch narrows `scenarios` to what must be re-derived; the spec-body
    # pins have to cover ALL of them or a skipped spec would never be seen changing again
    all_scenarios = scenarios
    # WHICH codebase this map is about. Recorded so a map can never answer about a
    # project it has not seen; derived from the git remote when nobody says.
    subject = a.purl if a.purl != "auto" else _git_purl(a.cwd)

    # Incremental: re-derive ONLY the clauses whose owned lines moved (plus any clause the
    # map has never seen). Everything else in the map is still true, and re-running its
    # specs would buy nothing but minutes.
    base, rebuilt = {}, ()
    if a.incremental and pathlib.Path(a.out).exists():
        base = json.loads(_read(a.out))
        current = digests(base, _sources_of(base))
        drifted = set(stale_clauses(base, current))
        # ...and a clause whose SPEC BODY moved. Pinning only the clause text and the owned
        # code missed the third input: strengthening a test to cover the arm it had been
        # skipping changed the branch evidence and moved no digest, so the rebuild said
        # "nothing to re-derive" and `partial` kept answering from before the fix.
        now_specs = spec_digests(scenarios, _test_sources(scenarios))
        moved = set(stale_specs(base, now_specs))
        drifted |= {s.requirement_key for s in scenarios if s.id in moved}
        unseen = {c.id for c in contract.live()} - set(base.get("clauses") or {})
        rebuilt = tuple(sorted(drifted | unseen))
        scenarios = tuple(s for s in scenarios if s.requirement_key in set(rebuilt))
        if not scenarios:
            # Nothing to re-derive, but the CONTRACT pin may still have moved — a note, a
            # draft clause, any edit that owns no lines changes `contract.version` without
            # changing what anybody owns. Returning here without re-pinning left the map
            # permanently stale to `seam.map_fresh`, with no incremental way back: the only
            # cure was a full rebuild that would have derived byte-identical ownership.
            cmap = _finish_map((), contract, scen_path, scenarios=all_scenarios,
                               base=base, rebuilt=(), subject=subject)
            pathlib.Path(a.out).write_text(json.dumps(cmap, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
            _emit({"map": a.out, "rebuilt": [], "kept": len(cmap.get("clauses") or {}),
                   "repinned": cmap["contract_version"],
                   "note": "every clause still owns the lines it owned; re-pinned only"})
            return 0
    spec_lines = collect(scenarios, sources=tuple(a.source), workdir=a.workdir,
                         cwd=a.cwd, jobs=a.jobs)
    cmap = _finish_map(spec_lines, contract, scen_path, scenarios=all_scenarios,
                       base=base, rebuilt=rebuilt, subject=subject)
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


def _git_purl(root: str = ".") -> str:
    """EFFECTFUL: derive `pkg:<host>/<owner>/<repo>` from the git remote, or "" if unknown.

    A default nobody has to type is the difference between a subject that gets recorded and
    one that does not. Best-effort on purpose: no remote, no git, no subject — and an
    unstated subject is simply not checked rather than guessed at.
    """
    import subprocess
    try:
        out = subprocess.run(["git", "-C", root, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    url = (out.stdout or "").strip()
    if out.returncode != 0 or not url:
        return ""
    url = url.removesuffix(".git")
    m = re.search(r"(?:https?://|git@|ssh://git@)([^/:]+)[/:](.+)$", url)
    if not m:
        return ""
    host, path = m.group(1).lower(), m.group(2).strip("/")
    kind = {"github.com": "github", "gitlab.com": "gitlab",
            "bitbucket.org": "bitbucket"}.get(host, "generic")
    return f"pkg:{kind}/{path}" if kind != "generic" else f"pkg:generic/{path.split('/')[-1]}"


def _test_sources(scenarios) -> dict:
    """{path: text} for every test module a run_cmd names. I/O, so it lives here."""
    out = {}
    for sc in scenarios or ():
        node = next((tok for tok in sc.run_cmd.split() if "::" in tok), "")
        path = node.partition("::")[0].replace("\\", "/").strip().lstrip("./")
        if path and path not in out and pathlib.Path(path).exists():
            out[path] = _read(path)
    return out


def _finish_map(spec_lines, contract, scen_path, *, scenarios=(), base=None,
                rebuilt=(), subject: str = "") -> dict:
    """Fold the collected lines into a map and pin each clause to the lines it owns."""
    from lib.clause_map import build, digests, merge, spec_digests
    from lib.versioning import hash_text
    sv = hash_text(_read(str(scen_path)))
    sd = spec_digests(scenarios, _test_sources(scenarios))
    draft = (merge(base, spec_lines, contract_version=contract.version, scenario_version=sv,
                   spec_digests=sd, subject=subject, rebuilt=tuple(rebuilt))
             if base else build(spec_lines, contract_version=contract.version,
                                scenario_version=sv, spec_digests=sd, subject=subject))
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


def cmd_judge_graph(a) -> int:
    """Put a judge run's steps in the provenance graph — as an INDEX, never as proof.

    Reads the records the two-stage driver wrote (verdict + reasoning fingerprint) and emits
    one `kind:judgement` node per pair. Emitting is ALL it does by default: `--run` is what
    touches the graph, because a command that writes to a durable store on a dry run is not
    a dry run.
    """
    import subprocess

    from lib.judgement_graph import compile_judgements, summarize

    payload = json.loads(_read(a.decisions))
    records = list((payload.get("records") or {}).values())
    if not records:
        _emit({"judgements": 0, "commands": 0,
               "note": "no records — the one-call driver keeps no reasoning, "
                       "use evals/judge_twostage.py"})
        return 0

    def run(argv):
        return subprocess.run(argv, capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout

    existing = frozenset()
    if a.run:
        from lib.bd_client import fetch_existing_keys
        existing = fetch_existing_keys(a.slug, run=run)

    cmds = compile_judgements(records, slug=a.slug, pin=payload.get("pin"),
                              existing_keys=existing)
    rep = {**summarize(records), "commands": len(cmds), "slug": a.slug, "ran": False}
    if a.run:
        from lib.bd_client import execute
        from lib.plan2beads import CompileResult
        execute(CompileResult(commands=tuple(cmds)), run=run)
        rep["ran"] = True
    elif a.out:
        lines = [" ".join(c.argv) for c in cmds]
        pathlib.Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        rep["out"] = a.out
    _emit(rep)
    return 0


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
    from lib.docrefs import fingerprint
    from lib.scaffold import next_steps, render_files
    dest = pathlib.Path(a.path)
    dest.mkdir(parents=True, exist_ok=True)
    # v3.10: the core is per PROJECT, not per feature. A feature under a project that already
    # has one cites that one by fingerprint (C-1.1); only a project without one gets a new
    # CORE.md, next to the contract. Three levels up covers `features/<name>/` from the root.
    core, core_pin = "CORE.md", ""
    resolved = dest.resolve()
    for anc in list(resolved.parents)[:3]:
        cand = anc / "CORE.md"
        if cand.exists():
            core = os.path.relpath(cand, resolved).replace("\\", "/")
            core_pin = fingerprint(cand.read_text(encoding="utf-8"))
            break
    files = render_files(title=a.title or dest.name.replace("-", " ").title(),
                         run_cmd=a.run_cmd, files=a.files,
                         dir_hint=str(dest).replace("\\", "/"),
                         core=core, core_pin=core_pin)
    written = []
    for name, text in sorted(files.items()):
        target = dest / name
        if target.exists() and not a.force:
            continue                      # never clobber a real contract by accident
        target.write_text(text, encoding="utf-8")
        written.append(str(target))
    print(next_steps(str(dest), len(written),
                     core=str(dest / core) if core == "CORE.md" else str((resolved / core).resolve())))
    _emit({"created": written, "skipped": sorted(set(str(dest / n) for n in files) - set(written)),
           "core": core})
    return 0


def cmd_check(a) -> int:
    """The product surface: the whole loop, one verdict, one exit code."""
    from lib.check import render
    report = _check_report(a)
    print(render(report) if a.text else json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["passed"] else 1


def _check_report(a) -> dict:
    """The whole loop for ONE contract, as a report dict (`gate` folds several of these).

    Order is upstream-first — a broken contract makes every downstream report meaningless,
    so it fails there and says so instead of drowning the user in consequences.
    """
    import datetime
    from lib.check import build
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
        results = run_specs(picked, cwd=a.cwd, timeout=a.timeout, jobs=a.jobs, env=env,
                            batch=not getattr(a, "no_batch", False), contract=contract)
        ledger = make_ledger(results, contract=contract,
                             scenario_version=hash_text(_read(scen_path)),
                             ts=datetime.datetime.now(datetime.timezone.utc)
                             .isoformat(timespec="seconds"))
        write_ledger(ledger, ledger_path)
        _append_run(ledger, here)

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
                    clause_digests=digests(cmap, _sources_of(cmap)),
                    subject=a.purl if a.purl != "auto" else _git_purl(a.cwd))
                gates["map_fresh"] = {"passed": mr.passed, "issues": list(mr.issues)}

    # Clause -> DOCUMENT links belong upstream with the contract: a clause citing an ADR
    # that has been rewritten is a claim nobody re-read, and the code cannot answer for it.
    from lib.docrefs import check as refs_check, targets as ref_targets
    ref_sources = {}
    for tgt in ref_targets(contract):
        tp = here / tgt
        ref_sources[tgt] = _read(str(tp)) if tp.exists() else None
    refs = refs_check(contract, ref_sources) if ref_sources else None

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
                   gates=gates, mutation=mutation, judge=judge, refs=refs,
                   strict_wording=a.strict)
    return report


# --- v3.10: the core layer — sources, lessons, the gate ---------------------------

def cmd_contract_sources(a) -> int:
    # Q4: where did each clause come from. Linear scan; failure signals are the lessons.
    from lib.contract_report import sources
    rep = sources(_load_contract(a))
    _report_out(a, rep, title="clause sources")
    return 0


def cmd_lessons_list(a) -> int:
    from lib.lessons import lessons, specs_for
    contract = _load_contract(a)
    scenarios = _load_scenarios(a, anchor=a.contract)
    items = lessons(contract)
    picked = specs_for(contract, scenarios, items)
    if a.text:
        print("# lessons — clauses born from a failure signal")
        for it in items:
            carried = "" if it["live"] == (it["origin"],) else \
                f" -> {', '.join(it['live']) or 'nothing live'}"
            print(f"  {it['origin']}{carried}  [{it['source']}]  {it['text'][:70]}")
        print(f"\nlessons={len(items)}  specs to rerun={len(picked)}: "
              f"{', '.join(s.id for s in picked) or '-'}")
    else:
        _emit({"lessons": list(items), "specs": [s.id for s in picked]})
    return 0


def cmd_lessons_rerun(a) -> int:
    # THE check that a lesson was learned: the old failure's proof, run again on the
    # pyramid as it stands now. Exit 1 on a forgotten or unproved lesson.
    from lib.lessons import render, report, specs_for
    from lib.spec_runner import run_specs, select
    contract = _load_contract(a)
    scenarios = _load_scenarios(a, anchor=a.contract)
    wanted = specs_for(contract, scenarios)
    picked = select(wanted, contract=contract, skip_tags=tuple(a.skip_tag))
    env = dict(kv.split("=", 1) for kv in a.env if "=" in kv) or None
    results = run_specs(picked, cwd=a.cwd, timeout=a.timeout, jobs=a.jobs, env=env,
                        batch=not a.no_batch, contract=contract)
    # a spec the caller's lane left out is SKIPPED, not silence (C-3.6)
    rep = report(contract, scenarios, results,
                 skipped={s.id for s in wanted} - {s.id for s in picked})
    print(render(rep) if a.text else json.dumps(rep, ensure_ascii=False, sort_keys=True))
    return 0 if rep["passed"] else 1


def _walk(root: pathlib.Path, name: str, depth: int):
    """EFFECTFUL: every `name` under root within `depth` levels, skipping vendored/scratch dirs."""
    from lib.gate import SKIP_DIRS
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        level = len(pathlib.Path(dirpath).relative_to(root).parts)
        dirnames[:] = ([d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
                       if level < depth else [])
        if name in filenames:
            yield pathlib.Path(dirpath) / name


def _gate_one(contract: pathlib.Path, root: pathlib.Path, *, run_specs: bool = False) -> dict:
    """The cheap lane for one contract: committed ledger, no spec run, no clause map.
    With `run_specs` (the refinery, C-2.3) the specs are run now: a merge is judged on what
    the workspace does, not on the ledger someone committed."""
    d = contract.parent
    argv = ["check", str(contract), "--allow-partial", "--cwd", str(root)]
    if run_specs:
        argv.append("--run")
    if (d / "scenarios.md").exists():
        argv += ["--scenarios", str(d / "scenarios.md")]
    if (d / "plan.md").exists():
        argv += ["--front", str(d / "plan.md")]
    if run_specs:
        # the run writes a ledger: never over the committed one, or the workspace is left
        # dirty and the next offer's rebase refuses (measured on the refinery's second offer)
        argv += ["--ledger", str(d / ".athena" / "spec_ledger.json")]
    else:
        for cand in (d / "spec_ledger.json", d / ".athena" / "spec_ledger.json"):
            if cand.exists():
                argv += ["--ledger", str(cand)]
                break
    try:
        shown = str(contract.relative_to(root)).replace("\\", "/")
    except ValueError:
        shown = str(contract)
    try:
        return {"contract": shown, "report": _check_report(build_parser().parse_args(argv))}
    except (ParseError, CompileError, OSError, ValueError, KeyError) as e:
        # a contract whose check cannot run is a FAILING contract, never a skipped one
        return {"contract": shown, "error": f"{type(e).__name__}: {str(e)[:200]}",
                "report": {"passed": False, "first_cause": "check could not run",
                           "failed": ["check"], "incomplete": []}}


def _nudges(session: str, *, bump: bool = False) -> int:
    """EFFECTFUL: the per-session count of blocks already issued (C-5.7)."""
    import tempfile
    key = re.sub(r"[^A-Za-z0-9_-]", "_", session)[:80]
    p = pathlib.Path(tempfile.gettempdir()) / f"athena-gate-nudges-{key}"
    try:
        n = int((p.read_text(encoding="utf-8").strip() or "0"))
    except (OSError, ValueError):
        n = 0
    if bump:
        try:
            p.write_text(str(n + 1), encoding="utf-8")
        except OSError:
            pass
    return n


def cmd_gate(a) -> int:
    """Every contract under a directory, the cheap lane, one verdict — and the Stop-hook
    decision when `--hook` reads the Claude Code payload from stdin."""
    from lib.gate import BYPASS_VAR, find_contracts, fold, hook_decision, render

    payload: dict = {}
    if a.hook:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
    root = pathlib.Path(a.root or payload.get("cwd") or ".")
    if not root.is_dir():
        root = pathlib.Path(".")
    root = root.resolve()
    bypassed = bool(os.environ.get(BYPASS_VAR))

    files: dict = {}
    for path in _walk(root, "contract.md", a.depth):
        try:
            files[str(path)] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    verdicts = [] if bypassed else [_gate_one(pathlib.Path(c), root) for c in find_contracts(files)]

    session = str(payload.get("session_id") or a.session or "")
    used = _nudges(session) if session else 0
    report = fold(verdicts, bypassed=bypassed, nudges_used=used, max_nudges=a.max_nudges)
    report["root"] = str(root)

    if a.hook:
        decision = hook_decision(report)
        if decision is not None:
            if session:
                _nudges(session, bump=True)
            print(json.dumps(decision, ensure_ascii=False))
        return 0            # for a hook the decision payload is the verdict, not the exit code

    print(render(report) if a.text else json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["passed"] else 1


# --- v3.11: the team layer — cases, decisions, intake, lanes, the harness, metrics -------

def cmd_case_run(a) -> int:
    """Replay one case in this process (the derived run_cmd of a case scenario)."""
    from lib.cases import CaseError, load_case, run_case
    try:
        res = run_case(load_case(a.path, a.cwd))
    except (CaseError, OSError, ValueError) as e:
        _emit({"case": a.path, "passed": False, "message": f"{type(e).__name__}: {e}"})
        return 2
    _emit({"case": a.path, "passed": res.passed, "message": res.message,
           "duration_ms": res.duration_ms})
    return 0 if res.passed else 1


def _adr_files(directory: str) -> list[pathlib.Path]:
    return sorted(p for p in pathlib.Path(directory).glob("*.md") if p.name[0].isdigit())


def cmd_adr_lint(a) -> int:
    from lib.adr import lint_adr
    issues: list[str] = []
    files = _adr_files(a.dir)
    for p in files:
        issues += list(lint_adr(_read(str(p)), name=p.name))
    if a.text:
        print(f"# decision records in {a.dir}: {len(files)}")
        print("\n".join(f"  - {i}" for i in issues) if issues else "  all six parts present")
    else:
        _emit({"dir": a.dir, "records": len(files), "issues": issues, "passed": not issues})
    return 0 if not issues else 1


def _all_contracts(root: pathlib.Path, depth: int = 3) -> list[pathlib.Path]:
    from lib.gate import is_contract
    out = []
    for p in _walk(root, "contract.md", depth):
        try:
            if is_contract(p.read_text(encoding="utf-8")):
                out.append(p)
        except OSError:
            continue
    return sorted(out)


def cmd_adr_unlinked(a) -> int:
    from lib.adr import cited_targets, unlinked
    from lib.contract import parse as parse_contract
    root = pathlib.Path(a.cwd).resolve()
    contracts = [pathlib.Path(c) for c in a.contract] or _all_contracts(root)
    cited: set[str] = set()
    for c in contracts:
        rel = str(c.resolve().relative_to(root)).replace("\\", "/") if c.resolve().is_relative_to(root) else str(c)
        cited |= cited_targets(rel, parse_contract(_read(str(c))))
    adrs = [str(p.resolve().relative_to(root)).replace("\\", "/") for p in _adr_files(a.dir)]
    rows = unlinked(adrs, cited)
    if a.text:
        print(f"# decision records nobody cites ({len(rows)} of {len(adrs)})")
        print("\n".join(f"  - {r}" for r in rows) if rows else "  every record is cited by a clause")
    else:
        _emit({"records": adrs, "unlinked": list(rows), "contracts": [str(c) for c in contracts],
               "passed": not rows})
    return 0 if not rows else 1


def cmd_contract_next_id(a) -> int:
    from lib.allocate import lane_from_env, next_id
    lane = a.lane if a.lane is not None else lane_from_env(os.environ)
    cid = next_id(_load_contract(a), a.group, lane)
    _emit({"id": cid, "group": a.group, "lane": lane})
    return 0


def cmd_intake(a) -> int:
    """A failure -> a draft clause + a red spec, in one step (team-layer C-3.*)."""
    from lib.allocate import lane_from_env
    from lib.contract import parse as parse_contract, pin_scenarios
    from lib.docrefs import fingerprint
    from lib.intake import intake
    cpath = pathlib.Path(a.contract)
    spath = pathlib.Path(a.scenarios or _sibling(a.contract, "scenarios.md"))
    trace = None
    if a.trace:
        tpath = pathlib.Path(a.trace)
        trace = (os.path.relpath(tpath.resolve(), cpath.resolve().parent).replace("\\", "/"),
                 fingerprint(tpath.read_text(encoding="utf-8")))
    case_path = a.case
    if not a.run_cmd and not case_path:
        stem = str(cpath.parent).replace("\\", "/").rstrip("/")
        case_path = f"{stem}/cases/PENDING.json"      # renamed to the allocated id below
    lane = a.lane if a.lane is not None else lane_from_env(os.environ)
    out = intake(_read(str(cpath)), _read(str(spath)) if spath.exists() else f"# Scenarios: {cpath.parent.name}\n",
                 group=a.group, source=a.source, text=a.text, lane=lane, trace=trace,
                 run_cmd=a.run_cmd, case_path=case_path)
    if out["case_text"] is not None:
        real = out["case_path"].replace("PENDING", out["clause_id"])
        out["scenarios_text"] = out["scenarios_text"].replace(out["case_path"], real)
        out["case_path"] = real
        p = pathlib.Path(real)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(out["case_text"], encoding="utf-8")
    cpath.write_text(out["contract_text"], encoding="utf-8")
    pinned, _stats = pin_scenarios(out["scenarios_text"], parse_contract(out["contract_text"]))
    spath.write_text(pinned, encoding="utf-8")
    _emit({"clause": out["clause_id"], "spec": out["spec_id"], "status": "draft",
           "source": a.source, "case": out["case_path"] or "", "run_cmd": a.run_cmd,
           "contract": str(cpath), "scenarios": str(spath),
           "next": "write the check from the trace, run `athena spec run`, then promote the "
                   "clause to active by removing *(draft)* once the spec is green"})
    return 0


def cmd_hook_pre_edit(a) -> int:
    """PreToolUse: the blast radius as context; a derived artifact refused (team-layer C-5.*)."""
    from lib.gate import BYPASS_VAR
    from lib.hooks import pre_edit_decision
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    target = str((payload.get("tool_input") or {}).get("file_path")
                 or (payload.get("tool_input") or {}).get("path") or a.path or "")
    if not target:
        return 0
    root = pathlib.Path(a.root or payload.get("cwd") or ".")
    root = root.resolve() if root.is_dir() else pathlib.Path(".").resolve()
    maps: dict = {}
    for mp in _walk(root, "clause_map.json", a.depth):
        try:
            label = str(mp.parent.relative_to(root)).replace("\\", "/") + "/contract.md"
            maps[label] = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    try:
        shown = str(pathlib.Path(target).resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        shown = target
    decision = pre_edit_decision(shown, maps, bypassed=bool(os.environ.get(BYPASS_VAR)))
    if decision is not None:
        print(json.dumps(decision, ensure_ascii=False))
    return 0


def cmd_lint_arch(a) -> int:
    from lib.archlint import lint_sources, render
    files: dict = {}
    for src in a.source:
        for p in sorted(pathlib.Path(src).glob("*.py")):
            files[str(p).replace("\\", "/")] = _read(str(p))
    findings = lint_sources(files)
    if a.text:
        print(render(findings))
    else:
        _emit({"files": len(files), "findings": list(findings), "passed": not findings})
    return 0 if not findings else 1


def cmd_metrics(a) -> int:
    from lib.dispatch import dispatch_metrics, parse_dispatches, render_metrics
    from lib.metrics import iterations_to_green, parse_runs, render
    here = pathlib.Path(a.contract).resolve().parent / ".athena"
    runs_path = here / "runs.jsonl"
    text = runs_path.read_text(encoding="utf-8") if runs_path.exists() else ""
    records, skipped = parse_runs(text)
    rep = iterations_to_green(records)
    dpath = here / "dispatch.jsonl"
    drecords, dskipped = parse_dispatches(dpath.read_text(encoding="utf-8") if dpath.exists() else "")
    drep = dispatch_metrics(drecords)
    # v3.13 C-2.6: what the refinery did with the green ones
    mpath = here / "merge.jsonl"
    mrep: dict = {}
    mtext = ""
    try:
        from lib.refinery import merge_metrics, parse_merges, render_merge_metrics
        merges = parse_merges(mpath.read_text(encoding="utf-8") if mpath.exists() else "")
        mrep = merge_metrics(drecords, merges)
        mtext = render_merge_metrics(mrep)
    except ImportError:            # the refinery module is a task of the refinery-layer plan
        mtext = "# merge — (lib/refinery.py not present)"
    if a.text:
        print(render(rep, skipped=skipped))
        print()
        print(render_metrics(drep))
        print(mtext)
    else:
        _emit({**rep, "skipped_lines": skipped, "runs_file": str(runs_path),
               "dispatch": {**drep, "skipped_lines": dskipped, "file": str(dpath)},
               "merge": {"by_executor": mrep, "file": str(mpath)}})
    return 0


# --- v3.14: the ceiling — a bench matrix through dispatch (C-7.4) ----------------------------

def bench_plan(a) -> dict:
    """PURE given args: the runs of tasks × executors, one workspace per executor, and the
    flags every dispatch will get. `dry_run` and `ran` are part of the plan so the caller
    can print it before, or instead of, running it."""
    from lib.bench import plan_matrix
    tasks = [s.strip() for s in (a.tasks or "").split(",") if s.strip()]
    executors = [s.strip() for s in (a.executors or "").split(",") if s.strip()]
    runs = plan_matrix(tasks, executors, str(a.base_workspace).replace("\\", "/").rstrip("/"))
    return {"contract": a.contract, "front": a.front, "runs": runs,
            "dispatch_flags": {"executor": "<per run>", "iterations": int(a.iterations),
                               "fanout": int(a.fanout), "timeout": int(a.timeout),
                               "stall": int(a.stall), "max_turns": int(a.max_turns)},
            "dry_run": bool(a.dry_run), "ran": 0}


def _pi_text(executor: str, prompt: str, *, cwd: pathlib.Path, timeout: int, thinking: str = "") -> tuple[str, dict, str]:
    """EFFECTFUL: one pi print-mode call with no tools — a text answer from the lane."""
    from lib.executors import pi_binary, pi_command
    cmd = pi_command(executor, prompt, pi_bin=pi_binary(), thinking=thinking)
    argv = cmd["argv"]
    i = argv.index("--tools")
    argv[i:i + 2] = ["--no-tools"]
    # a text answer needs a short output budget: prompt + maxTokens must fit the lane's 30720
    # (measured: a brief on a large packet was refused with 400 at 12288 output tokens)
    j = argv.index("--provider")
    argv[j + 1] = argv[j + 1] + "-text"
    argv[-1] = "Answer the question above. There is no user here. Reply with the answer only."
    return _run_command_executor(cmd, cwd=cwd, timeout=timeout)


def _packet_for(a, workspace: pathlib.Path):
    """The packet for a task as a local executor would see it: files inlined (excerpted), the
    spec sources carried. Shared by dispatch-like commands that need the executor's view."""
    from lib.dispatch import packet, test_node, test_source
    contract = _load_contract(a)
    scenarios = _load_scenarios(a, anchor=a.contract)
    plan = _parse_front_auto(a.front, "auto")
    try:
        task_files = next(tk for ph in plan.phases for tk in ph.tasks if tk.id == a.task).files
    except StopIteration:
        task_files = ()
    files = {}
    for rel in task_files:
        p = workspace / rel
        if p.is_file():
            files[rel] = p.read_text(encoding="utf-8", errors="replace")
    spec_sources = {}
    for s in scenarios:
        path, func = test_node(s.run_cmd)
        if path and func and (workspace / path).is_file():
            src = test_source((workspace / path).read_text(encoding="utf-8", errors="replace"), func)
            if src:
                spec_sources[s.id] = src
    return packet(contract, scenarios, plan, a.task, files=files, budget_chars=getattr(a, "budget", 36000),
                  root=str(workspace), spec_sources=spec_sources)


def cmd_brief(a) -> int:
    """C-8.4: the senior (a stronger reader, no tools) reads the packet and the task's last
    checkpoint and writes a plan without code; the brief is saved beside the checkpoints
    and can be carried in the next dispatch with --brief."""
    from lib.brief import brief_prompt, clean_brief
    from lib.dispatch import DispatchError
    workspace = pathlib.Path(a.workspace).resolve()
    try:
        pk = _packet_for(a, workspace)
    except DispatchError as e:
        _emit({"error": str(e)})
        return 2
    here = pathlib.Path(a.contract).resolve().parent / ".athena"
    cp_path = here / "checkpoints" / f"{a.task}.md"
    checkpoint = cp_path.read_text(encoding="utf-8") if cp_path.exists() and not a.no_checkpoint else ""
    # the senior reads on the same 30k window: past the cap the inlined files are cut to their
    # heads (measured: a 33k-token brief prompt for the witness task was refused outright)
    text = pk["text"]
    marker = "## Files, already read for you"
    if len(text) > a.max_chars and marker in text:
        head, files_part = text.split(marker, 1)
        keep = max(2000, (a.max_chars - len(head)) // max(1, len(pk.get("files") or {}) or 1))
        parts = files_part.split("=== ")
        cut = [parts[0]] + [p[:keep] + (chr(10) + "... (cut for the brief)" + chr(10) if len(p) > keep else "") for p in parts[1:]]
        text = head + marker + "=== ".join(cut)
    prompt = brief_prompt(text[: a.max_chars], checkpoint[-6000:])
    text, tokens, err = _pi_text(a.executor, prompt, cwd=workspace, timeout=a.timeout, thinking=a.pi_thinking)
    brief = clean_brief(text)
    out_path = here / "briefs" / f"{a.task}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if brief:
        out_path.write_text(brief + "\n", encoding="utf-8")
    out = {"task": a.task, "executor": a.executor, "brief": brief, "path": str(out_path) if brief else "",
           "tokens": tokens, "error": err, "checkpoint_used": bool(checkpoint)}
    if a.text:
        print(f"# brief {a.task} <- {a.executor}: {'written to ' + str(out_path) if brief else 'nothing usable'}"
              + (f"  [{err[:100]}]" if err else ""))
        if brief:
            print(brief)
    else:
        _emit(out)
    return 0 if brief else 1


def cmd_locate(a) -> int:
    """C-8.2: a clause with no files named gets its files from the swarm — a repo map within a
    budget, N localiser samples, votes merged by count then first mention."""
    from lib.locate import merge_votes, parse_files_reply, repo_map
    contract = _load_contract(a)
    cl = contract.by_id(a.clause)
    if cl is None:
        _emit({"error": f"no clause {a.clause}"})
        return 2
    root = pathlib.Path(a.workspace).resolve()
    the_map = repo_map(str(root), budget_chars=a.budget)
    prompt = (f"# Locate the files for one requirement\n\nRepository root: {str(root).replace(chr(92), '/')}\n\n"
              f"## The requirement\n- **{cl.id}** — {cl.text}\n\n## The repository map (path: definitions, lines)\n"
              f"{the_map}\n\n## Question\nWhich files must change or be created to satisfy this requirement? "
              f"Answer with a JSON list of at most {a.top} repository-relative paths, most likely first. "
              f"A file that does not exist yet may be named. Nothing but the JSON list.")
    votes, claims = [], []
    for k in range(max(1, a.n)):
        text, tokens, err = _pi_text(a.executor, prompt, cwd=root, timeout=a.timeout, thinking=a.pi_thinking)
        files = parse_files_reply(text)
        votes.append(files)
        claims.append({"sample": k + 1, "files": files, "tokens": tokens, "error": err})
    merged = merge_votes(votes, top=a.top)
    out = {"clause": cl.id, "executor": a.executor, "files": merged, "samples": claims,
           "map_chars": len(the_map)}
    if a.text:
        print(f"# locate {cl.id} -> {a.executor} ({a.n} samples): " + (", ".join(merged) or "(nothing)"))
        for c in claims:
            print(f"  sample {c['sample']}: {', '.join(c['files']) or '-'}" + (f"  [{c['error'][:80]}]" if c["error"] else ""))
    else:
        _emit(out)
    return 0 if merged else 1


def cmd_testwrite(a) -> int:
    """C-8.1: N candidate reproduction tests for a clause, each written by the executor in its
    own copy of the workspace, kept only when they fail on the code as it is, clustered, the
    largest cluster's representative appended to the module in the workspace."""
    import ast
    from lib.dispatch import fan_names, snapshot
    from lib.executors import pi_binary, pi_command
    from lib.spec_runner import _spawn
    from lib.testwriter import choose_test, test_function_name
    contract = _load_contract(a)
    cl = contract.by_id(a.clause)
    if cl is None:
        _emit({"error": f"no clause {a.clause}"})
        return 2
    root = pathlib.Path(a.workspace).resolve()
    module = a.module.replace("\\", "/")
    existing = (root / module).read_text(encoding="utf-8") if (root / module).is_file() else ""
    prompt = (f"# Write ONE failing test for one requirement\n\nRepository root: {str(root).replace(chr(92), '/')}\n\n"
              f"## The requirement\n- **{cl.id}** — {cl.text}\n\n"
              f"## Where\nAppend exactly one pytest function to `{module}` (create the file if it does not exist; "
              f"keep what is there). Its name starts with `test_` and reads as a sentence; its docstring starts "
              f"with `{cl.id} — `. It imports what it needs from the module under test and asserts the behaviour "
              f"the requirement promises.\n\n## Rules\nDo NOT implement the behaviour: the test must FAIL on the "
              f"code as it is, for an assertion or a missing name, not for a syntax error and not by skipping. "
              f"Write only the test. Then answer with one line: DONE.\n"
              + (f"\n## The module today\n```python\n{existing[-6000:]}\n```\n" if existing else ""))
    copies = _fan_out(root, fan_names(str(root), max(1, a.n)))
    candidates = []
    try:
        from lib.dispatch import retarget
        for k, ws in enumerate(copies, 1):
            # each copy is told its own root, or every worker writes into the base (measured
            # twice now: the fan-out and this demo)
            cmd = pi_command(a.executor, retarget(prompt, str(root), str(ws)), pi_bin=pi_binary(),
                             thinking=a.pi_thinking, strict=a.pi_strict)
            claim, tokens, err = _run_command_executor(cmd, cwd=ws, timeout=a.timeout, stall=a.stall)
            new_text = (ws / module).read_text(encoding="utf-8") if (ws / module).is_file() else ""
            added = new_text[len(existing):] if new_text.startswith(existing) else new_text
            name = test_function_name(added)
            run = {"exit": 126, "tail": "no test function added"}
            if name:
                argv = [sys.executable, "-m", "pytest", f"{module}::{name}", "-q"]
                code, tail = _spawn(argv, cwd=str(ws), timeout=a.check_timeout)
                run = {"exit": code, "tail": tail}
            candidates.append({"source": added.strip("\n") + "\n" if added.strip() else "", "run": run,
                               "sample": k, "error": err})
    finally:
        _fan_in(root, copies)
    pick = choose_test(candidates, clause=cl.id)
    if pick["source"]:
        with (root / module).open("a", encoding="utf-8") as fh:
            fh.write(("\n\n" if existing and not existing.endswith("\n\n") else "") + pick["source"])
    out = {"clause": cl.id, "executor": a.executor, "module": module, "chosen": pick["source"],
           "cluster_size": pick["cluster_size"], "admissible": pick["admissible"], "rejected": pick["rejected"],
           "candidates": [{"sample": c["sample"], "exit": c["run"]["exit"], "name": test_function_name(c["source"]),
                           "error": c["error"][:120]} for c in candidates]}
    if a.text:
        print(f"# testwrite {cl.id} -> {a.executor}: {a.n} candidates, {pick['admissible']} admissible, "
              f"cluster {pick['cluster_size']}" + (f", appended to {module}" if pick["source"] else ", nothing chosen"))
        for c in out["candidates"]:
            print(f"  sample {c['sample']}: {c['name'] or '(no test)'} exit {c['exit']}" + (f"  [{c['error']}]" if c["error"] else ""))
    else:
        _emit(out)
    return 0 if pick["source"] else 1


def cmd_next(a) -> int:
    """C-7.3: the next ready task of a slug out of bd, claimed, dispatched with the flags given
    — Gas Town's "if there is work on your hook, run it", with bd as the hook."""
    import subprocess
    from lib.queue import claim_command, pick_ready, ready_command
    plan = _parse_front_auto(a.front, "auto")
    slug = a.slug or _slugify(getattr(plan, "title", "") or pathlib.Path(a.contract).resolve().parent.name)
    try:
        listed = subprocess.run(ready_command(slug), capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60)
        ready_json = listed.stdout or ""
    except (OSError, subprocess.SubprocessError) as e:
        _emit({"slug": slug, "task": "", "error": f"bd ready failed: {e}"})
        return 2
    task = pick_ready(ready_json, slug)
    if not task:
        print(f"next: nothing ready for {slug}" if a.text else json.dumps({"slug": slug, "task": ""}))
        return 1
    if a.dry_run:
        print(f"next: {task} ({slug})" if a.text else json.dumps({"slug": slug, "task": task, "dry_run": True}))
        return 0
    subprocess.run(claim_command(slug, task), capture_output=True, timeout=60)
    argv = [sys.executable, str(pathlib.Path(__file__).resolve()), "dispatch", a.contract, "--front", a.front,
            "--task", task, "--executor", a.executor, "--workspace", a.workspace,
            "--iterations", str(a.iterations), "--fanout", str(a.fanout), "--timeout", str(a.timeout),
            "--stall", str(a.stall), "--slug", slug, "--bd"] + (["--text"] if a.text else [])
    print(f"# next: {task} -> {a.executor}", flush=True)
    return subprocess.run(argv).returncode


def cmd_bench(a) -> int:
    """Run the matrix: each run is `athena dispatch` in its executor's workspace, a worktree
    created from the current HEAD when it does not exist; then the table from the record."""
    import subprocess
    from lib.bench import matrix_table, render_matrix
    from lib.dispatch import parse_dispatches
    plan = bench_plan(a)
    if a.dry_run:
        print(json.dumps(plan, ensure_ascii=False, sort_keys=True) if not a.text
              else "\n".join(f"{r['task']:8} {r['executor']:10} {r['workspace']}" for r in plan["runs"]))
        return 0
    repo = pathlib.Path(a.repo or ".").resolve()
    here = pathlib.Path(a.contract).resolve().parent / ".athena"
    for run in plan["runs"]:
        ws = pathlib.Path(run["workspace"])
        if not ws.exists():
            subprocess.run(["git", "worktree", "add", "--detach", str(ws), "HEAD"], cwd=str(repo),
                           capture_output=True, text=True)
        argv = [sys.executable, str(pathlib.Path(__file__).resolve()), "dispatch", a.contract,
                "--front", a.front, "--task", run["task"], "--executor", run["executor"],
                "--workspace", str(ws), "--iterations", str(a.iterations), "--fanout", str(a.fanout),
                "--timeout", str(a.timeout), "--stall", str(a.stall), "--max-turns", str(a.max_turns), "--text"]
        if a.pi_thinking:
            argv += ["--pi-thinking", a.pi_thinking]
        if a.pi_strict:
            argv += ["--pi-strict"]
        if a.pi_hashline:
            argv += ["--pi-hashline"]
        if a.tag:
            argv += ["--tag", a.tag]
        print(f"# bench {run['task']} -> {run['executor']} in {ws}", flush=True)
        proc = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True, encoding="utf-8", errors="replace")
        print((proc.stdout or "").strip().splitlines()[0] if (proc.stdout or "").strip() else f"  exit {proc.returncode}", flush=True)
        subprocess.run(["git", "add", "-A"], cwd=str(ws), capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", f"bench {run['executor']} {run['task']}"], cwd=str(ws), capture_output=True)
        plan["ran"] += 1
    dpath = here / "dispatch.jsonl"
    records, _ = parse_dispatches(dpath.read_text(encoding="utf-8") if dpath.exists() else "")
    tasks = [r["task"] for r in plan["runs"]]
    tasks = list(dict.fromkeys(tasks))
    executors = list(dict.fromkeys(r["executor"] + (f"#{a.tag}" if a.tag else "") for r in plan["runs"]))
    table = matrix_table(records, tasks, executors)
    if a.text:
        print(render_matrix(table, tasks, executors))
    else:
        _emit({**plan, "table": table})
    return 0


# --- v3.13: the refinery — a green workspace reaches the target through four stages -------

def cmd_verify(a) -> int:
    """C-2.7: a workspace nobody dispatched — assembled by cherry-pick, finished by hand —
    earns its dispatch record from the frame: the diff against the target and the task's
    spec commands, run now, decide; the record is written under executor `verify`."""
    import datetime
    import subprocess
    from lib.dispatch import record, test_node
    from lib.refinery import VERIFY_EXECUTOR, verify_verdict
    from lib.spec_runner import _spawn, _tokenize
    contract = _load_contract(a)
    scenarios = _load_scenarios(a, anchor=a.contract)
    plan = _parse_front_auto(a.front, "auto")
    workspace = pathlib.Path(a.workspace).resolve()
    try:
        task = next(tk for ph in plan.phases for tk in ph.tasks if tk.id == a.task)
    except StopIteration:
        _emit({"passed": False, "error": f"plan has no task {a.task}"})
        return 2
    by_id = {s.id: s for s in scenarios}
    cmds = [by_id[v].run_cmd for v in task.verifies if v in by_id and by_id[v].run_cmd]
    if task.success_check and task.success_check not in cmds:
        cmds.append(task.success_check)
    spec_files = [test_node(c)[0] for c in cmds]
    p = subprocess.run(["git", "diff", "--name-only", f"{a.target}...HEAD"], cwd=str(workspace),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    changed = [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
    checks = []
    for cmdline in cmds:
        argv, why = _tokenize(cmdline)
        if argv and argv[0] in ("python", "python3") and a.check_python:
            argv[0] = a.check_python
        code, tail = (126, why) if not argv else _spawn(argv, cwd=str(workspace), timeout=a.check_timeout)
        checks.append({"cmd": cmdline, "exit": code, "tail": tail})
    v = verify_verdict(changed, checks, spec_files=[f for f in spec_files if f])
    here = pathlib.Path(a.contract).resolve().parent / ".athena"
    here.mkdir(parents=True, exist_ok=True)
    rec = record(a.task, VERIFY_EXECUTOR, v, duration_ms=0, tokens={},
                 ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                 workspace=str(workspace))
    rec["target"] = a.target
    with (here / "dispatch.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if a.text:
        print(f"# verify {a.task} in {workspace} against {a.target}: {'GREEN' if v['green'] else 'RED'}"
              f"  landed={v['landed']} changed={len(changed)}")
        for c in checks:
            print(f"  {'ok  ' if c['exit'] == 0 else 'FAIL'} {c['cmd']}")
        if v["reason"]:
            print("  " + v["reason"][:400])
    else:
        _emit({**v, "task": a.task, "workspace": str(workspace), "target": a.target})
    return 0 if v["passed"] else 1


def cmd_merge(a) -> int:
    """Offer a workspace to the merge queue (C-2.1..C-2.5). Admit on the task's last dispatch
    record, rebase onto the target, run every contract in the workspace, fast-forward the
    target; refuse at the first stage that fails, append the merge record, and hand back the
    bd command that returns the task with the reason. Nothing here trusts a report: git's
    exit codes and the check decide."""
    import datetime
    import subprocess
    from lib.dispatch import parse_dispatches
    from lib.gate import find_contracts
    from lib.refinery import admit, bd_return_command, fast_forward, first_failure, merge_record, rebase

    contract = pathlib.Path(a.contract).resolve()
    here = contract.parent / ".athena"
    here.mkdir(parents=True, exist_ok=True)
    workspace = pathlib.Path(a.workspace).resolve()
    if not workspace.is_dir():
        print(f"merge: workspace is not a directory: {workspace}", file=sys.stderr)
        return 2
    plan = _parse_front_auto(a.front, "auto") if a.front else None
    slug = a.slug or _slugify(getattr(plan, "title", "") or contract.parent.name)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    dpath = here / "dispatch.jsonl"
    records, _ = parse_dispatches(dpath.read_text(encoding="utf-8") if dpath.exists() else "")
    mine = [r for r in records if r.get("task") == a.task]
    executor = a.executor or (mine[-1].get("executor", "?") if mine else "?")

    def run(argv, cwd):
        try:
            p = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=a.timeout)
        except subprocess.TimeoutExpired:
            return 124, f"timed out after {a.timeout}s: {' '.join(argv)}"
        except OSError as e:
            return 127, str(e)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def end(stage: str, ok: bool, reason: str) -> int:
        rec = merge_record(a.task, executor, stage, ok, reason, ts=ts)
        rec["workspace"] = str(workspace)
        rec["target"] = a.target
        with (here / "merge.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out = dict(rec)
        if not ok:
            argv = bd_return_command(slug, a.task, stage, reason)
            out["bd_command"] = argv
            if a.bd:
                code, tail = run(argv, workspace)
                out["bd_exit"] = code
                out["bd_tail"] = tail[-300:]
        if a.text:
            mark = "merged" if ok else f"refused at {stage}"
            print(f"merge: {mark} — {a.task} by {executor} -> {a.target}\n  {reason}")
            if not ok:
                print("  bd: " + " ".join(out["bd_command"][:3]) + " ...")
        else:
            _emit(out)
        return 0 if ok else 1

    d = admit(records, a.task, workspace=str(workspace))
    if not d.get("ok"):
        return end("admit", False, d.get("reason", "not admitted"))

    r = rebase(run, str(workspace), a.target)
    if not r.get("ok"):
        return end("rebase", False, r.get("reason", "rebase failed"))

    files: dict = {}
    for path in _walk(workspace, "contract.md", a.depth):
        try:
            files[str(path)] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    verdicts = [_gate_one(pathlib.Path(c), workspace, run_specs=True) for c in find_contracts(files)]
    fail = first_failure(verdicts)
    if fail:
        return end("check", False, fail)
    # C-2.8: the sealed tier — run here and nowhere else
    from lib.refinery import sealed_checks, sealed_dirs
    from lib.spec_runner import _spawn, _tokenize
    for cmdline in sealed_checks(sealed_dirs(str(workspace))):
        argv, why = _tokenize(cmdline)
        if argv and argv[0] in ("python", "python3"):
            argv[0] = sys.executable
        code, tail = (126, why) if not argv else _spawn(argv, cwd=str(workspace), timeout=a.timeout)
        if code != 0:
            return end("check", False, f"sealed acceptance: {cmdline} exit {code}: {tail[-300:]}")

    f = fast_forward(run, str(workspace), a.target)
    if not f.get("ok"):
        return end("fast-forward", False, f.get("reason", "not a fast-forward"))
    return end("fast-forward", True,
               f"{a.target} {str(f.get('old', ''))[:12]} -> {str(f.get('head', ''))[:12]} "
               f"({len(verdicts)} contracts held)")


# --- v3.12: the executor layer — packets in, verdicts out -------------------------

def _gateway_key() -> str:
    """The LiteLLM master key for the local lanes: env first, then the gateway's own config."""
    key = os.environ.get("LITELLM_LOCAL_KEY") or os.environ.get("ATHENA_LOCAL_GATEWAY_KEY")
    if key:
        return key
    cfg = pathlib.Path(os.environ.get("LITELLM_CONFIG", r"D:\litellm-win\litellm_config.yaml"))
    if cfg.exists():
        try:
            import yaml
            data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            return str((data.get("general_settings") or {}).get("master_key") or "")
        except Exception:                          # noqa: BLE001 — a missing key is reported downstream
            return ""
    return ""


def _worker_json(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        for line in reversed(stdout.splitlines()):
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue
    return {}


def _git(argv: list, cwd) -> tuple[int, str]:
    import subprocess
    try:
        p = subprocess.run(["git", *argv], cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _fan_out(workspace: pathlib.Path, names: list) -> list:
    """EFFECTFUL (C-5.6): one detached worktree per fanned attempt at the workspace's HEAD,
    carrying its uncommitted changes and untracked files, so every attempt starts from the
    same state the checkpoint describes."""
    import shutil
    copies: list = []
    code, head = _git(["rev-parse", "HEAD"], workspace)
    if code != 0:
        raise RuntimeError(f"fan-out needs a git workspace: {head.strip()[:200]}")
    _, diff = _git(["diff", "--binary", "HEAD"], workspace)
    _, untracked = _git(["ls-files", "--others", "--exclude-standard"], workspace)
    for name in names:
        ws = pathlib.Path(name)
        if ws.exists():
            _git(["worktree", "remove", "--force", str(ws)], workspace)
            shutil.rmtree(ws, ignore_errors=True)
        code, out = _git(["worktree", "add", "--detach", str(ws), head.strip()], workspace)
        if code != 0:
            raise RuntimeError(f"could not create {ws}: {out.strip()[:200]}")
        if diff.strip():
            import subprocess
            subprocess.run(["git", "apply", "--binary", "--whitespace=nowarn"], cwd=str(ws), input=diff,
                           capture_output=True, text=True, encoding="utf-8")
        for rel in untracked.split("\n"):
            rel = rel.strip()
            if rel:
                src, dst = workspace / rel, ws / rel
                if src.is_file():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
        copies.append(ws)
    return copies


def _adopt(workspace: pathlib.Path, winner: pathlib.Path, changed: list, deleted: list) -> None:
    """EFFECTFUL (C-5.6, C-5.7): the kept attempt's files become the workspace's."""
    import shutil
    for rel in changed:
        src, dst = winner / rel, workspace / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for rel in deleted:
        try:
            (workspace / rel).unlink()
        except OSError:
            pass


def _fan_in(workspace: pathlib.Path, copies: list) -> None:
    """EFFECTFUL: the fanned worktrees are removed; the record keeps what they did."""
    import shutil
    for ws in copies:
        _git(["worktree", "remove", "--force", str(ws)], workspace)
        shutil.rmtree(ws, ignore_errors=True)
    _git(["worktree", "prune"], workspace)


def _kill_tree(proc) -> None:
    """EFFECTFUL: end a worker and everything it spawned. The claude launcher's child inherits
    the pipes: kill() alone leaves communicate() hanging (measured: a 15-minute timeout
    became a 30-minute hang)."""
    import subprocess
    if os.name == "nt":
        try:
            # taskkill has been seen to sit for 30 s under a test runner: bounded, then kill()
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=8)
        except (subprocess.TimeoutExpired, OSError):
            pass
    try:
        proc.kill()
    except OSError:
        pass


def _run_command_executor(cmd: dict, *, cwd: pathlib.Path, timeout: int, stall: int = 0) -> tuple[str, dict, str]:
    """EFFECTFUL: spawn a worker (a Claude Code lane, pi, the subscription); return
    (claim text, tokens, worker error). stdout is read as it comes: with `stall` > 0 a
    worker that writes nothing for that many seconds is ended and reported as STALLED,
    distinct from the timeout (C-7.2) — the hung workers were held to the 900-second
    timeout and their orphaned requests kept the lane's slots."""
    import subprocess
    import threading
    import time as _time
    env = os.environ.copy()
    for name in cmd.get("unset", []):
        env.pop(name, None)
    env.update(cmd.get("env", {}))
    try:
        proc = subprocess.Popen(cmd["argv"], cwd=str(cwd), env=env,
                                stdin=subprocess.PIPE if cmd.get("stdin") else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace")
    except OSError as e:
        return "", {}, f"could not start the worker: {e}"

    chunks: list = []
    errs: list = []
    last = [_time.monotonic()]

    def pump(stream, sink, touch):
        try:
            for line in iter(stream.readline, ""):
                sink.append(line)
                if touch:
                    last[0] = _time.monotonic()
        except (OSError, ValueError):
            pass

    t_out = threading.Thread(target=pump, args=(proc.stdout, chunks, True), daemon=True)
    t_err = threading.Thread(target=pump, args=(proc.stderr, errs, False), daemon=True)
    t_out.start()
    t_err.start()
    if cmd.get("stdin"):
        try:
            proc.stdin.write(cmd["stdin"])
            proc.stdin.close()
        except (OSError, ValueError):
            pass
    started = _time.monotonic()
    ended_by = ""
    while proc.poll() is None:
        now = _time.monotonic()
        if now - started > timeout:
            ended_by = f"worker timed out after {timeout}s (process tree killed)"
            break
        if stall and now - last[0] > stall:
            ended_by = f"worker stalled: no output for {stall}s (process tree killed)"
            break
        _time.sleep(0.2)
    if ended_by:
        _kill_tree(proc)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
    t_out.join(timeout=5)
    t_err.join(timeout=5)
    out, err_text = "".join(chunks), "".join(errs)
    if ended_by:
        return "", {}, ended_by
    p = subprocess.CompletedProcess(cmd["argv"], proc.returncode, out, err_text)
    if cmd.get("parse") == "pi":                      # C-3.6: pi's JSONL events
        from lib.executors import pi_result
        claim, tokens, err = pi_result(p.stdout or "")
        if p.returncode != 0 and not err:
            err = f"exit {p.returncode}: {(p.stderr or '')[-600:]}"
        return claim, tokens, err
    data = _worker_json(p.stdout or "")
    claim = str(data.get("result", "")) if data else (p.stdout or "")[-2000:]
    tokens = data.get("usage") or {}
    err = ""
    if p.returncode != 0 or data.get("is_error"):
        err = f"exit {p.returncode}: {(p.stderr or claim)[-600:]}"
    return claim, tokens, err


def _run_openhands(cfg: dict) -> tuple[str, dict, str]:
    """EFFECTFUL: one OpenHands SDK conversation in-process over the workspace. Best effort
    against the SDK's public surface; any failure is a worker error, never a traceback."""
    try:
        import importlib
        from pydantic import SecretStr
        from openhands.sdk import LLM, Agent, Conversation, Tool
        for name in cfg.get("tools", ("file_editor",)):
            importlib.import_module(f"openhands.tools.{name}")     # registers the tool
    except ImportError as e:
        return "", {}, f"openhands-sdk import failed: {e}"
    key = os.environ.get(cfg["api_key_env"], "") or _gateway_key() or "local"
    try:
        llm_kwargs = dict(model=cfg["model"], base_url=cfg["base_url"] or None,
                          api_key=SecretStr(key), usage_id="athena-dispatch")
        if cfg.get("native_tools") is not None:
            # a local Qwen through the gateway DOES emit native tool calls (the Claude Code
            # lanes prove it); left to guess, the SDK fell back to prompt-style calls and the
            # model answered with raw <tool_call> text nobody parsed (measured, 160 tokens)
            llm_kwargs["native_tool_calling"] = bool(cfg["native_tools"])
        # the local lanes have a 30720-token window; tell the SDK so its condenser summarises
        # BEFORE the server refuses (measured: a run that had landed edits died on
        # ContextWindowExceededError with the spec still red)
        llm_kwargs["max_input_tokens"] = int(cfg.get("max_input_tokens") or 22000)
        try:
            llm = LLM(**llm_kwargs)
        except (TypeError, ValueError):
            llm_kwargs.pop("native_tool_calling", None)
            llm = LLM(**llm_kwargs)
        agent_kwargs = dict(llm=llm, tools=[Tool(name=n) for n in cfg.get("tools", ("file_editor",))])
        if cfg.get("system_prompt"):
            # C-3.5: the implementer's prompt instead of the stock explorer's
            agent_kwargs["system_prompt"] = cfg["system_prompt"]
        try:
            from openhands.sdk import LLMSummarizingCondenser
            # keep_first=4 is the SDK's own default: system prompt + the task must survive a
            # condensation (measured: with 2 the summary "forgot" the task)
            agent_kwargs["condenser"] = LLMSummarizingCondenser(llm=llm, max_size=12, keep_first=4)
        except Exception:                      # noqa: BLE001 — a condenser is a comfort, not the verdict
            pass
        try:
            agent = Agent(**agent_kwargs)
        except (TypeError, ValueError):
            agent_kwargs.pop("system_prompt", None)
            agent = Agent(**agent_kwargs)
        conv = Conversation(agent=agent, workspace=cfg["workspace"],
                            max_iteration_per_run=cfg["max_iterations"])
        # the SDK's prompt talks about /workspace; on this machine the repository is a
        # Windows path, and the first two turns of a run went to `glob **/* /workspace`
        # ("D:\\workspace is not a valid directory"). Name the root, absolutely.
        conv.send_message(cfg["task"])
        conv.run()
        claim = ""
        for ev in reversed(list(getattr(conv.state, "events", []))):
            text = getattr(ev, "content", None) or getattr(ev, "message", None)
            if text:
                claim = str(text)
                break
        tokens = {}
        metrics = getattr(llm, "metrics", None)
        usage = getattr(metrics, "accumulated_token_usage", None) if metrics else None
        if usage is not None:
            tokens = {"input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                      "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0)}
        return claim, tokens, ""
    except Exception as e:                        # noqa: BLE001 — the verdict does not depend on this
        return "", {}, f"openhands run failed: {type(e).__name__}: {str(e)[:400]}"


def cmd_dispatch(a) -> int:
    """Pour one plan task into an executor and judge it by the diff and the spec commands."""
    import datetime
    import time
    from lib.dispatch import DispatchError, packet, record, snapshot, verdict
    from lib.executors import (LOCAL_GATEWAY, availability, claude_binary, claude_command,
                               local_lane_command, openhands_config, resolve)
    from lib.spec_runner import _spawn, _tokenize

    contract = _load_contract(a)
    scenarios = _load_scenarios(a, anchor=a.contract)
    plan = _parse_front_auto(a.front, a.speckit)
    workspace = pathlib.Path(a.workspace).resolve()

    spec = None
    if a.executor != "none":
        try:
            spec = resolve(a.executor)
        except ValueError as e:
            _emit({"passed": False, "error": str(e)})
            return 2

    files: dict = {}
    # executors without Bash get the files inlined: the local lanes, and OpenHands, whose
    # explorer instincts on a 30k window are the measured failure mode
    inline = (spec is not None and spec["kind"] in ("local", "openhands", "pi")) or a.inline
    try:
        task_files = next(t for ph in plan.phases for t in ph.tasks if t.id == a.task).files
    except StopIteration:
        task_files = ()
    if inline and getattr(a, "pi_hashline", False) and spec is not None and spec["kind"] == "pi":
        inline = False          # C-3.7: the files stay out; the anchored read tool brings them
    if inline:
        for rel in task_files:
            p = workspace / rel
            if p.is_file():
                files[rel] = p.read_text(encoding="utf-8", errors="replace")
    # C-1.5: the spec's own test source travels in the packet, so the executor has nothing
    # left to read — the reads were what blew the 30k window
    from lib.dispatch import test_node, test_source
    spec_sources: dict = {}
    for s in scenarios:
        path, func = test_node(s.run_cmd)
        if path and func and (workspace / path).is_file():
            src = test_source((workspace / path).read_text(encoding="utf-8", errors="replace"), func)
            if src:
                spec_sources[s.id] = src
    try:
        pk = packet(contract, scenarios, plan, a.task, files=files, budget_chars=a.budget,
                    root=str(workspace), spec_sources=spec_sources)
    except DispatchError as e:
        _emit({"passed": False, "error": str(e)})
        return 2

    if spec is None:
        print(json.dumps({k: v for k, v in pk.items() if k != "files"}, ensure_ascii=False,
                         sort_keys=True) if a.json else pk["text"])
        return 0

    av = availability(a.executor)
    if not av["available"]:
        _emit({"passed": False, "executor": a.executor, "available": False, "reason": av["reason"]})
        return 2
    if pk["over_budget"] and spec["kind"] in ("local", "pi"):
        _emit({"passed": False, "executor": a.executor, "error":
               f"packet is {pk['chars']} chars, over the {pk['budget_chars']} budget of a local "
               f"lane: split the task or drop files from it"})
        return 2

    from lib.dispatch import bd_checkpoint_command, run_iterations
    here = pathlib.Path(a.contract).resolve().parent
    dpath = here / ".athena" / "dispatch.jsonl"
    dpath.parent.mkdir(parents=True, exist_ok=True)
    slug = a.slug or _slugify(getattr(plan, "title", "") or here.name)
    before = snapshot(workspace)
    state = {"tokens": {}, "err": "", "checks": [], "duration": 0, "claim": ""}

    def run_executor(text: str, ws: pathlib.Path):
        if spec["kind"] == "local":
            gateway = LOCAL_GATEWAY
            if a.base_url:                       # C-6.5: a lane through the relay
                gateway = a.base_url.rstrip("/")
                gateway = gateway[:-3] if gateway.endswith("/v1") else gateway
            cmd = local_lane_command(a.executor, text, max_turns=a.max_turns, gateway=gateway,
                                     claude_bin=claude_binary(), auth_token=_gateway_key())
            return _run_command_executor(cmd, cwd=ws, timeout=a.timeout, stall=a.stall)
        if spec["kind"] == "claude":
            cmd = claude_command(text, max_turns=a.max_turns, claude_bin=claude_binary())
            cmd["unset"] = ["CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"]
            return _run_command_executor(cmd, cwd=ws, timeout=a.timeout, stall=a.stall)
        if spec["kind"] == "pi":
            from lib.executors import hashline_extension, pi_binary, pi_command
            ext = hashline_extension() if a.pi_hashline else ""
            cmd = pi_command(a.executor, text, pi_bin=pi_binary(), thinking=a.pi_thinking,
                             hashline=ext, files=list(task_files), require_hashline=bool(a.pi_hashline),
                             strict=a.pi_strict)
            return _run_command_executor(cmd, cwd=ws, timeout=a.timeout, stall=a.stall)
        cfg = openhands_config(text, workspace=str(ws),
                               model=a.model or "openai/qwopus-27b",
                               base_url=a.base_url if a.base_url is not None else LOCAL_GATEWAY + "/v1",
                               max_iterations=a.max_turns, terminal=a.terminal,
                               prompt=a.openhands_prompt)
        cfg["native_tools"] = None if a.native_tools == "auto" else (a.native_tools == "on")
        return _run_openhands(cfg)

    def run_checks(ws: pathlib.Path = workspace) -> list:
        rows = []
        for cmdline in pk["checks"]:
            argv, why = _tokenize(cmdline)
            if argv and argv[0] in ("python", "python3") and a.check_python:
                # `python` on PATH is not necessarily the interpreter that has the test deps:
                # when dispatch itself runs from a venv, Windows resolves `python` from the
                # parent's image directory. The check runs with the interpreter the caller named.
                argv[0] = a.check_python
            code, tail = (126, why) if not argv else _spawn(argv, cwd=str(ws), timeout=a.check_timeout)
            rows.append({"cmd": cmdline, "exit": code, "tail": tail})
        return rows

    # C-2.6: the blast radius — every contract's map and scenarios under the workspace, so a
    # change to a shared module runs the sibling clauses' specs too
    from lib.dispatch import radius_checks
    from lib.scenario_parser import parse as parse_scenarios_text
    radius_maps: dict = {}
    radius_scen: dict = {}
    for mp in _walk(workspace, "clause_map.json", 3):
        try:
            label = str(mp.parent.relative_to(workspace)).replace("\\", "/") + "/contract.md"
            radius_maps[label] = json.loads(mp.read_text(encoding="utf-8"))
            sp = mp.parent / "scenarios.md"
            if sp.exists():
                radius_scen[label] = parse_scenarios_text(sp.read_text(encoding="utf-8"))
        except (OSError, ValueError, ParseError):
            continue
    # C-2.7: the test modules the task's specs live in — touching them is never green
    spec_files = [test_node(s.run_cmd)[0] for s in scenarios
                  if s.id in pk["task"].get("verifies", ()) or s.run_cmd in pk["checks"]]
    spec_files = [f for f in spec_files if f]

    def one_attempt(ws: pathlib.Path, before_ws: dict, current: dict) -> dict:
        """One executor process in one workspace, judged there: verdict, claim, checks."""
        t0 = time.perf_counter()
        claim, tokens, err = run_executor(current["text"], ws)
        duration = int((time.perf_counter() - t0) * 1000)
        after = snapshot(ws)
        changed_now = sorted(p for p, sig in after.items() if before_ws.get(p) != sig)
        extra = radius_checks(changed_now, radius_maps, radius_scen, already=pk["checks"])
        checks = run_checks(ws)
        from lib.dispatch import batch_radius
        for batch in batch_radius(extra):          # one pytest per module, not per command
            argv, why = _tokenize(batch["cmd"])
            if argv and argv[0] in ("python", "python3") and a.check_python:
                argv[0] = a.check_python
            code, tail = (126, why) if not argv else _spawn(argv, cwd=str(ws), timeout=a.check_timeout)
            checks.append({"cmd": batch["cmd"], "exit": code, "tail": tail, "radius": True,
                           "members": batch["members"]})
        v = verdict(before_ws, after, checks, claim=claim, spec_files=spec_files, allowed=list(task_files))
        v["duration_ms"] = duration
        return {"v": v, "claim": claim, "tokens": tokens, "err": err, "checks": checks,
                "duration": duration, "ws": ws}

    def write_record(r: dict, iteration: int, *, attempt_no: int = 0, winner: bool = True) -> None:
        named = a.executor + (f"#{a.tag}" if getattr(a, "tag", "") else "")   # a setting under test
        rec = record(a.task, named, r["v"], duration_ms=r["duration"], tokens=r["tokens"],
                     ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                     workspace=str(workspace))
        rec["iteration"] = iteration
        if attempt_no:
            rec["attempt"] = attempt_no          # C-5.7: every fanned attempt is recorded
            rec["winner"] = winner
        with dpath.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def attempt(iteration: int, current: dict):
        # C-5.2: every iteration is a NEW executor process with the same window; the only
        # memory between them is the checkpoint inside the packet and the workspace itself
        if a.fanout <= 1:
            r = one_attempt(workspace, before, current)
            write_record(r, iteration)
        else:
            # C-5.6: the same packet into N copies of the workspace at once; the first green
            # verdict is the iteration's, else the least red landing is carried forward
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from lib.dispatch import fan_names, pick_winner, retarget
            copies = _fan_out(workspace, fan_names(str(workspace), a.fanout))
            results: list = []
            try:
                befores = {ws: snapshot(ws) for ws in copies}
                # the packet names the root absolutely: each copy gets a packet naming ITSELF,
                # or every worker edits the base and every copy reports "nothing landed" (measured)
                packets = {ws: {**current, "text": retarget(current["text"], str(workspace), str(ws))}
                           for ws in copies}
                with ThreadPoolExecutor(max_workers=len(copies)) as pool:
                    futs = {pool.submit(one_attempt, ws, befores[ws], packets[ws]): ws for ws in copies}
                    for fut in as_completed(futs):
                        results.append(fut.result())
                # C-5.8: choose by behaviour — which checks passed and the normalised patch —
                # not by completion order; fall back to first-green when the module is absent
                win = None
                selection = None
                try:
                    from lib.select import select_attempt
                    attempts_view = []
                    for k, r in enumerate(results):
                        sources = {}
                        for rel in (r["v"].get("changed_files") or [])[:12]:
                            p = pathlib.Path(r["ws"]) / rel
                            if p.is_file() and p.suffix == ".py":
                                try:
                                    sources[rel] = p.read_text(encoding="utf-8", errors="replace")
                                except OSError:
                                    pass
                        attempts_view.append({"index": k, "landed": bool(r["v"].get("landed")),
                                              "green": bool(r["v"].get("green")), "checks": r["checks"],
                                              "duration_ms": int(r["duration"]), "sources": sources})
                    selection = select_attempt(attempts_view)
                    win = selection.get("index")
                except ImportError:
                    win = pick_winner([r["v"] for r in results])
                for k, r in enumerate(results, 1):
                    write_record(r, iteration, attempt_no=k, winner=(win is not None and results[win] is r))
                if selection is not None:
                    state["selection"] = {"cluster_size": selection.get("cluster_size"),
                                          "green_clusters": selection.get("green_clusters"),
                                          "representatives": [x.get("index") for x in selection.get("representatives", [])]}
                if win is None:
                    r = results[0]
                    r["v"]["reason"] = (f"{len(results)} fanned attempts, none landed; " + r["v"]["reason"])
                else:
                    r = results[win]
                    _adopt(workspace, r["ws"], r["v"]["changed_files"], r["v"]["deleted_files"])
                    how = (f"attempt {win + 1} of {len(results)} kept"
                           + (f" (cluster of {selection['cluster_size']}, {selection['green_clusters']} green clusters)"
                              if selection else ""))
                    r["v"]["reason"] = how + ("; " if r["v"]["reason"] else "") + r["v"]["reason"]
            finally:
                _fan_in(workspace, copies)
        v, claim, tokens, err, checks, duration = r["v"], r["claim"], r["tokens"], r["err"], r["checks"], r["duration"]
        state.update(tokens=tokens, err=err, checks=checks, duration=duration, claim=claim)
        if not v["passed"]:
            from lib.dispatch import checkpoint as make_checkpoint, render_checkpoint
            cp = make_checkpoint(a.task, iteration, v, claim=claim)
            cpath = here / ".athena" / "checkpoints" / f"{a.task}.md"
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(render_checkpoint(cp), encoding="utf-8")   # C-5.1, C-5.5
            if a.bd:
                argv = bd_checkpoint_command(slug, a.task, cp)
                _spawn(argv, cwd=str(workspace), timeout=60)             # C-5.4, on request
        return v, claim

    # C-1.6: the executor starts knowing which specs are RED right now — a model that saw a
    # complete-looking file and no failing check called finish without editing (measured)
    from lib.dispatch import packet_with_status
    from lib.executors import LOCAL_OUTPUT_TOKENS
    if getattr(a, "brief", ""):
        # C-8.4: the senior's brief travels in the packet, ahead of the spec status
        from lib.brief import packet_with_brief
        bp = pathlib.Path(a.brief)
        if bp.is_file():
            pk = packet_with_brief(pk, bp.read_text(encoding="utf-8"))
    pk = packet_with_status(pk, run_checks(),
                            output_tokens=LOCAL_OUTPUT_TOKENS.get(a.executor, 0) if spec["kind"] == "local" else 0)
    loop = run_iterations(pk, attempt, budget=a.iterations)
    v, checks, tokens, err, duration = loop["verdict"], state["checks"], state["tokens"], state["err"], state["duration"]

    out = {**v, "task": a.task, "executor": a.executor, "duration_ms": duration,
           "tokens": tokens, "worker_error": err, "checks": checks, "record": str(dpath),
           "iterations": loop["iterations"], "budget": a.iterations,
           "checkpoint": str(here / ".athena" / "checkpoints" / f"{a.task}.md") if loop["checkpoints"] else "",
           "bd_note": bd_checkpoint_command(slug, a.task, loop["last_checkpoint"])[:4] if loop["last_checkpoint"] else []}
    if a.text:
        print(f"# dispatch {a.task} -> {a.executor}: {'PASS' if v['passed'] else 'FAIL'}"
              f"  (iteration {loop['iterations']} of {a.iterations})")
        print(f"  landed={v['landed']}  green={v['green']}  changed={len(v['changed_files'])}  "
              f"{duration} ms  tokens={tokens.get('input_tokens', '?')}/{tokens.get('output_tokens', '?')}")
        for c in checks:
            print(f"  {'ok  ' if c['exit'] == 0 else 'FAIL'} {c['cmd']}")
        if v["changed_files"] or v["deleted_files"]:
            shown = (v["changed_files"] + [f"{p} (deleted)" for p in v["deleted_files"]])[:8]
            more = len(v["changed_files"]) + len(v["deleted_files"]) - len(shown)
            print("  changed: " + ", ".join(shown) + (f", +{more} more" if more > 0 else ""))
        if v["review_flags"]:
            print("  review: " + ", ".join(v["review_flags"]))
        if err:
            print(f"  worker: {err}")
        if v["reason"]:
            print(f"  reason: {v['reason'][:400]}")
        if out["checkpoint"]:
            print(f"  checkpoint: {out['checkpoint']}" + ("  (also appended to bd)" if a.bd else ""))
    else:
        _emit(out)
    return 0 if v["passed"] else 1


def cmd_relay(a) -> int:
    """An OpenAI-compatible relay in front of the gateway: non-streaming chat completions are
    normalised (a tool call left as text becomes tool_calls, C-6.1); everything else, and
    every streaming response, is forwarded byte for byte (C-6.2). The lanes are not touched."""
    import http.server
    import urllib.error
    import urllib.request
    from lib.toolcalls import normalize_completion, prepare_request

    upstream = a.upstream.rstrip("/")
    log = open(a.log, "a", encoding="utf-8") if a.log else None

    def note(line: str) -> None:
        if log:
            log.write(line + "\n")
            log.flush()

    class Relay(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):     # quiet; the relay's own log is opt-in
            return

        def _forward(self, body: bytes | None):
            url = upstream + self.path
            headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in ("host", "content-length", "transfer-encoding", "connection")}
            req = urllib.request.Request(url, data=body, method=self.command, headers=headers)
            try:
                return urllib.request.urlopen(req, timeout=a.timeout)
            except urllib.error.HTTPError as e:
                return e

        def _count(self, parsed: dict):
            """The lane's own count of the prompt (POST /tokenize), and its window; (None, 0)
            when the lane does not answer — then nothing is clamped."""
            try:
                req_body = {"model": parsed.get("model"), "messages": parsed.get("messages", []),
                            "add_generation_prompt": True}
                if parsed.get("tools"):
                    req_body["tools"] = parsed["tools"]
                req = urllib.request.Request(upstream + "/tokenize", data=json.dumps(req_body).encode("utf-8"),
                                             method="POST", headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read())
                return int(data.get("count")), int(data.get("max_model_len") or a.window)
            except Exception:                       # noqa: BLE001 — a count we cannot get is not a reason to fail the call
                return None, 0

        def _send(self, status: int, headers, payload: bytes) -> None:
            self.send_response(status)
            for k, v in headers:
                if k.lower() in ("content-length", "transfer-encoding", "connection", "content-encoding"):
                    continue
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            resp = self._forward(None)
            self._send(resp.status, resp.getheaders(), resp.read())

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            streaming = False
            try:
                parsed = json.loads(body or b"{}")
                streaming = bool(parsed.get("stream"))
                if self.path.endswith("/chat/completions") and isinstance(parsed, dict):
                    # C-6.4: tool-carrying requests go out with thinking off (vLLM #42021)
                    parsed, changed = prepare_request(parsed, thinking=(a.thinking == "on"), strict=a.strict)
                    # C-6.8: the output budget clamped to the window, counted by the lane itself
                    if a.clamp:
                        count, window = self._count(parsed)
                        if count is not None:
                            from lib.toolcalls import clamp_output
                            parsed, c2 = clamp_output(parsed, count, window, margin=a.margin)
                            if c2:
                                note(f"clamped: prompt {count} of {window}, budget -> "
                                     f"{parsed.get('max_tokens', parsed.get('max_completion_tokens'))}")
                                changed = True
                    if changed:
                        body = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
            except (ValueError, AttributeError):
                streaming = False
            if self.path.rstrip("/").endswith("/messages") and isinstance(parsed, dict):
                # C-6.5: the Anthropic path Claude Code speaks. The upstream is asked without
                # a stream, the reply is normalised (a textual tool call -> tool_use), and
                # the client gets the SSE frames it asked for, or JSON. Thinking untouched.
                from lib.toolcalls import normalize_messages_response, sse_events
                wanted_stream = streaming
                if streaming:
                    parsed = {**parsed, "stream": False}
                    body = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
                resp = self._forward(body)
                raw = resp.read()
                if resp.status != 200:
                    self._send(resp.status, resp.getheaders(), raw)
                    return
                try:
                    payload = json.loads(raw)
                except ValueError:
                    self._send(resp.status, resp.getheaders(), raw)
                    return
                payload, changed = normalize_messages_response(payload)
                if changed:
                    note("messages normalised: " + ", ".join(
                        b.get("name", "?") for b in payload.get("content", []) if b.get("type") == "tool_use"))
                if wanted_stream:
                    data = "".join(sse_events(payload)).encode("utf-8")
                    self._send(200, [("Content-Type", "text/event-stream"), ("Cache-Control", "no-cache")], data)
                else:
                    self._send(200, [("Content-Type", "application/json")],
                               json.dumps(payload, ensure_ascii=False).encode("utf-8"))
                return
            resp = self._forward(body)
            if streaming or not self.path.endswith("/chat/completions") or resp.status != 200:
                # pass through, chunk by chunk when the upstream streams
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in ("content-length", "transfer-encoding", "connection"):
                        self.send_header(k, v)
                data = resp.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            raw = resp.read()
            try:
                payload = json.loads(raw)
            except ValueError:
                self._send(resp.status, resp.getheaders(), raw)
                return
            payload, changed = normalize_completion(payload)
            if changed:
                note(f"normalised: {[c['message']['tool_calls'][0]['function']['name'] for c in payload['choices'] if c.get('message', {}).get('tool_calls')]}")
            self._send(200, [("Content-Type", "application/json")],
                       json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    server = http.server.ThreadingHTTPServer((a.host, a.port), Relay)
    print(json.dumps({"relay": f"http://{a.host}:{a.port}/v1", "upstream": upstream,
                      "note": "non-streaming chat completions are normalised; the lanes are untouched"}))
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


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
    _rep("sources", cmd_contract_sources)

    cn = csub.add_parser("next-id", help="the next unused clause id of a group, in a lane "
                                         "(lane N allocates N*1000..N*1000+999)")
    cn.add_argument("contract")
    cn.add_argument("group", help="e.g. C-3")
    cn.add_argument("--lane", type=int, default=None,
                    help="author/branch lane (default: ATHENA_LANE, else 0)")
    cn.set_defaults(fn=cmd_contract_next_id)

    ca = sub.add_parser("case", help="specs as data: given/when/then in JSON, run in-process")
    casub = ca.add_subparsers(dest="case_cmd", required=True)
    car = casub.add_parser("run")
    car.add_argument("path")
    car.add_argument("--cwd", default=".")
    car.set_defaults(fn=cmd_case_run)

    ad = sub.add_parser("adr", help="decision records: lint their shape, find uncited ones")
    adsub = ad.add_subparsers(dest="adr_cmd", required=True)
    adl = adsub.add_parser("lint")
    adl.add_argument("dir", nargs="?", default="docs/adr")
    adl.add_argument("--text", action="store_true")
    adl.set_defaults(fn=cmd_adr_lint)
    adu = adsub.add_parser("unlinked")
    adu.add_argument("dir", nargs="?", default="docs/adr")
    adu.add_argument("--contract", action="append", default=[],
                     help="contract(s) whose citations count (default: every contract under cwd)")
    adu.add_argument("--cwd", default=".")
    adu.add_argument("--text", action="store_true")
    adu.set_defaults(fn=cmd_adr_unlinked)

    it = sub.add_parser("intake", help="a failure -> a draft clause + a red spec")
    it.add_argument("contract")
    it.add_argument("--scenarios", default="")
    it.add_argument("--group", required=True, help="clause group, e.g. C-3")
    it.add_argument("--source", required=True,
                    help="incident | audit | ledger | mutation | review")
    it.add_argument("--text", required=True, help="the clause: WHEN ... THE SYSTEM SHALL ...")
    it.add_argument("--trace", default="", help="the failure record file to cite by fingerprint")
    it.add_argument("--run-cmd", dest="run_cmd", default="",
                    help="bind this command instead of writing a case skeleton")
    it.add_argument("--case", default="", help="path of the case skeleton to write")
    it.add_argument("--lane", type=int, default=None)
    it.set_defaults(fn=cmd_intake)

    hk = sub.add_parser("hook", help="Claude Code hook decisions")
    hksub = hk.add_subparsers(dest="hook_cmd", required=True)
    hpe = hksub.add_parser("pre-edit", help="PreToolUse for Edit/Write: owning clauses as context, "
                                            "derived artifacts refused")
    hpe.add_argument("--path", default="", help="target file (default: the payload's tool_input.file_path)")
    hpe.add_argument("--root", default="", help="repository root (default: the payload's cwd)")
    hpe.add_argument("--depth", type=int, default=3)
    hpe.set_defaults(fn=cmd_hook_pre_edit)

    ln = sub.add_parser("lint", help="structural lints")
    lnsub = ln.add_subparsers(dest="lint_cmd", required=True)
    lna = lnsub.add_parser("arch", help="effects only behind the allowlisted seams")
    lna.add_argument("--source", action="append", default=["lib"])
    lna.add_argument("--text", action="store_true")
    lna.set_defaults(fn=cmd_lint_arch)

    dp = sub.add_parser("dispatch", help="pour one plan task into an executor (local lane, "
                                         "OpenHands, Claude) and judge it by diff + specs")
    dp.add_argument("contract")
    dp.add_argument("--scenarios", default="")
    dp.add_argument("--front", required=True, help="plan.md (or tasks.md) holding the task")
    dp.add_argument("--task", required=True, help="task id, e.g. T5.1")
    dp.add_argument("--executor", default="none",
                    help="none (print the packet) | local-27b | local-9b | openhands | claude")
    dp.add_argument("--workspace", default=".", help="where the executor works (repo or worktree)")
    dp.add_argument("--model", default="", help="openhands: model id (default openai/qwopus-27b)")
    dp.add_argument("--base-url", dest="base_url", default=None,
                    help="openhands: OpenAI-compatible base url (default: the local gateway /v1)")
    dp.add_argument("--brief", default="", help="a senior's brief (athena brief) carried in the packet (C-8.4)")
    dp.add_argument("--tag", default="", help="a label appended to the executor name in the record, e.g. low, strict")
    dp.add_argument("--pi-strict", dest="pi_strict", action="store_true",
                    help="pi executors: use the lane's strict relay provider (<provider>-strict), tool "
                         "calls under the lane's grammar (C-6.7)")
    dp.add_argument("--pi-hashline", dest="pi_hashline", action="store_true",
                    help="pi executors: load the hashline extension, anchored read/replace/insert "
                         "instead of str_replace, files left out of the packet (C-3.7)")
    dp.add_argument("--pi-thinking", dest="pi_thinking", default="",
                    choices=("", "off", "minimal", "low", "medium", "high", "xhigh"),
                    help="pi executors: the thinking level pi asks the model for")
    dp.add_argument("--stall", type=int, default=0,
                    help="seconds of worker silence on stdout before it is ended as stalled (C-7.2); "
                         "0 = only the timeout")
    dp.add_argument("--fanout", type=int, default=1,
                    help="attempts per iteration, each in its own copy of the workspace; the "
                         "first green wins, else the least red landing is carried forward (C-5.6)")
    dp.add_argument("--iterations", type=int, default=1,
                    help="fresh-context iterations on the same task; a checkpoint (files changed, "
                         "red commands, last words) carries between them so a 30k window is enough")
    dp.add_argument("--bd", action="store_true",
                    help="also append each checkpoint to the task's notes in bd")
    dp.add_argument("--slug", default="", help="bd project slug (default: from the plan title)")
    dp.add_argument("--max-turns", dest="max_turns", type=int, default=30)
    dp.add_argument("--timeout", type=int, default=900, help="seconds for the executor")
    dp.add_argument("--check-timeout", dest="check_timeout", type=int, default=300)
    dp.add_argument("--check-python", dest="check_python", default=sys.executable,
                    help="interpreter for `python ...` check commands (default: this one)")
    dp.add_argument("--budget", type=int, default=36000, help="packet budget in chars")
    dp.add_argument("--inline", action="store_true",
                    help="inline the task's files into the packet (default for local lanes)")
    dp.add_argument("--native-tools", dest="native_tools", choices=("auto", "on", "off"), default="on",
                    help="openhands: native function calling for the model (default on: the local "
                         "Qwen lanes emit real tool calls through the gateway)")
    dp.add_argument("--openhands-prompt", dest="openhands_prompt", choices=("implementer", "default"),
                    default="implementer",
                    help="openhands: the implementer's system prompt (default) or the SDK's stock "
                         "explorer prompt")
    dp.add_argument("--terminal", action="store_true",
                    help="openhands: also grant the terminal tool (off by default: the specs are "
                         "run by the verdict, and on Windows the tool speaks PowerShell)")
    dp.add_argument("--json", action="store_true", help="with --executor none: the packet as JSON")
    dp.add_argument("--text", action="store_true")
    dp.set_defaults(fn=cmd_dispatch)

    rl = sub.add_parser("relay", help="OpenAI-compatible relay in front of the gateway that turns "
                                      "tool calls left as text into tool_calls (the lanes stay untouched)")
    rl.add_argument("--upstream", default="http://127.0.0.1:8413", help="the gateway")
    rl.add_argument("--host", default="127.0.0.1")
    rl.add_argument("--port", type=int, default=8414)
    rl.add_argument("--timeout", type=int, default=900)
    rl.add_argument("--log", default="", help="append a line per normalised completion here")
    rl.add_argument("--clamp", action="store_true",
                    help="count the prompt with the lane's /tokenize and clamp the output budget to what "
                         "the window leaves (C-6.8)")
    rl.add_argument("--margin", type=int, default=1024, help="tokens kept free under the window when clamping")
    rl.add_argument("--window", type=int, default=30720, help="the window when the lane does not report one")
    rl.add_argument("--strict", action="store_true",
                    help="set strict: true on every function tool so the lane applies its grammar "
                         "to the call (C-6.7); the lane itself is not touched")
    rl.add_argument("--thinking", choices=("off", "on"), default="on",
                    help="for requests that carry tools: set chat_template_kwargs.enable_thinking "
                         "(off by default; vLLM #42021: with thinking on, Qwen3.5 hides its tool "
                         "calls inside the reasoning)")
    rl.set_defaults(fn=cmd_relay)

    me = sub.add_parser("metrics", help="iterations to green and durations, from the record of runs")
    me.add_argument("contract", nargs="?", default="contract.md")
    me.add_argument("--text", action="store_true")
    me.set_defaults(fn=cmd_metrics)

    br = sub.add_parser("brief", help="the senior reads the packet and the last checkpoint and writes a plan "
                                      "without code, for the next dispatch (C-8.4)")
    br.add_argument("contract")
    br.add_argument("--scenarios", default="")
    br.add_argument("--front", required=True)
    br.add_argument("--task", required=True)
    br.add_argument("--executor", default="pi-27b")
    br.add_argument("--workspace", default=".")
    br.add_argument("--budget", type=int, default=36000)
    br.add_argument("--max-chars", dest="max_chars", type=int, default=48000,
                    help="the brief prompt's cap in characters (~12k tokens) so it fits the window with room to answer")
    br.add_argument("--timeout", type=int, default=600)
    br.add_argument("--pi-thinking", dest="pi_thinking", default="")
    br.add_argument("--no-checkpoint", dest="no_checkpoint", action="store_true")
    br.add_argument("--speckit", default="auto")
    br.add_argument("--text", action="store_true")
    br.set_defaults(fn=cmd_brief)

    lo = sub.add_parser("locate", help="the files for a clause, from a repo map and N localiser samples (C-8.2)")
    lo.add_argument("contract")
    lo.add_argument("--clause", required=True)
    lo.add_argument("--executor", default="pi-27b")
    lo.add_argument("--workspace", default=".")
    lo.add_argument("--n", type=int, default=3)
    lo.add_argument("--top", type=int, default=5)
    lo.add_argument("--budget", type=int, default=12000, help="repo map characters")
    lo.add_argument("--timeout", type=int, default=600)
    lo.add_argument("--pi-thinking", dest="pi_thinking", default="")
    lo.add_argument("--text", action="store_true")
    lo.set_defaults(fn=cmd_locate)

    tw = sub.add_parser("testwrite", help="N candidate failing tests for a clause, kept only when they fail on "
                                          "the current code, the largest cluster appended to the module (C-8.1)")
    tw.add_argument("contract")
    tw.add_argument("--clause", required=True)
    tw.add_argument("--module", required=True, help="tests/test_<name>.py to append to")
    tw.add_argument("--executor", default="pi-9b")
    tw.add_argument("--workspace", default=".")
    tw.add_argument("--n", type=int, default=4)
    tw.add_argument("--timeout", type=int, default=900)
    tw.add_argument("--stall", type=int, default=300)
    tw.add_argument("--check-timeout", dest="check_timeout", type=int, default=300)
    tw.add_argument("--pi-thinking", dest="pi_thinking", default="")
    tw.add_argument("--pi-strict", dest="pi_strict", action="store_true")
    tw.add_argument("--text", action="store_true")
    tw.set_defaults(fn=cmd_testwrite)

    nx = sub.add_parser("next", help="the next ready task of a slug from bd, claimed and dispatched (C-7.3)")
    nx.add_argument("contract")
    nx.add_argument("--front", required=True)
    nx.add_argument("--slug", default="")
    nx.add_argument("--executor", default="pi-9b")
    nx.add_argument("--workspace", default=".")
    nx.add_argument("--iterations", type=int, default=3)
    nx.add_argument("--fanout", type=int, default=1)
    nx.add_argument("--timeout", type=int, default=900)
    nx.add_argument("--stall", type=int, default=0)
    nx.add_argument("--dry-run", dest="dry_run", action="store_true")
    nx.add_argument("--text", action="store_true")
    nx.set_defaults(fn=cmd_next)

    bn = sub.add_parser("bench", help="run a matrix of tasks x executors through dispatch, one "
                                      "worktree per executor, and print the table (C-7.4)")
    bn.add_argument("contract")
    bn.add_argument("--front", required=True, help="plan.md holding the tasks")
    bn.add_argument("--tasks", required=True, help="comma-separated task ids")
    bn.add_argument("--executors", required=True, help="comma-separated executor names")
    bn.add_argument("--base-workspace", dest="base_workspace", required=True,
                    help="prefix for the per-executor worktrees: <prefix>-<executor>")
    bn.add_argument("--repo", default="", help="repository the worktrees are made from (default: cwd)")
    bn.add_argument("--iterations", type=int, default=3)
    bn.add_argument("--fanout", type=int, default=1)
    bn.add_argument("--timeout", type=int, default=900)
    bn.add_argument("--stall", type=int, default=0)
    bn.add_argument("--max-turns", dest="max_turns", type=int, default=30)
    bn.add_argument("--pi-thinking", dest="pi_thinking", default="")
    bn.add_argument("--pi-strict", dest="pi_strict", action="store_true")
    bn.add_argument("--pi-hashline", dest="pi_hashline", action="store_true")
    bn.add_argument("--tag", default="", help="label for the record's executor name, e.g. low")
    bn.add_argument("--dry-run", dest="dry_run", action="store_true")
    bn.add_argument("--text", action="store_true")
    bn.set_defaults(fn=cmd_bench)

    vf = sub.add_parser("verify", help="a workspace nobody dispatched earns its record: diff against "
                                       "the target + the task's specs, run now (C-2.7)")
    vf.add_argument("contract")
    vf.add_argument("--scenarios", default="")
    vf.add_argument("--front", required=True)
    vf.add_argument("--task", required=True)
    vf.add_argument("--workspace", required=True)
    vf.add_argument("--target", default="master")
    vf.add_argument("--check-python", dest="check_python", default=sys.executable)
    vf.add_argument("--check-timeout", dest="check_timeout", type=int, default=600)
    vf.add_argument("--speckit", default="auto")
    vf.add_argument("--text", action="store_true")
    vf.set_defaults(fn=cmd_verify)

    mg = sub.add_parser("merge", help="offer a workspace to the refinery: admit on the record, "
                                      "rebase, run every contract, fast-forward the target")
    mg.add_argument("contract")
    mg.add_argument("--front", default="", help="plan.md, for the bd slug")
    mg.add_argument("--task", required=True, help="task id whose last dispatch record admits the offer")
    mg.add_argument("--workspace", required=True, help="the worktree the executor worked in")
    mg.add_argument("--target", default="master", help="branch to fast-forward")
    mg.add_argument("--executor", default="", help="recorded executor (default: from the dispatch record)")
    mg.add_argument("--slug", default="", help="bd project slug (default: from the plan title)")
    mg.add_argument("--bd", action="store_true", help="on refusal, run the bd command that returns the task")
    mg.add_argument("--depth", type=int, default=3, help="how deep to look for contract.md in the workspace")
    mg.add_argument("--timeout", type=int, default=600, help="seconds per git command")
    mg.add_argument("--text", action="store_true")
    mg.set_defaults(fn=cmd_merge)

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
    cm.add_argument("--purl", default="auto",
                    help="package URL of the codebase this map describes "
                         "(default: derived from the git remote; '' to omit)")
    cm.add_argument("--incremental", action="store_true",
                    help="re-derive only the clauses whose owned lines moved")
    cm.set_defaults(fn=cmd_contract_map)

    cr = csub.add_parser("refs", help="clause -> document links: suspect, broken, unpinned")
    cr.add_argument("contract", nargs="?", default="contract.md")
    cr.add_argument("--write", action="store_true",
                    help="re-pin every moved reference (that is a REVIEW: read the diff)")
    cr.add_argument("--text", action="store_true")
    cr.add_argument("--gate", action="store_true", help="exit 1 on a suspect or broken link")
    cr.set_defaults(fn=cmd_contract_refs)

    cex = csub.add_parser("export", help="publish the clause index for other repositories")
    cex.add_argument("contract", nargs="?", default="contract.md")
    cex.add_argument("--scenarios", default="")
    cex.add_argument("--map", default="")
    cex.add_argument("--format", default="needs", choices=("needs", "oft"),
                     help="needs = sphinx-needs needs.json; oft = OpenFastTrace specobject XML")
    cex.add_argument("--project", default="", help="namespace a consumer prefixes our ids with")
    cex.add_argument("--version", default="", help="index version (default: contract version)")
    cex.add_argument("-o", "--out", default="")
    cex.set_defaults(fn=cmd_contract_export)

    cmk = csub.add_parser("markers", help="@relation(...) markers in code, checked "
                                          "against the clause map")
    cmk.add_argument("contract", nargs="?", default="contract.md")
    cmk.add_argument("--source", action="append", default=[], metavar="PATH",
                     help="where to look for markers (repeatable, default: lib)")
    cmk.add_argument("--map", default="", help="clause map (default: beside the contract)")
    cmk.add_argument("--cwd", default=".")
    cmk.add_argument("--text", action="store_true")
    cmk.add_argument("--gate", action="store_true",
                     help="exit 1 on an unknown, retired or unbacked marker")
    cmk.set_defaults(fn=cmd_contract_markers)

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
    ck.add_argument("--purl", default="auto",
                    help="package URL of the codebase under check "
                         "(default: derived from the git remote)")
    ck.add_argument("--cwd", default=".")
    ck.add_argument("--text", action="store_true")
    ck.add_argument("--allow-partial", dest="allow_partial", action="store_true",
                    help="accept a run where a whole leg produced no evidence (fast lane)")
    ck.add_argument("--no-batch", dest="no_batch", action="store_true",
                    help="one process per spec even when specs share an invocation")
    ck.set_defaults(fn=cmd_check)

    ga = sub.add_parser("gate", help="every contract under a directory, the cheap lane, "
                                     "one verdict (the Stop hook execs this with --hook)")
    ga.add_argument("--root", default="", help="directory to scan (default: the hook payload's "
                                               "cwd, else the current directory)")
    ga.add_argument("--depth", type=int, default=3, help="how deep to look for contract.md")
    ga.add_argument("--hook", action="store_true",
                    help="read the Claude Code Stop-hook payload on stdin; print a block "
                         "decision only when a contract does not hold")
    ga.add_argument("--session", default="", help="session id for the nudge budget "
                                                  "(the hook payload carries it)")
    ga.add_argument("--max-nudges", dest="max_nudges", type=int, default=2,
                    help="blocks per session before the gate lets go and says so")
    ga.add_argument("--text", action="store_true")
    ga.set_defaults(fn=cmd_gate)

    le = sub.add_parser("lessons", help="clauses born from a failure signal, and whether "
                                        "their proofs still pass")
    lsub = le.add_subparsers(dest="lessons_cmd", required=True)
    for name, fn in (("list", cmd_lessons_list), ("rerun", cmd_lessons_rerun)):
        lp = lsub.add_parser(name)
        lp.add_argument("contract", nargs="?", default="contract.md")
        lp.add_argument("--scenarios", default="")
        lp.add_argument("--text", action="store_true")
        if name == "rerun":
            lp.add_argument("--cwd", default=".")
            lp.add_argument("--skip-tag", dest="skip_tag", action="append", default=[],
                            metavar="TAG", help="leave out lessons whose clause carries this tag")
            lp.add_argument("--jobs", type=int, default=0)
            lp.add_argument("--env", action="append", default=[], metavar="KEY=VALUE")
            lp.add_argument("--timeout", type=int, default=120)
            lp.add_argument("--no-batch", dest="no_batch", action="store_true")
        lp.set_defaults(fn=fn)

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

    jg = jsub.add_parser("graph", help="record a judge run's steps in the provenance graph")
    jg.add_argument("decisions", nargs="?", default="judge_decisions.json")
    jg.add_argument("--slug", default="contract-layer",
                    help="the slug the clause and scenario nodes were compiled under")
    jg.add_argument("--run", action="store_true",
                    help="actually write to bd (default: emit the commands only)")
    jg.add_argument("-o", "--out", default="", help="write the commands to a file")
    jg.set_defaults(fn=cmd_judge_graph)

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
    srun.add_argument("--no-batch", dest="no_batch", action="store_true",
                      help="one process per spec even when specs share an invocation "
                           "(the default batches them and reads pytest's junit report)")
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
