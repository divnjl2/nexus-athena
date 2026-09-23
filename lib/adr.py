"""
Athena adr — decision records the clauses can rest on, kept in the repository (v3.11).

The pyramid is core, then decisions and requirements. The CRISP design step wrote its
Design Decisions to an ignored scratch folder, so decisions did not outlive the session,
and the `see:` mechanism had nothing to cite but CORE.md. A record here is a short MADR:

    # ADR-0007: Branch evidence per clause
    - Status: accepted
    - Date: 2026-09-23
    ## Context ... ## Decision ... ## Consequences ...

`lint_adr` requires the six parts (C-2.1); `unlinked` reports a record no clause of any
contract cites (C-2.2). A citation is `see: ../../docs/adr/0007-....md@<fingerprint>`, and
when the record changes the citing clauses go suspect through `lib.docrefs`.

Freeze-line: PURE, stdlib-only. Reading files is the CLI's job.
"""
from __future__ import annotations

import posixpath
import re

from lib.docrefs import parse_ref

SCHEMA = "athena.adr/1"
STATUSES = ("proposed", "accepted", "superseded", "deprecated", "rejected")
REQUIRED_SECTIONS = ("context", "decision", "consequences")

_TITLE = re.compile(r"^#\s+(ADR-\d+)\s*:\s*(.+?)\s*$", re.MULTILINE)
_FIELD = re.compile(r"^-\s*(status|date|deciders|cited by)\s*:\s*(.+?)\s*$",
                    re.MULTILINE | re.IGNORECASE)
_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_adr(text: str) -> dict:
    """PURE: a record -> {id, title, status, date, deciders, sections}. Never raises: a
    malformed record is a lint report, not a crash."""
    m = _TITLE.search(text or "")
    fields = {k.lower(): v for k, v in _FIELD.findall(text or "")}
    sections: dict[str, str] = {}
    parts = _SECTION.split(text or "")
    # parts = [preamble, name1, body1, name2, body2, ...]
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i].strip().lower()] = parts[i + 1].strip()
    return {
        "id": m.group(1) if m else "",
        "title": m.group(2) if m else "",
        "status": fields.get("status", "").lower(),
        "date": fields.get("date", ""),
        "deciders": fields.get("deciders", ""),
        "sections": sections,
    }


def lint_adr(text: str, name: str = "") -> tuple[str, ...]:
    """PURE: the six parts, by name (C-2.1)."""
    rec = parse_adr(text)
    issues: list[str] = []
    if not rec["id"]:
        issues.append("missing id: the title must read like '# ADR-0007: <title>'")
    if not rec["status"]:
        issues.append("missing Status")
    elif rec["status"] not in STATUSES:
        issues.append(f"unknown Status {rec['status']!r} (one of {', '.join(STATUSES)})")
    if not rec["date"]:
        issues.append("missing Date")
    elif not _DATE.match(rec["date"]):
        issues.append(f"Date {rec['date']!r} is not YYYY-MM-DD")
    for sec in REQUIRED_SECTIONS:
        if not rec["sections"].get(sec):
            issues.append(f"missing section: {sec.capitalize()}")
    prefix = f"{name}: " if name else ""
    return tuple(prefix + i for i in issues)


def cited_targets(contract_path: str, contract) -> set[str]:
    """PURE: every local document a contract cites, as a repository-relative posix path."""
    base = posixpath.dirname(contract_path.replace("\\", "/"))
    out: set[str] = set()
    for c in contract.clauses:
        for raw in c.refs:
            ref = parse_ref(raw)
            if ref["external"]:
                continue
            out.add(posixpath.normpath(posixpath.join(base, ref["target"])))
    return out


def unlinked(adr_paths, cited: set[str]) -> tuple[str, ...]:
    """PURE: records no clause cites (C-2.2), in the order given."""
    norm_cited = {posixpath.normpath(p.replace("\\", "/")) for p in cited}
    return tuple(p for p in adr_paths
                 if posixpath.normpath(str(p).replace("\\", "/")) not in norm_cited)
