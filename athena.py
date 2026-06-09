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

from lib.frontend import parse_source                       # noqa: E402
from lib.plan2beads import compile, CompileError, _slugify  # noqa: E402
from lib.hermes_plan import render_master_plan              # noqa: E402
from lib import seams                                       # noqa: E402


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
    plan = parse_source(a.front, speckit=_speckit(a.speckit))
    res = compile(plan)
    _emit({"epics": len(res.epic_keys), "issues": res.issue_count, "commands": len(res.commands)})
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
    plan = parse_source(front, speckit=_speckit(a.speckit))
    if name == "ast_wellformed":
        r = seams.seam_ast_wellformed(plan)
    elif name == "compile_pure":
        r = seams.seam_compile_pure(compile, plan)
    else:
        _emit({"error": f"unknown seam: {a.name}"})
        return 2
    _emit({"seam": r.name, "passed": r.passed, "issues": list(r.issues), "hash": r.artifact_hash})
    return 0 if r.passed else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="athena")
    p.add_argument("--speckit", choices=("on", "off", "auto"), default="auto")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate"); v.add_argument("front"); v.set_defaults(fn=cmd_validate)
    c = sub.add_parser("compile"); c.add_argument("front"); c.set_defaults(fn=cmd_compile)
    h = sub.add_parser("hermes-plan")
    h.add_argument("front", nargs="?", default=""); h.add_argument("-o", "--out", default="")
    h.add_argument("--plan-id", dest="plan_id", default=""); h.add_argument("--created", default="")
    h.set_defaults(fn=cmd_hermes_plan)
    s = sub.add_parser("seam"); s.add_argument("name"); s.add_argument("front", nargs="?", default="")
    s.set_defaults(fn=cmd_seam)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
