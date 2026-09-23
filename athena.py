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


def _gate_one(contract: pathlib.Path, root: pathlib.Path) -> dict:
    """The cheap lane for one contract: committed ledger, no spec run, no clause map."""
    d = contract.parent
    argv = ["check", str(contract), "--allow-partial", "--cwd", str(root)]
    if (d / "scenarios.md").exists():
        argv += ["--scenarios", str(d / "scenarios.md")]
    if (d / "plan.md").exists():
        argv += ["--front", str(d / "plan.md")]
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
    if a.text:
        print(render(rep, skipped=skipped))
        print()
        print(render_metrics(drep))
    else:
        _emit({**rep, "skipped_lines": skipped, "runs_file": str(runs_path),
               "dispatch": {**drep, "skipped_lines": dskipped, "file": str(dpath)}})
    return 0


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


def _run_command_executor(cmd: dict, *, cwd: pathlib.Path, timeout: int) -> tuple[str, dict, str]:
    """EFFECTFUL: spawn a Claude Code worker (local lane or subscription); return
    (claim text, tokens, worker error)."""
    import subprocess
    env = os.environ.copy()
    for name in cmd.get("unset", []):
        env.pop(name, None)
    env.update(cmd.get("env", {}))
    try:
        p = subprocess.run(cmd["argv"], cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return "", {}, f"worker timed out after {timeout}s"
    except OSError as e:
        return "", {}, f"could not start the worker: {e}"
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
        from pydantic import SecretStr
        from openhands.sdk import LLM, Agent, Conversation, Tool
        import openhands.tools.file_editor  # noqa: F401 — registers the tool
        import openhands.tools.terminal     # noqa: F401
    except ImportError as e:
        return "", {}, f"openhands-sdk import failed: {e}"
    key = os.environ.get(cfg["api_key_env"], "") or _gateway_key() or "local"
    try:
        llm = LLM(model=cfg["model"], base_url=cfg["base_url"] or None, api_key=SecretStr(key),
                  usage_id="athena-dispatch")
        agent = Agent(llm=llm, tools=[Tool(name="terminal"), Tool(name="file_editor")])
        conv = Conversation(agent=agent, workspace=cfg["workspace"],
                            max_iteration_per_run=cfg["max_iterations"])
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
    inline = (spec is not None and spec["kind"] == "local") or a.inline
    if inline:
        try:
            task_files = next(t for ph in plan.phases for t in ph.tasks if t.id == a.task).files
        except StopIteration:
            task_files = ()
        for rel in task_files:
            p = workspace / rel
            if p.is_file():
                files[rel] = p.read_text(encoding="utf-8", errors="replace")
    try:
        pk = packet(contract, scenarios, plan, a.task, files=files, budget_chars=a.budget)
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
    if pk["over_budget"] and spec["kind"] == "local":
        _emit({"passed": False, "executor": a.executor, "error":
               f"packet is {pk['chars']} chars, over the {pk['budget_chars']} budget of a local "
               f"lane: split the task or drop files from it"})
        return 2

    before = snapshot(workspace)
    t0 = time.perf_counter()
    if spec["kind"] == "local":
        cmd = local_lane_command(a.executor, pk["text"], max_turns=a.max_turns,
                                 claude_bin=claude_binary(), auth_token=_gateway_key())
        claim, tokens, err = _run_command_executor(cmd, cwd=workspace, timeout=a.timeout)
    elif spec["kind"] == "claude":
        cmd = claude_command(pk["text"], max_turns=a.max_turns, claude_bin=claude_binary())
        cmd["unset"] = ["CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"]
        claim, tokens, err = _run_command_executor(cmd, cwd=workspace, timeout=a.timeout)
    else:
        cfg = openhands_config(pk["text"], workspace=str(workspace),
                               model=a.model or "openai/qwopus-27b",
                               base_url=a.base_url if a.base_url is not None else LOCAL_GATEWAY + "/v1",
                               max_iterations=a.max_turns)
        claim, tokens, err = _run_openhands(cfg)
    duration = int((time.perf_counter() - t0) * 1000)

    checks = []
    for cmdline in pk["checks"]:
        argv, why = _tokenize(cmdline)
        code, tail = (126, why) if not argv else _spawn(argv, cwd=str(workspace), timeout=a.check_timeout)
        checks.append({"cmd": cmdline, "exit": code, "tail": tail})
    v = verdict(before, snapshot(workspace), checks, claim=claim)
    rec = record(a.task, a.executor, v, duration_ms=duration, tokens=tokens,
                 ts=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    dpath = pathlib.Path(a.contract).resolve().parent / ".athena" / "dispatch.jsonl"
    dpath.parent.mkdir(parents=True, exist_ok=True)
    with dpath.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    out = {**v, "task": a.task, "executor": a.executor, "duration_ms": duration,
           "tokens": tokens, "worker_error": err, "checks": checks, "record": str(dpath)}
    if a.text:
        print(f"# dispatch {a.task} -> {a.executor}: {'PASS' if v['passed'] else 'FAIL'}")
        print(f"  landed={v['landed']}  green={v['green']}  changed={len(v['changed_files'])}  "
              f"{duration} ms  tokens={tokens.get('input_tokens', '?')}/{tokens.get('output_tokens', '?')}")
        for c in checks:
            print(f"  {'ok  ' if c['exit'] == 0 else 'FAIL'} {c['cmd']}")
        if v["review_flags"]:
            print("  review: " + ", ".join(v["review_flags"]))
        if err:
            print(f"  worker: {err}")
        if v["reason"]:
            print(f"  reason: {v['reason'][:400]}")
    else:
        _emit(out)
    return 0 if v["passed"] else 1


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
    dp.add_argument("--max-turns", dest="max_turns", type=int, default=30)
    dp.add_argument("--timeout", type=int, default=900, help="seconds for the executor")
    dp.add_argument("--check-timeout", dest="check_timeout", type=int, default=300)
    dp.add_argument("--budget", type=int, default=36000, help="packet budget in chars")
    dp.add_argument("--inline", action="store_true",
                    help="inline the task's files into the packet (default for local lanes)")
    dp.add_argument("--json", action="store_true", help="with --executor none: the packet as JSON")
    dp.add_argument("--text", action="store_true")
    dp.set_defaults(fn=cmd_dispatch)

    me = sub.add_parser("metrics", help="iterations to green and durations, from the record of runs")
    me.add_argument("contract", nargs="?", default="contract.md")
    me.add_argument("--text", action="store_true")
    me.set_defaults(fn=cmd_metrics)

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
