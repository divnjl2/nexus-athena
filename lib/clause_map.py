"""
Athena clause_map — the per-clause `file:line` map (v3.3).

The reverse leg was stuck at FILE granularity: a contract that claims `lib/seams.py` for one
gate looked like it claimed all of it, so 26 branches belonging to older features read as
"code no requirement demands". The fix needs a map from a requirement to the exact lines it
owns — and nobody has to author one, because the binding already exists:

    clause --(verifies)--> spec --(run_cmd)--> the lines that command executes

Run each spec ALONE under coverage and the lines it touches are that clause's territory.
The map is derived, never annotated, so it cannot drift from the code by hand.

What it answers that the file-level report could not:
  * `owners("lib/seams.py", 214)` -> which requirements die if this line changes
  * three-way classification of every line in a claimed file:
      owned            — a clause's own spec executes it
      other_coverage   — the wider test suite executes it, but no clause of THIS contract
                         demands it (it belongs to another feature living in the same file)
      unreached        — nothing executes it: dead code, or code nobody tests at all
    Only the third is unambiguously a gap; the file-level report conflated all three.

Freeze-line, as everywhere else in lib/: `build`, `owners`, `classify` are PURE and
stdlib-only. `collect` is the single effectful function (it shells out to coverage.py, which
stays OUT of this module's imports so lib/ keeps no third-party dependency).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shlex
from dataclasses import dataclass, field

#: /3 pinned the OWNED LINES per clause instead of whole files. /4 adds `collected`: which
#: clauses actually produced coverage data, so "this spec ran and touched none of the source
#: roots" stops being indistinguishable from "the coverage run failed and told us nothing".
#: /5 adds `partial`: owned lines whose other arm was never taken, because a line is a weak
#: unit of proof — `if x:` reads as executed the moment control reaches it.
#: /6 adds `subject`: the purl of the codebase the map was derived from, so a map can no
#: longer be mistaken for one describing a different project.
SCHEMA = "athena.clause_map/6"


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip().lstrip("./")


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SpecLines:
    """Lines one spec executed, per file. The atom the map is folded from.

    `collected` separates the two ways `files` can be empty. A spec that ran and touched
    none of the source roots (the binding guard reads artifacts, not modules) legitimately
    owns nothing. A spec whose coverage run FAILED also reports nothing — and treating those
    the same is how a rebuild wiped 25 clauses' ownership without a single warning.
    """
    scenario_id: str
    clause_id: str
    files: dict            # normalized path -> tuple[int, ...]
    collected: bool = True
    branches: dict = field(default_factory=dict)   # path -> {"executed"/"missing": ((a,b)…)}


def run_argv(run_cmd: str, data_file: str, sources: tuple[str, ...]) -> list[str]:
    """PURE: the argv that runs ONE spec under its own coverage data file.

    Isolated data files are what make per-clause attribution possible: the usual
    `--cov` aggregate answers "did the suite touch this line", never "which requirement did".
    Refuses the same shell metacharacters `spec_runner` refuses — a run_cmd is an LLM-hop
    output here too, and this path would otherwise be a way around that rule.
    """
    if any(ch in run_cmd for ch in (";", "|", "&", "`", "$", ">", "<", "\n")):
        raise ValueError(f"refused: shell metacharacter in run_cmd: {run_cmd!r}")
    argv = shlex.split(run_cmd)
    if not argv:
        raise ValueError("refused: empty run_cmd")
    # Drop the interpreter: `python -m coverage run` takes its place. What is left must be
    # a `-m <module> ...` form, because `coverage run <script>` cannot launch a console
    # entry point like `pytest` on Windows.
    if argv[0] == "python" or argv[0].endswith(("python", "python.exe", "python3")):
        argv = argv[1:]
    if argv[:1] != ["-m"]:
        argv = ["-m", *argv]
    # ONE `--source`, comma-joined. coverage.py takes a list here and LAST FLAG WINS when
    # the option repeats, so `--source=lib --source=athena.py` measured athena.py alone —
    # a module pytest never imports. Every spec then collected nothing, and because an
    # empty result is indistinguishable from "owns no lines", an incremental rebuild wiped
    # the line ownership of 25 clauses and reported `unmapped_clauses: []`.
    # Deduplicated in order: `--source` is an argparse `append` over a non-empty default,
    # so the default root arrives again every time a caller names it explicitly.
    roots = list(dict.fromkeys(sources))
    src = [f"--source={','.join(roots)}"] if roots else []
    # --branch always: half a guard is not a proved guard, and the cost is a few percent
    # of a run that already takes minutes.
    return ["python", "-m", "coverage", "run", "--branch", f"--data-file={data_file}",
            *src, *argv]


def json_argv(data_file: str, out_file: str) -> list[str]:
    """PURE: the argv that turns one spec's coverage data into JSON."""
    return ["python", "-m", "coverage", "json", f"--data-file={data_file}",
            "-o", out_file, "--pretty-print"]


