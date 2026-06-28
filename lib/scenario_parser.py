"""
Athena scenario_parser — canonical scenarios.md -> tuple[Scenario] (v3.1).

Parses the `/athena.scenarios` output (one Given-When-Then block per EARS criterion)
back into `lib.ast.Scenario` objects so the compiler can materialise the v3.1
provenance edges (scenario --validates--> spec, task --tracks--> scenario).

Format (stdlib-only, line-oriented state machine):

    ### S1.1 — New game places the snake
    - **verifies:** R1.1
    - **run_cmd:** `pytest tests/test_snake_body.py::test_initial_placement -q`
    - **Given** a new game ...
    - **When** the game is initialized
    - **Then** the snake occupies ...

A scenario block ends at the next `###`/`##` heading or EOF. `verifies:` is the spec
requirement key (R-n); `run_cmd:` is the executable success-check; the Given/When/Then
bullets are concatenated into `gwt_text`.
"""
from __future__ import annotations

import re

from lib.ast import ParseError, Scenario


class ScenarioParseError(ParseError):
    """Canonical scenarios.md format violated."""


# `### S1.2 — title` or `### S1.2 - title` (em-dash or hyphen separator, optional)
_SCEN_RE = re.compile(r"^###\s+(S\d+\.\d+)\s*(?:[—\-]\s*(.*))?$")
_VERIFIES_RE = re.compile(r"^-\s*\*\*verifies:\*\*\s*`?(.+?)`?\s*$", re.IGNORECASE)
_RUNCMD_RE = re.compile(r"^-\s*\*\*run_cmd:\*\*\s*`?(.+?)`?\s*$", re.IGNORECASE)
# Given / When / Then bullet — bold marker optional, prose follows
_GWT_RE = re.compile(r"^-\s*\*\*(Given|When|Then|And)\*\*\s*(.*)$", re.IGNORECASE)


def parse(text: str) -> tuple[Scenario, ...]:
    """Line-oriented parser. Deterministic, stdlib-only. Returns scenarios in document order."""
    scenarios: list[Scenario] = []
    cur: dict | None = None
    gwt: list[str] = []

    def flush():
        nonlocal cur, gwt
        if cur is None:
            return
        sid = cur["id"]
        if not cur.get("requirement_key"):
            raise ScenarioParseError(f"scenario {sid} missing **verifies:** requirement key")
        if not cur.get("run_cmd"):
            raise ScenarioParseError(f"scenario {sid} missing **run_cmd:**")
        scenarios.append(Scenario(
            id=sid,
            requirement_key=cur["requirement_key"],
            gwt_text=" ".join(g.strip() for g in gwt if g.strip()).strip(),
            run_cmd=cur["run_cmd"],
        ))
        cur, gwt = None, []

    for raw in text.splitlines():
        m = _SCEN_RE.match(raw)
        if m:
            flush()
            cur = {"id": m.group(1)}
            title = (m.group(2) or "").strip()
            if title:
                gwt.append(title)
            continue
        if raw.startswith("## ") and not raw.startswith("###"):
            flush()            # a new requirement group ends the current scenario
            continue
        if cur is None:
            continue
        mv = _VERIFIES_RE.match(raw)
        if mv:
            cur["requirement_key"] = mv.group(1).strip()
            continue
        mr = _RUNCMD_RE.match(raw)
        if mr:
            cur["run_cmd"] = mr.group(1).strip()
            continue
        mg = _GWT_RE.match(raw)
        if mg:
            gwt.append(f"{mg.group(1).capitalize()} {mg.group(2).strip()}".strip())
            continue
        # continuation of the previous bullet: a Given/When/Then clause wrapped onto an
        # indented line with no marker. Append to the last gwt entry so multi-line prose
        # is not silently truncated (regression: 4/31 snake scenarios cut mid-sentence).
        if gwt and raw[:1] in (" ", "\t") and raw.strip():
            gwt[-1] = f"{gwt[-1]} {raw.strip()}"
            continue

    flush()

    if not scenarios:
        raise ScenarioParseError("no scenarios parsed (expected '### S<n>.<m>' headings)")

    seen: set[str] = set()
    for sc in scenarios:
        if sc.id in seen:
            raise ScenarioParseError(f"duplicate scenario id {sc.id}")
        seen.add(sc.id)

    return tuple(scenarios)
