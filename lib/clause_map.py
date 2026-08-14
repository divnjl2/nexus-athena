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

import json
import pathlib
import shlex
from dataclasses import dataclass

SCHEMA = "athena.clause_map/1"


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip().lstrip("./")


@dataclass(frozen=True)
class SpecLines:
    """Lines one spec executed, per file. The atom the map is folded from."""
    scenario_id: str
    clause_id: str
    files: dict            # normalized path -> tuple[int, ...]


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
    return ["python", "-m", "coverage", "run", f"--data-file={data_file}",
            *[f"--source={s}" for s in sources], *argv]


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


def build(spec_lines: tuple[SpecLines, ...], *, contract_version: str = "",
          scenario_version: str = "") -> dict:
    """PURE: fold per-spec line sets into the clause map artifact.

    A clause owns the UNION of the lines its specs execute. Two clauses may own the same
    line — that is not a conflict, it is shared code serving two requirements, and the
    owners() query returns both.
    """
    clauses: dict = {}
    for sl in spec_lines:
        per_clause = clauses.setdefault(sl.clause_id, {})
        for path, lines in sl.files.items():
            per_clause[path] = sorted(set(per_clause.get(path, ())) | set(lines))
    return {
        "schema": SCHEMA,
        "contract_version": contract_version,
        "scenario_version": scenario_version,
        "clauses": {cid: {p: clauses[cid][p] for p in sorted(clauses[cid])}
                    for cid in sorted(clauses)},
        "specs": {sl.scenario_id: sl.clause_id for sl in sorted(spec_lines,
                                                                key=lambda s: s.scenario_id)},
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
        try:
            runner(run_argv(sc.run_cmd, str(data), sources), cwd)
            runner(json_argv(str(data), str(js)), cwd)
            files = lines_from_json(js.read_text(encoding="utf-8")) if js.exists() else {}
        except (ValueError, OSError, json.JSONDecodeError):
            files = {}
        return SpecLines(scenario_id=sc.id, clause_id=sc.requirement_key, files=files)

    if not scenarios:
        return ()
    import os
    with ThreadPoolExecutor(max_workers=jobs or max(1, min(64, os.cpu_count() or 4))) as pool:
        return tuple(pool.map(one, scenarios))