def lines_from_json(text: str) -> dict:
    """PURE: coverage.py JSON -> {path: (executed lines...)}. Deterministic ordering."""
    data = json.loads(text)
    out = {}
    for path, entry in sorted((data.get("files") or {}).items()):
        executed = tuple(sorted(entry.get("executed_lines") or ()))
        if executed:
            out[_norm(path)] = executed
    return out


def branches_from_json(text: str) -> dict:
    """PURE: coverage.py JSON -> {path: {"executed": ((a,b)...), "missing": ((a,b)...)}}.

    A line is a weak unit of proof: `if x:` counts as executed the moment control reaches it,
    whether or not the other way out was ever taken. The spec that runs a guard only on its
    happy path OWNS that line under a line map and proves half of what the clause says.

    Present only when the run enabled `--branch`; an older data file simply yields nothing,
    which reads as "no branch evidence" rather than "no missing branches".
    """
    data = json.loads(text)
    out = {}
    for path, entry in sorted((data.get("files") or {}).items()):
        ex = tuple(sorted(tuple(b) for b in (entry.get("executed_branches") or ())))
        ms = tuple(sorted(tuple(b) for b in (entry.get("missing_branches") or ())))
        if ex or ms:
            out[_norm(path)] = {"executed": ex, "missing": ms}
    return out


def partial_lines(files: dict, branches: dict) -> dict:
    """PURE: {path: (line, ...)} for OWNED lines with an outgoing branch never taken.

    Computed against the clause's whole branch evidence, not one spec's: if spec A takes the
    true arm and spec B the false one, the clause has proved both and the line is not partial.
    Only lines the clause owns count — an arm out of a line nobody ran is plain uncovered,
    and saying "half-proved" about it would be flattering.

    @relation(C-9.22, scope=function)
    """
    out = {}
    for path, lines in files.items():
        ev = branches.get(path) or {}
        owned = set(lines)
        taken = set(ev.get("executed") or ())
        half = sorted({a for a, b in (ev.get("missing") or ())
                       if a in owned and (a, b) not in taken})
        if half:
            out[path] = tuple(half)
    return out


def build(spec_lines: tuple[SpecLines, ...], *, contract_version: str = "",
          scenario_version: str = "", clause_digests: dict | None = None,
          spec_digests: dict | None = None, subject: str = "") -> dict:
    """PURE: fold per-spec line sets into the clause map artifact.

    A clause owns the UNION of the lines its specs execute. Two clauses may own the same
    line — that is not a conflict, it is shared code serving two requirements, and the
    owners() query returns both.
    """
    clauses: dict = {}
    collected: set = set()
    branch_ev: dict = {}
    for sl in spec_lines:
        per_clause = clauses.setdefault(sl.clause_id, {})
        if sl.collected:
            collected.add(sl.clause_id)
        for path, lines in sl.files.items():
            per_clause[path] = sorted(set(per_clause.get(path, ())) | set(lines))
        # Branch evidence unions across the clause's specs BEFORE anything is called partial.
        ev = branch_ev.setdefault(sl.clause_id, {})
        for path, arms in (sl.branches or {}).items():
            slot = ev.setdefault(path, {"executed": set(), "missing": set()})
            slot["executed"] |= set(arms.get("executed") or ())
            slot["missing"] |= set(arms.get("missing") or ())
    partial = {cid: partial_lines(files, {p: {"executed": tuple(v["executed"]),
                                              "missing": tuple(v["missing"])}
                                          for p, v in (branch_ev.get(cid) or {}).items()})
               for cid, files in clauses.items()}
    return {
        "schema": SCHEMA,
        "contract_version": contract_version,
        "scenario_version": scenario_version,
        # WHICH codebase this describes, as a package URL. Not a path: a path says where
        # somebody checked something out, and that is exactly what must not matter.
        "subject": subject,
        # The clauses whose coverage actually ran. Owning no lines is a legitimate answer
        # for a spec that reads artifacts rather than modules; owning no lines because the
        # run failed is not an answer at all, and the two must stay distinguishable.
        "collected": sorted(collected),
        # Pinning the owned LINES is what closes the last hole: a refactor that shifts a
        # file changes neither the contract nor the specs, so those two pins stay green
        # while every line number in the map silently points somewhere else.
        "clause_digests": dict(sorted((clause_digests or {}).items())),
        # The third input: the spec bodies themselves. Pinning only clause and code let
        # a strengthened test change the branch evidence with every digest unmoved.
        "spec_digests": dict(sorted((spec_digests or {}).items())),
        # Owned lines with an arm never taken. Kept BESIDE `clauses` rather than inside it so
        # `owners()`, `classify()` and the per-clause digests keep their shape: a half-proved
        # line is still owned, and the pin must still move when its content changes.
        "partial": {cid: {p: list(partial[cid][p]) for p in sorted(partial[cid])}
                    for cid in sorted(partial) if partial[cid]},
        "clauses": {cid: {p: clauses[cid][p] for p in sorted(clauses[cid])}
                    for cid in sorted(clauses)},
        "specs": {sl.scenario_id: sl.clause_id for sl in sorted(spec_lines,
                                                                key=lambda s: s.scenario_id)},
    }


