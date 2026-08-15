"""
Athena mutation — does a spec PROVE anything? (v3.4, deterministic, no model)

`assert True` passes every gate in this repo: coverage sees the line, the ledger sees exit 0,
the map sees ownership. The only mechanical way to ask "does this spec prove anything" is to
break the code the clause owns and check that the clause's specs notice.

The clause map is what makes this affordable. Mutating a whole repo is hours; mutating only
the lines a clause owns, and running only the specs of the clauses that own THAT line, is
seconds. Both scopings come straight out of `clause_map.owners()`.

Four method errors this module exists to avoid, ALL of them found by running it, none by
reading it:
  * regex mutation hits comments and string constants and produces equivalent mutants that
    "survive" while meaning nothing. Mutations here are AST-level and skip docstrings.
  * scoping the run to the OWNING clause's specs alone reported false vacuity: a line owned
    by many clauses is proved by whichever spec asserts it. The run set is every owner's
    specs (`scoped_specs`), and a mutant dies the moment any of them goes red.
  * `finally: restore` is NOT enough. A timeout takes the process out between the write and
    the restore — twice, here — and the repo is left holding a mutant.
  * so the harness does not mutate the working tree AT ALL. `isolate()` mirrors the repo
    into a scratch directory and everything happens there; the worst a killed run can now
    leave behind is a temp folder. `snapshot`/`recover` remain for callers that insist on
    running in place.

Freeze-line: `mutants`, `scoped_specs`, `summarize` are PURE; `hunt`, `isolate`, `snapshot`,
`recover` are effectful and take injected I/O where it matters.
"""
from __future__ import annotations

import ast
import copy
import json
import pathlib
import shutil
from dataclasses import dataclass

_FLIP_CMP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt,
             ast.Gt: ast.LtE, ast.LtE: ast.Gt, ast.In: ast.NotIn, ast.NotIn: ast.In,
             ast.Is: ast.IsNot, ast.IsNot: ast.Is}
_FLIP_BOOL = {ast.And: ast.Or, ast.Or: ast.And}

LOCK = ".athena/mutation_lock.json"
#: never copied into the mirror: history, databases, caches, other people's artifacts
_SKIP_DIRS = {".git", ".beads", ".athena", "node_modules", "__pycache__", ".pytest_cache",
              ".venv", "venv", ".deepeval", "console", "vendor", "evals", "obsidian-ai-pack"}


@dataclass(frozen=True)
class Mutant:
    """One broken version of the source, and where the break is."""
    path: str
    line: int
    kind: str
    source: str


def _sites(tree: ast.AST, lines: frozenset[int]) -> list[tuple[ast.AST, str]]:
    """Nodes ON the owned lines that carry decidable behaviour. Docstrings and bare string
    constants are skipped: mutating prose yields an equivalent mutant, which is noise."""
    out: list[tuple[ast.AST, str]] = []
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) not in lines:
            continue
        if isinstance(node, ast.Compare) and type(node.ops[0]) in _FLIP_CMP:
            out.append((node, f"flip {type(node.ops[0]).__name__}"))
        elif isinstance(node, ast.BoolOp) and type(node.op) in _FLIP_BOOL:
            out.append((node, f"flip {type(node.op).__name__}"))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            out.append((node, "drop not"))
        elif isinstance(node, ast.Constant) and id(node) not in docstrings \
                and isinstance(node.value, bool):
            out.append((node, f"{node.value} -> {not node.value}"))
    return out


def mutants(source: str, lines, path: str = "") -> tuple[Mutant, ...]:
    """PURE: every single-point AST mutation on the given lines, in document order.

    One mutation per mutant: a mutant that changes two things cannot tell you which one the
    specs failed to notice.
    """
    owned = frozenset(int(x) for x in lines)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()
    out: list[Mutant] = []
    for index, (_, kind) in enumerate(_sites(tree, owned)):
        clone = ast.parse(source)
        target, _ = _sites(clone, owned)[index]
        line = getattr(target, "lineno", 0)
        if isinstance(target, ast.Compare):
            target.ops = [_FLIP_CMP[type(target.ops[0])]()] + list(target.ops[1:])
        elif isinstance(target, ast.BoolOp):
            target.op = _FLIP_BOOL[type(target.op)]()
        elif isinstance(target, ast.UnaryOp):
            _replace(clone, target, copy.deepcopy(target.operand))
        elif isinstance(target, ast.Constant):
            target.value = not target.value
        out.append(Mutant(path=path, line=line, kind=kind,
                          source=ast.unparse(ast.fix_missing_locations(clone))))
    return tuple(out)


def _replace(tree: ast.AST, old: ast.AST, new: ast.AST) -> None:
    """Swap a node for another in place (used to drop a `not`)."""
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if value is old:
                setattr(parent, field, new)
                return
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if item is old:
                        value[i] = new
                        return


