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
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from lib.frontend import parse_source                       # noqa: E402
from lib.plan2beads import compile, _slugify                # noqa: E402
from lib.hermes_plan import render_master_plan              # noqa: E402
from lib import seams                                       # noqa: E402


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
    plan = parse_source(a.front, speckit=_speckit(a.speckit))
    aw = seams.seam_ast_wellformed(plan)
    if not aw.passed:
        _emit({"seam": aw.name, "passed": False, "issues": list(aw.issues)})
        return 1
    compile(plan)  # determinism + compile-time validation before we emit
    md = render_master_plan(plan, plan_id=a.plan_id or _slugify(plan.title), created=a.created or "")
    pathlib.Path(a.out).write_text(md, encoding="utf-8")
    _emit({"out": a.out, "tasks": sum(len(p.tasks) for p in plan.phases), "plan_id": a.plan_id or _slugify(plan.title)})
    return 0


def cmd_seam(a) -> int:
    plan = parse_source(a.front, speckit=_speckit(a.speckit))
    if a.name in ("ast_wellformed", "seam.ast_wellformed"):
        r = seams.seam_ast_wellformed(plan)
    elif a.name in ("compile_pure", "seam.compile_pure"):
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
    h.add_argument("front"); h.add_argument("-o", "--out", required=True)
    h.add_argument("--plan-id", dest="plan_id", default=""); h.add_argument("--created", default="")
    h.set_defaults(fn=cmd_hermes_plan)
    s = sub.add_parser("seam"); s.add_argument("name"); s.add_argument("front"); s.set_defaults(fn=cmd_seam)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
