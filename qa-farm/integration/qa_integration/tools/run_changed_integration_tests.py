"""L1: decide which integration tests to run for a change. Composes changed_boundaries with a
boundary→tests map and handles the two edge cases explicitly: no relevant change (run nothing,
exit clean) and a docker-compose/shared-fixture change (fall back to the full run)."""
from __future__ import annotations

from dataclasses import dataclass

from qa_integration.config import Config, is_compose_or_fixture_change
from qa_integration.primitives.changed_boundaries import changed_boundaries


@dataclass(frozen=True)
class Selection:
    tests: tuple[str, ...]
    boundaries: tuple[str, ...]
    reason: str          # "affected" | "no_relevant_change" | "compose_change_full_run"
    full_run: bool


def select_integration_tests(changed_paths, boundary_map, test_map, *, cfg=None,
                             boundary_graph=None, all_tests=None) -> Selection:
    cfg = cfg or Config()
    if all_tests is None:
        all_tests = tuple(sorted({t for ts in test_map.values() for t in ts}))
    else:
        all_tests = tuple(all_tests)

    # EC-2 / R1.3: a docker-compose or shared-fixture change invalidates impact analysis —
    # fall back to the full run rather than risk under-selection.
    if any(is_compose_or_fixture_change(p, cfg) for p in changed_paths):
        return Selection(tests=all_tests, boundaries=tuple(sorted(boundary_map)),
                         reason="compose_change_full_run", full_run=True)

    boundaries = changed_boundaries(changed_paths, boundary_map, boundary_graph=boundary_graph)
    # EC-1 / R1.2: nothing under integration test changed → run nothing; never a full-run
    # fallback here (that would defeat the point of change-scoping).
    if not boundaries:
        return Selection(tests=(), boundaries=(), reason="no_relevant_change", full_run=False)

    selected: list[str] = []
    for b in boundaries:
        selected.extend(test_map.get(b, []))
    return Selection(tests=tuple(sorted(set(selected))), boundaries=tuple(boundaries),
                     reason="affected", full_run=False)