def clause_digest(files: dict, sources: dict) -> str:
    """PURE: fingerprint the CONTENT sitting at the lines a clause owns.

    Whole-file pinning was the safe first cut and far too blunt: any edit anywhere in a
    covered file invalidated every clause in it, so on an active file the map could never
    stay green. Hashing the owned lines instead is both tighter and still correct — an
    insertion above them shifts what those numbers point at, so the digest moves; an edit
    below or beside them does not touch what the clause owns, so it does not.

    `sources` is {path: file text}, injected — reading files is the caller's job.
    A line past the end of its file digests as a sentinel, which is itself a change.
    """
    parts = []
    for path in sorted(files):
        text = sources.get(_norm(path))
        lines = text.splitlines() if text is not None else []
        for ln in files[path]:
            body = lines[ln - 1] if 0 < ln <= len(lines) else "<gone-line>"
            parts.append(f"{_norm(path)}:{ln}:{body}")
    return _sha16("\n".join(parts))


def node_source(run_cmd: str, text: str) -> str:
    """PURE: the source of the ONE test function a run_cmd names, out of its module text.

    Empty when the command names no `path::function` node — a whole-file or `-k` command has
    no single function to hash, and pretending otherwise would invent evidence.
    """
    import ast as _ast
    node = next((tok for tok in run_cmd.split() if "::" in tok), "")
    func = node.rpartition("::")[2]
    if not func:
        return ""
    try:
        tree = _ast.parse(text)
    except SyntaxError:
        return ""
    for n in tree.body:
        if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and n.name == func:
            return _ast.get_source_segment(text, n) or ""
    return ""


def spec_digests(scenarios, sources: dict) -> dict:
    """PURE: {scenario id: digest of the test function that spec runs}.

    The map is derived from THREE things — the clause, the code, and the spec that connects
    them — and only the first two were pinned. So strengthening a test to cover the arm it
    had been missing changed the branch evidence, moved no digest, and an incremental rebuild
    reported "every clause still owns the lines it owned" while `partial` kept the answer
    from before the fix. Evidence that improves in silence rots exactly like evidence that
    decays in silence.
    """
    out = {}
    for sc in scenarios or ():
        node = next((tok for tok in sc.run_cmd.split() if "::" in tok), "")
        path = _norm(node.partition("::")[0])
        body = node_source(sc.run_cmd, sources.get(path, ""))
        out[sc.id] = _sha16(path + chr(10) + body) if body else ""
    return dict(sorted(out.items()))


def stale_specs(clause_map: dict, current: dict) -> tuple[str, ...]:
    """PURE: the scenario ids whose test function no longer holds what it held."""
    pinned = (clause_map or {}).get("spec_digests") or {}
    return tuple(sorted(sid for sid, d in pinned.items()
                        if sid in current and current[sid] != d))


def digests(clause_map: dict, sources: dict) -> dict:
    """PURE: {clause id: digest of the lines it owns} for every clause in the map."""
    return {cid: clause_digest(files, sources)
            for cid, files in sorted((clause_map.get("clauses") or {}).items())}


def stale_clauses(clause_map: dict, current: dict) -> tuple[str, ...]:
    """PURE: the clauses whose owned lines no longer hold what they held. This is the set an
    incremental rebuild has to re-derive — everything else in the map is still true."""
    pinned = (clause_map or {}).get("clause_digests") or {}
    return tuple(sorted(cid for cid, d in pinned.items()
                        if cid in current and current[cid] != d))