def scoped_specs(clause_map: dict, spec_cmds: dict, path: str, line: int) -> tuple[str, ...]:
    """PURE: the run_cmds that must notice a break at this line — every OWNER's specs.

    Scoping to a single clause is the error that produced false vacuity in the first probe:
    a line owned by 93 clauses is proved by whichever of them asserts it.
    """
    from lib.clause_map import owners
    ids = set(owners(clause_map, path, line))
    return tuple(cmd for sid, (cid, cmd) in sorted(spec_cmds.items()) if cid in ids)


def summarize(results: tuple[dict, ...]) -> dict:
    """PURE: the report. `survivors` is the answer to "which specs prove nothing".

    A mutant whose spec budget ran out is NOT a survivor: it is undetermined, counted apart,
    and it never claims that anything failed to prove anything.
    """
    survivors = [r for r in results if r.get("status", "survived" if not r["killed"]
                                             else "killed") == "survived"]
    undetermined = [r for r in results if r.get("status") == "undetermined"]
    decided = len(results) - len(undetermined)
    return {
        "mutants": len(results),
        "killed": sum(1 for r in results if r["killed"]),
        "survived": len(survivors),
        "undetermined": len(undetermined),
        "score": round(sum(1 for r in results if r["killed"]) / decided, 4) if decided else 1.0,
        "survivors": survivors,
    }


def isolate(repo: str, mirror: str, *, skip: frozenset = frozenset(_SKIP_DIRS)) -> str:
    """EFFECTFUL: mirror the repo into a scratch tree so mutation never touches the original.

    This is the answer to a harness that was killed twice mid-mutation. A copy costs a
    second; a mutant left in `lib/` costs trust in every green run after it.
    """
    src, dst = pathlib.Path(repo).resolve(), pathlib.Path(mirror)
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*skip), dirs_exist_ok=False)
    return str(dst)


def snapshot(targets: dict, *, lock_path: str = LOCK) -> str:
    """EFFECTFUL: write the pristine sources to disk BEFORE the first mutation.

    Kept for in-place callers. `finally` cannot survive a kill, so recovery has to belong to
    the next invocation rather than to the process that died.
    """
    p = pathlib.Path(lock_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"schema": "athena.mutation_lock/1",
                             "files": {path: spec["source"] for path, spec in targets.items()}},
                            ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    return str(p)


def recover(*, lock_path: str = LOCK, writer=None) -> tuple[str, ...]:
    """EFFECTFUL: put every snapshotted file back and drop the lock. Safe to call always."""
    p = pathlib.Path(lock_path)
    if not p.exists():
        return ()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ()
    if writer is None:
        def writer(path, text):
            pathlib.Path(path).write_text(text, encoding="utf-8")
    restored = []
    for path, text in sorted((data.get("files") or {}).items()):
        writer(path, text)
        restored.append(path)
    p.unlink()
    return tuple(restored)


def hunt(clause_map: dict, spec_cmds: dict, targets: dict, *, runner, writer,
         limit_per_line: int = 1, max_mutants: int = 0,
         max_specs: int = 0) -> tuple[dict, ...]:
    """EFFECTFUL: build mutants, run each against its owners' specs, stop at first killer.

    `runner(cmd) -> int` and `writer(path, text) -> None` are injected, so the caller decides
    WHERE this happens — and the CLI points both at an isolated mirror, never at the repo.
    """
    results: list[dict] = []
    for path, spec in sorted(targets.items()):
        original, lines = spec["source"], spec["lines"]
        per_line: dict[int, int] = {}
        for mut in mutants(original, lines, path=path):
            if max_mutants and len(results) >= max_mutants:
                return tuple(results)
            if per_line.get(mut.line, 0) >= limit_per_line:
                continue
            per_line[mut.line] = per_line.get(mut.line, 0) + 1
            cmds = scoped_specs(clause_map, spec_cmds, path, mut.line)
            budget = cmds[:max_specs] if max_specs else cmds
            killed, killer, ran = False, "", 0
            try:
                writer(path, mut.source)
                for cmd in budget:
                    ran += 1
                    if runner(cmd) != 0:
                        killed, killer = True, cmd
                        break
            finally:
                writer(path, original)
            # THREE outcomes, not two. A line owned by 129 clauses cannot be swept inside a
            # CI budget, and calling the leftover "survived" would manufacture vacuity claims
            # nobody checked. Undetermined is the honest third state.
            status = "killed" if killed else (
                "survived" if ran >= len(cmds) else "undetermined")
            results.append({"path": path, "line": mut.line, "kind": mut.kind,
                            "specs_run": ran, "specs_total": len(cmds),
                            "status": status, "killed": killed, "killer": killer})
    return tuple(results)
