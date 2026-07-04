"""L0: coverage.xml (Cobertura) → per-boundary line/branch coverage + delta vs a base line
rate. Pure XML parsing; no thresholds, no PASS/FAIL (that is L1)."""
from __future__ import annotations

import xml.etree.ElementTree as ET


def parse_coverage_text(xml_text: str, boundary_map, *, base_line: dict | None = None) -> dict:
    """`boundary_map` maps boundary_name -> list of path prefixes it owns. Every <class> whose
    filename matches a boundary's prefix contributes its line hits to that boundary's tally; a
    class matching no boundary is ignored (out of scope for the integration gate). A boundary
    with NO matching class at all still appears in the output at 0% — never "no data"."""
    root = ET.fromstring(xml_text)
    base_line = base_line or {}

    tallies = {b: {"covered": 0, "total": 0, "branch_covered": 0, "branch_total": 0}
               for b in boundary_map}

    for cls in root.iter("class"):
        path = cls.get("filename", "")
        boundary = _owning_boundary(path, boundary_map)
        if boundary is None:
            continue
        t = tallies[boundary]
        for ln in cls.iter("line"):
            number = ln.get("number")
            if number is None:
                continue
            t["total"] += 1
            if int(ln.get("hits", 0)) > 0:
                t["covered"] += 1
            if ln.get("branch") == "true":
                t["branch_total"] += 1
                cov = ln.get("condition-coverage", "")
                if cov and "100%" in cov:
                    t["branch_covered"] += 1

    boundaries_out = {}
    for boundary, t in tallies.items():
        line = round(t["covered"] / t["total"], 4) if t["total"] else 0.0
        branch = round(t["branch_covered"] / t["branch_total"], 4) if t["branch_total"] else 0.0
        delta = None if boundary not in base_line else round(line - base_line[boundary], 4)
        boundaries_out[boundary] = {
            "line": line, "branch": branch, "delta": delta, "has_tests": t["total"] > 0,
        }
    return {"boundaries": boundaries_out}


def _owning_boundary(path, boundary_map):
    """When two boundaries declare overlapping prefixes (e.g. "services/" and
    "services/billing/"), the MOST SPECIFIC (longest) matching prefix wins, deterministically
    — never whichever boundary happens to iterate first in `boundary_map`."""
    p = path.replace("\\", "/")
    best_boundary = None
    best_len = -1
    for boundary, prefixes in boundary_map.items():
        for prefix in prefixes:
            prefix = prefix.replace("\\", "/").rstrip("/")
            if (p == prefix or p.startswith(prefix + "/")) and len(prefix) > best_len:
                best_len = len(prefix)
                best_boundary = boundary
    return best_boundary
