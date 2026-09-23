"""L0: a list of changed paths → the set of affected service boundaries, expanded by a
reverse-dependency closure (any boundary that depends on an affected boundary is also
affected)."""
from __future__ import annotations


def changed_boundaries(changed_paths, boundary_map, *, boundary_graph=None) -> list[str]:
    """`boundary_map` maps boundary_name -> list of path prefixes/globs it owns. `boundary_graph`
    maps boundary -> list of boundaries it depends on; the reverse closure adds any boundary
    that depends on an already-affected one."""
    boundary_graph = boundary_graph or {}
    changed = {p.replace("\\", "/") for p in changed_paths}

    direct = set()
    for boundary, prefixes in boundary_map.items():
        owned = {p.replace("\\", "/") for p in prefixes}
        if any(c == o or c.startswith(o.rstrip("/") + "/") for c in changed for o in owned):
            direct.add(boundary)

    affected = set(direct)
    frontier = list(direct)
    while frontier:
        cur = frontier.pop()
        for boundary, deps in boundary_graph.items():
            if cur in deps and boundary not in affected:
                affected.add(boundary)
                frontier.append(boundary)
    return sorted(affected)
