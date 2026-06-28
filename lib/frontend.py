"""
Athena front selection — pick the parser by the ATHENA_SPECKIT toggle (§6).

The 3-layer <-> 2-layer switch is exactly this one choice; everything downstream (the
Plan AST and plan2beads) is identical, which is why the toggle costs nothing.
  ATHENA_SPECKIT=on  -> speckit_parser(tasks.md)   [primary]
  ATHENA_SPECKIT=off -> plan_parser(plan.md)        [fallback]
"""
from __future__ import annotations

import dataclasses
import os
import pathlib

from lib.ast import Plan, Provenance


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


def parse_with_provenance(path: str, *, speckit: bool | None = None,
                          run_id: str = "") -> Plan:
    """Parse the front AND attach sibling provenance so the v3.1 graph materialises.

    The bare front (plan.md / tasks.md) carries `Task.verifies` but no Scenario objects
    and no version pins, so `plan2beads` cannot emit scenario nodes or verifies/satisfies
    edges (it guards on `provenance.spec_version` + `provenance.scenario_version`). This
    helper looks for `spec.md` and `scenarios.md` next to the front, parses the scenarios,
    and pins both versions to deterministic content hashes — turning a flat front into a
    full provenance source WITHOUT requiring an `.athena/seams.jsonl` pinning run.

    If no sibling `scenarios.md` exists, the plan is returned unchanged (v2/flat behaviour).
    """
    from lib.versioning import hash_file

    plan = parse_source(path, speckit=speckit)
    front = pathlib.Path(path)
    scen_path = front.parent / "scenarios.md"
    spec_path = front.parent / "spec.md"
    design_path = front.parent / "design.md"

    if not scen_path.exists():
        return plan

    from lib.scenario_parser import parse as parse_scenarios
    scenarios = parse_scenarios(scen_path.read_text(encoding="utf-8"))

    # spec_version is REQUIRED for any provenance emission; fall back to the scenarios
    # hash only if spec.md is absent so the edges still resolve.
    spec_version = hash_file(spec_path) if spec_path.exists() else hash_file(scen_path)
    provenance = Provenance(
        spec_version=spec_version,
        scenario_version=hash_file(scen_path),
        design_version=hash_file(design_path) if design_path.exists() else "",
        run_id=run_id,
    )
    return dataclasses.replace(plan, scenarios=scenarios, provenance=provenance)
