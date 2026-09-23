"""
Athena cases — a spec as DATA: given / when / then in JSON, run in the current process (v3.11).

Every executable spec used to be a pytest node bound to a clause by its docstring, and the
Given/When/Then in scenarios.md was prose nothing executed. That proves an implementation:
a refactor breaks specs whose behaviour did not change, and a second language means a
rewrite. The reference approach gets thousands of specs per second because specs are data
over a pure core, not because the runner is clever (ADR-0001).

A case:

    {"clause": "C-1.1",
     "given": {"text": "# Contract: X\\n\\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\\n"},
     "when":  {"call": "lib.contract:parse", "args": ["$text"]},
     "then":  [{"path": "clauses[0].id", "equals": "C-1.1"},
               {"path": "clauses", "length": 1}]}

`given` names values, `when` calls one `module:callable` with `$name` references resolved
from given, `then` is a non-empty list of checks: equals, contains, truthy, startswith,
length, raises, pending. `pending` is how intake writes a spec that is red until somebody
writes the assertion (C-3.5).

Freeze-line: no process is spawned here, ever (C-1.2). Importing the subject is the one
effect, and it is injectable. Reading the file is `load_case`, kept apart from `run_case`.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass

SCHEMA = "athena.case/1"
CHECKS = ("equals", "contains", "truthy", "startswith", "length", "raises", "pending")
_TAIL = 400
_PATH_TOKEN = re.compile(r"\[(\d+)\]|([^.\[\]]+)")


class CaseError(ValueError):
    """The case FILE is malformed: a missing part, an unknown check, a bad reference."""


@dataclass(frozen=True)
class CaseResult:
    passed: bool
    message: str
    duration_ms: int


def parse_case(data) -> dict:
    """PURE: validate a case and return its normalised shape (C-1.1)."""
    if not isinstance(data, Mapping):
        raise CaseError("a case is a JSON object with given, when and then")
    for part in ("given", "when", "then"):
        if part not in data:
            raise CaseError(f"case is missing its {part} part")
    given, when, then = data["given"], data["when"], data["then"]
    if not isinstance(given, Mapping):
        raise CaseError("given must be an object of named values")
    if not isinstance(when, Mapping) or not isinstance(when.get("call"), str) \
            or ":" not in when["call"]:
        raise CaseError("when needs a call of the form module:callable")
    if not isinstance(then, list) or not then:
        raise CaseError("then must be a non-empty list of checks")
    for chk in then:
        if not isinstance(chk, Mapping) or not any(k in chk for k in CHECKS):
            raise CaseError(f"unknown check {chk!r}; one of {', '.join(CHECKS)}")
    return {
        "clause": str(data.get("clause", "")),
        "given": dict(given),
        "when": {"call": when["call"], "args": list(when.get("args", [])),
                 "kwargs": dict(when.get("kwargs", {}))},
        "then": [dict(c) for c in then],
    }


def resolve_ref(value, given: Mapping):
    """PURE: `$name` -> given[name], recursively through lists and objects."""
    if isinstance(value, str) and value.startswith("$"):
        name = value[1:]
        if name not in given:
            raise CaseError(f"unknown given ${name}")
        return given[name]
    if isinstance(value, list):
        return [resolve_ref(v, given) for v in value]
    if isinstance(value, Mapping):
        return {k: resolve_ref(v, given) for k, v in value.items()}
    return value


def get_path(obj, path: str):
    """PURE: `clauses[0].id` -> obj.clauses[0].id; "" or "$" is the object itself."""
    if path in ("", "$"):
        return obj
    for index, name in _PATH_TOKEN.findall(path):
        if index:
            obj = obj[int(index)]
        elif isinstance(obj, Mapping):
            obj = obj[name]
        else:
            obj = getattr(obj, name)
    return obj


def _load_callable(spec: str, importer):
    module, _, attr = spec.partition(":")
    obj = importer(module)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


def run_case(case: dict, *, importer=None) -> CaseResult:
    """Run one parsed case in THIS process; red with expected/actual on a failed check
    (C-1.2, C-1.3, C-1.4). `importer` is the only effect and is injectable."""
    importer = importer or importlib.import_module
    t0 = time.perf_counter()

    def done(passed: bool, message: str) -> CaseResult:
        return CaseResult(passed, message[-_TAIL:] if message else "",
                          int((time.perf_counter() - t0) * 1000))

    try:
        fn = _load_callable(case["when"]["call"], importer)
        args = resolve_ref(case["when"]["args"], case["given"])
        kwargs = resolve_ref(case["when"]["kwargs"], case["given"])
    except (CaseError, ImportError, AttributeError) as e:
        return done(False, f"when: {e}")

    raised = None
    result = None
    try:
        result = fn(*args, **kwargs)
    except Exception as e:                      # noqa: BLE001 — the case decides what counts
        raised = e

    for chk in case["then"]:
        if "pending" in chk:
            return done(False, f"pending: {chk['pending']}")
        if "raises" in chk:
            want = chk["raises"]
            if raised is None:
                return done(False, f"raises: expected {want}, got a return value {result!r}")
            names = {c.__name__ for c in type(raised).__mro__}
            if want not in names:
                return done(False, f"raises: expected {want}, got {type(raised).__name__}: {raised}")
            continue
        if raised is not None:
            return done(False, f"when: raised {type(raised).__name__}: {raised}")
        path = chk.get("path", "")
        try:
            actual = get_path(result, path)
        except (KeyError, IndexError, AttributeError, TypeError, ValueError) as e:
            return done(False, f"{path}: not reachable ({type(e).__name__}: {e})")
        if "equals" in chk and actual != chk["equals"]:
            return done(False, f"{path}: expected {chk['equals']!r}, got {actual!r}")
        if "contains" in chk and chk["contains"] not in actual:
            return done(False, f"{path}: expected to contain {chk['contains']!r}, got {actual!r}")
        if "truthy" in chk and bool(actual) != bool(chk["truthy"]):
            return done(False, f"{path}: expected truthy={chk['truthy']}, got {actual!r}")
        if "startswith" in chk and not str(actual).startswith(str(chk["startswith"])):
            return done(False, f"{path}: expected to start with {chk['startswith']!r}, got {actual!r}")
        if "length" in chk and len(actual) != chk["length"]:
            return done(False, f"{path}: expected length {chk['length']}, got {len(actual)}")
    return done(True, "")


def derived_run_cmd(case_path) -> str:
    """PURE: the command that replays a case through the CLI (C-1.5), so the clause map,
    the mutation sweep and the binding guard see a command like any other."""
    return f"python -m athena case run {str(case_path).replace(chr(92), '/')}"


def load_case(path, cwd: str = ".") -> dict:
    """EFFECTFUL (file read): the parsed case at `path`, relative to `cwd` unless absolute."""
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = pathlib.Path(cwd) / p
    return parse_case(json.loads(p.read_text(encoding="utf-8")))


def binding_issues(scenarios, cases: Mapping) -> tuple[str, ...]:
    """PURE: a case must document the clause its scenario verifies (C-1.7), the same rule
    the pytest guard applies to docstrings. `cases` is {case path: case dict}."""
    out: list[str] = []
    for s in scenarios:
        case_path = getattr(s, "case", "")
        if not case_path:
            continue
        case = cases.get(case_path)
        if case is None:
            out.append(f"{s.id}: case {case_path} not found")
        elif case.get("clause") and case["clause"] != s.requirement_key:
            out.append(f"{s.id} verifies {s.requirement_key} but its case {case_path} "
                       f"documents {case['clause']}")
    return tuple(out)
