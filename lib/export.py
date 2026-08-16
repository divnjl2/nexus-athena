"""
Athena export — publishing the contract so another repository can point at it (v3.8).

"Independent of the repository" cannot mean "everybody checks out everybody". Sphinx-needs
answered this years ago and the answer is boring in the right way: each project publishes a
machine-readable index of its items, and other projects consume it by namespace, exactly as
intersphinx does for documentation cross-references. Nobody clones anything.

So this module emits two shapes of the same content:

  needs      the sphinx-needs `needs.json` shape — versions -> needs -> {id, type, title,
             status, links, ...}. A consumer that already reads needs.json reads ours.
  oft        OpenFastTrace's specobject XML, so its tracing suite can ingest our clauses
             next to whatever else a team already traces.

Neither is our own invention, and that is the point: an index only helps if something on the
other side already knows how to read it.

Freeze-line: PURE. Writing files, and stamping a build time, belong to the CLI.
"""
from __future__ import annotations

import json
from xml.sax.saxutils import escape

#: sphinx-needs writes a `current_version` plus a versions map; consumers select by version.
NEEDS_SCHEMA = "needs.json/1"

#: Our clause statuses in sphinx-needs' vocabulary. `open`/`implemented` is the convention
#: their filters expect; the athena status is kept verbatim alongside so nothing is lost.
_NEEDS_STATUS = {"active": "open", "draft": "draft",
                 "superseded": "superseded", "withdrawn": "withdrawn"}

#: OFT insists on `artifact-type~name~revision`. Our ids carry no revision, so the clause
#: version stands in for one: a reference made against an old wording is then visibly old.
OFT_TYPE = "req"


def _needs_links(clause) -> list:
    return list(clause.superseded_by) + list(clause.supersedes)


def to_needs(contract, *, project: str = "", version: str = "",
             coverage: dict | None = None, clause_map: dict | None = None) -> dict:
    """PURE: contract -> the sphinx-needs `needs.json` shape.

    `project` is the namespace a consumer will prefix our ids with, which is what lets two
    projects both own a `C-1.1` without a collision — the same trick intersphinx plays with
    documentation labels.

    Coverage and the map are optional and, when present, travel WITH the index: a consumer
    then sees not only "this requirement exists" but "it is proved, and by this much code".
    That is the part a plain requirements index cannot say.
    """
    covered = set((coverage or {}).get("covered", ()))
    owned = (clause_map or {}).get("clauses") or {}
    partial = (clause_map or {}).get("partial") or {}

    needs = {}
    for c in contract.clauses:
        files = owned.get(c.id) or {}
        needs[c.id] = {
            "id": c.id,
            "type": "req",
            "title": c.text[:120],
            "description": c.text,
            "status": _NEEDS_STATUS.get(c.status, c.status),
            "athena_status": c.status,
            "version": c.version,
            "docname": project or contract.title,
            "section": c.group,
            "tags": list(c.tags),
            "links": _needs_links(c),
            "refs": list(c.refs),
            # what a plain index cannot say
            "proved": c.id in covered,
            "owns_files": sorted(files),
            "owns_lines": sum(len(v) for v in files.values()),
            "half_proved_lines": sum(len(v) for v in (partial.get(c.id) or {}).values()),
        }
    return {
        "schema": NEEDS_SCHEMA,
        "project": project or contract.title,
        "current_version": version or contract.version,
        "versions": {version or contract.version: {
            "needs_amount": len(needs),
            "needs": needs,
        }},
    }


def to_oft(contract, *, doc_id: str = "") -> str:
    """PURE: contract -> OpenFastTrace specobject XML.

    OFT's model is `artifact-type~name~revision`; ours is an immutable id plus a per-clause
    content hash. They line up better than they look: the hash IS a revision, just not a
    counting one, so it is carried as `<version>` and the numeric revision stays 1. A team
    already running `oft trace` can then put our clauses in the same report as theirs.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<specdocument>',
             f'  <specobjects doctype="{OFT_TYPE}">']
    for c in contract.clauses:
        if not c.is_live and c.status == "withdrawn":
            continue                      # a withdrawn clause is not a requirement any more
        lines += [
            '    <specobject>',
            f'      <id>{escape(c.id)}</id>',
            '      <version>1</version>',
            f'      <status>{escape(c.status)}</status>',
            f'      <description>{escape(c.text)}</description>',
        ]
        if doc_id:
            lines.append(f'      <fragment>{escape(doc_id)}</fragment>')
        covers = [x for x in c.supersedes]
        if covers:
            lines.append('      <providescoverage>')
            for target in covers:
                lines += ['        <provcov>',
                          f'          <linksto>{OFT_TYPE}~{escape(target)}~1</linksto>',
                          '        </provcov>']
            lines.append('      </providescoverage>')
        lines.append('    </specobject>')
    lines += ['  </specobjects>', '</specdocument>', '']
    return "\n".join(lines)


def render_needs(payload: dict) -> str:
    """PURE: the bytes to write. Sorted and indented so a re-export is a no-op in git."""
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