def merge(base: dict, spec_lines: tuple[SpecLines, ...], *, contract_version: str = "",
          scenario_version: str = "", clause_digests: dict | None = None,
          spec_digests: dict | None = None, subject: str = "",
          rebuilt: tuple[str, ...] = ()) -> dict:
    """PURE: fold freshly collected specs into an existing map, keeping what stayed true.

    Only the clauses in `rebuilt` are replaced; the rest of the map is carried over intact.
    That is what makes the map affordable on a live repo: re-deriving one clause costs one
    spec run, not the whole suite.
    """
    fresh = build(spec_lines, contract_version=contract_version,
                  scenario_version=scenario_version)
    clauses = dict((base or {}).get("clauses") or {})
    specs = dict((base or {}).get("specs") or {})
    for cid in rebuilt:
        clauses.pop(cid, None)
    clauses.update(fresh["clauses"])
    specs.update(fresh["specs"])
    kept = dict((base or {}).get("clause_digests") or {})
    kept.update(clause_digests or {})
    # A rebuilt clause carries whatever THIS run found out; the rest keep what the base said.
    got = set((base or {}).get("collected") or ()) - set(rebuilt)
    got |= set(fresh.get("collected") or ())
    # `partial` follows the same rule as ownership: a rebuilt clause takes this run's answer,
    # every other clause keeps the one already on record.
    half = {c: v for c, v in ((base or {}).get("partial") or {}).items() if c not in rebuilt}
    half.update(fresh.get("partial") or {})
    return {
        "schema": SCHEMA,
        "contract_version": contract_version,
        "scenario_version": scenario_version,
        "subject": subject or (base or {}).get("subject", ""),
        "collected": sorted(c for c in got if c in clauses),
        "partial": {c: half[c] for c in sorted(half) if c in clauses and half[c]},
        "clause_digests": {c: kept[c] for c in sorted(kept) if c in clauses},
        "spec_digests": {**((base or {}).get("spec_digests") or {}),
                         **(spec_digests or {})},
        "clauses": {c: clauses[c] for c in sorted(clauses)},
        "specs": {s: specs[s] for s in sorted(specs)},
    }


def owners(clause_map: dict, path: str, line: int) -> tuple[str, ...]:
    """PURE: which clauses own this line — reverse traceability at line granularity.

    This is the query a developer actually has: "I am about to change this line; which
    requirements am I allowed to break?"
    """
    q = _norm(path)
    return tuple(sorted(cid for cid, files in (clause_map.get("clauses") or {}).items()
                        if line in (files.get(q) or ())))


def owned_lines(clause_map: dict) -> dict:
    """PURE: {path: frozenset(lines)} — everything at least one clause owns."""
    out: dict = {}
    for files in (clause_map.get("clauses") or {}).values():
        for path, lines in files.items():
            out[path] = out.get(path, frozenset()) | frozenset(lines)
    return out


def classify(clause_map: dict, suite_lines: dict, *, files: tuple[str, ...] = ()) -> dict:
    """PURE: split every line of the given files into owned / other_coverage / unreached.

    `suite_lines` is {path: iterable_of_executed_lines} from a run of the WIDER test suite.
    The distinction it buys is the one the file-level report could not make: code that is
    tested but belongs to another feature is NOT a gap in this contract, while code nothing
    reaches at all is a gap in everybody's.
    """
    owned = owned_lines(clause_map)
    targets = tuple(_norm(f) for f in files) or tuple(sorted(owned))
    report = {}
    for path in targets:
        own = owned.get(path, frozenset())
        suite = frozenset(suite_lines.get(path, ()))
        report[path] = {
            "owned": sorted(own),
            "other_coverage": sorted(suite - own),
            "unreached": [],          # filled by the caller when it knows the file's lines
            "owned_count": len(own),
            "other_coverage_count": len(suite - own),
        }
    return report


