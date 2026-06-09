"""
Athena front selection — pick the parser by the ATHENA_SPECKIT toggle (§6).

The 3-layer <-> 2-layer switch is exactly this one choice; everything downstream (the
Plan AST and plan2beads) is identical, which is why the toggle costs nothing.
  ATHENA_SPECKIT=on  -> speckit_parser(tasks.md)   [primary]
  ATHENA_SPECKIT=off -> plan_parser(plan.md)        [fallback]
"""
from __future__ import annotations

import os
import pathlib

from lib.ast import Plan


def speckit_enabled() -> bool:
    return os.environ.get("ATHENA_SPECKIT", "on").strip().lower() != "off"


def parse_source(path: str, *, speckit: bool | None = None) -> Plan:
    """Read the front file at `path` and parse it with the toggled parser."""
    if speckit is None:
        speckit = speckit_enabled()
    text = pathlib.Path(path).read_text(encoding="utf-8")
    if speckit:
        from lib.speckit_parser import parse
    else:
        from lib.plan_parser import parse
    return parse(text)