def staleness(clause_map: dict, contract, scenarios, *, scenario_version: str = "",
              clause_digests: dict | None = None, subject: str = "") -> dict:
    """PURE: is this map still describing the contract and the specs in front of us?

    A derived artifact nobody re-derives is worse than no artifact: `owners()` keeps
    answering, confidently, from a map built two refactors ago. Four independent ways it
    goes stale, reported separately so the fix is obvious:

      absent          — no map at all, or not this schema
      contract_drift  — the map's contract pin is not the contract's current version
      spec_drift      — the map's scenario pin is not the current scenarios.md hash
      unmapped        — a live clause the map never saw (added since it was built), or one
                        whose entry is EMPTY: owning no lines is not a state a clause can be
                        proved in, and an empty entry is exactly what a failed coverage run
                        leaves behind. Counting it as "mapped" is how a rebuild silently
                        dropped 25 clauses' ownership while this gate stayed green.
      stale_entries   — a mapped clause the contract no longer defines (removed since)
      clause_drift    — a mapped CLAUSE whose owned lines no longer hold what they held:
                        the code moved even though the requirements did not

    `scenario_version` is INJECTED, because hashing a file is I/O and this stays pure.
    """
    mapped = (clause_map or {}).get("clauses") or {}
    schema_ok = (clause_map or {}).get("schema") == SCHEMA
    absent = not clause_map or not schema_ok or not mapped

    live = {c.id for c in contract.live()} if contract is not None else set()
    known = {c.id for c in contract.clauses} if contract is not None else set()
    # A clause counts as mapped when it owns lines, OR when its coverage ran and honestly
    # found none in the source roots (the binding guard reads artifacts, not modules). An
    # entry that is empty because the run FAILED is in neither set, and stays unmapped.
    owning = {cid for cid, files in mapped.items() if files}
    owning |= set((clause_map or {}).get("collected") or ()) & set(mapped)
    unmapped = sorted(live - owning)
    stale_entries = sorted(set(mapped) - known)

    clause_drift = list(stale_clauses(clause_map, clause_digests or {}))

    # A map from ANOTHER codebase answers with the confidence of a build artifact about
    # code it has never seen. Checked only when both sides name a subject: inventing an
    # identity for a map that does not claim one would be a different kind of lie.
    from lib.purl import same_subject
    map_subject = (clause_map or {}).get("subject", "")
    foreign_subject = bool(subject and map_subject and not same_subject(subject, map_subject))

    map_contract = (clause_map or {}).get("contract_version", "")
    map_scenarios = (clause_map or {}).get("scenario_version", "")
    contract_drift = bool(contract is not None and map_contract
                          and map_contract != contract.version)
    spec_drift = bool(scenario_version and map_scenarios
                      and map_scenarios != scenario_version)

    return {
        "absent": absent,
        "foreign_subject": foreign_subject,
        "map_subject": map_subject,
        "subject": subject,
        "contract_drift": contract_drift,
        "spec_drift": spec_drift,
        "unmapped": unmapped,
        "stale_entries": stale_entries,
        "clause_drift": clause_drift,
        "map_contract_version": map_contract,
        "contract_version": contract.version if contract is not None else "",
        "map_scenario_version": map_scenarios,
        "scenario_version": scenario_version,
        "specs_mapped": len((clause_map or {}).get("specs") or {}),
        "specs_now": len(scenarios or ()),
        "is_fresh": not (absent or foreign_subject or contract_drift or spec_drift
                         or unmapped or stale_entries or clause_drift),
    }


def collect(scenarios, *, sources: tuple[str, ...], workdir: str, cwd: str = ".",
            runner=None, jobs: int = 0) -> tuple[SpecLines, ...]:
    """EFFECTFUL: run every spec alone under coverage and read back the lines it executed.

    `runner(argv, cwd) -> int` is injected so the pure folding above can be tested without
    spawning 79 processes. Specs that fail to produce data are skipped with an empty file
    map rather than aborting the collection — a partial map still answers most queries.
    """
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    if runner is None:
        def runner(argv, cwd):
            return subprocess.run(argv, cwd=cwd, capture_output=True, text=True).returncode

    work = pathlib.Path(workdir)
    work.mkdir(parents=True, exist_ok=True)

    def one(sc) -> SpecLines:
        stem = sc.id.replace("/", "_").replace(".", "_")
        data = work / f"{stem}.coverage"
        js = work / f"{stem}.json"
        got = False
        try:
            runner(run_argv(sc.run_cmd, str(data), sources), cwd)
            runner(json_argv(str(data), str(js)), cwd)
            # `js` exists only when coverage had data to report. That file is the whole
            # difference between "this spec owns no lines" and "we learned nothing".
            got = js.exists()
            raw = js.read_text(encoding="utf-8") if got else ""
            files = lines_from_json(raw) if got else {}
            arms = branches_from_json(raw) if got else {}
        except (ValueError, OSError, json.JSONDecodeError):
            files, arms, got = {}, {}, False
        return SpecLines(scenario_id=sc.id, clause_id=sc.requirement_key, files=files,
                         collected=got, branches=arms)

    if not scenarios:
        return ()
    import os
    with ThreadPoolExecutor(max_workers=jobs or max(1, min(64, os.cpu_count() or 4))) as pool:
        return tuple(pool.map(one, scenarios))
