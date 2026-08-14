"""
Athena contract — the formal requirement language (v3.3): `contract.md` -> tuple[Clause].

WHY a contract instead of "the requirements section of spec.md":

  A spec.md is prose with an implicit numbering. Renumber it and every `verifies: R4.2`
  written last month silently points at a different requirement — the reference rots
  without a single test going red. A CONTRACT fixes the identity: a clause id is
  allocated once, is never reused, and is never edited in place. A requirement that
  changes is SUPERSEDED by one or more successors, so the old reference keeps
  resolving — forward, to whatever replaced it.

  That one rule is what makes the three cheap questions answerable by a linear scan:
    * which clauses have no executable spec?          -> contract_report.coverage()
    * what is still left to implement?                -> contract_report.todo()  (red/unrun specs)
    * where did requirement, spec and code diverge?   -> contract_report.drift()  (per-clause pins)

Freeze-line: this module is PURE + deterministic + stdlib-only (same discipline as the
compiler and the seams). No I/O, no clock, no LLM. `parse` raises on a malformed FILE;
`lint` reports a semantically broken CONTRACT — the two failure classes stay separate so
a gate can tell "you typed it wrong" from "your requirements are inconsistent".

Format (line-oriented, diff-friendly, human-writable):

    # Contract: Classic Snake Game

    ## C-1 — Initial state

    - **C-1.1** — WHEN a new game starts THE SYSTEM SHALL place the snake at its
      starting cells.
    - **C-1.2** *(draft)* — WHEN a new game starts THE SYSTEM SHALL seed the RNG.
    - **C-1.3** *(superseded-by C-1.4 C-1.5)* — WHEN a new game starts THE SYSTEM
      SHALL set the score to zero.
    - **C-1.4** *(supersedes C-1.3)* — WHEN a new game starts THE SYSTEM SHALL set
      the score to zero.
      - tags: scoring
    - **C-2.9** *(withdrawn)* — THE SYSTEM SHALL play a sound on death.

Attributes may be given inline in the `*( ... )*` marker (semicolon-separated) or as
indented sub-bullets (`- status:`, `- supersedes:`, `- superseded-by:`, `- tags:`).
An indented line that is neither is a CONTINUATION of the clause text — wrapped prose
must never be silently truncated (regression class already hit once in scenario_parser).
"""
from __future__ import annotations

import re

from lib.ast import (CLAUSE_ACTIVE, CLAUSE_DRAFT, CLAUSE_SUPERSEDED, CLAUSE_WITHDRAWN,
                     Clause, Contract, ParseError)
from lib.versioning import hash_text


class ContractParseError(ParseError):
    """The contract FILE is malformed (unparseable / ambiguous identity)."""


# A clause id: 1-4 uppercase letters, optional dash, then a dotted number path.
# `C-3.2`, `R1.1`, `FR-14`, `NFR-2.1.3` all qualify — so an existing Athena spec.md
# (whose EARS criteria are already `R<n>.<m>`) imports WITHOUT renumbering anything.
CLAUSE_ID = r"[A-Z]{1,4}-?\d+(?:\.\d+)*"

_TITLE_RE = re.compile(r"^#\s+(?:Contract:\s*)?(.+?)\s*$")
_HEADING_RE = re.compile(rf"^#{{2,4}}\s+(?:({CLAUSE_ID})\s*)?(?:[—\-]\s*)?(.*)$")
_CLAUSE_RE = re.compile(
    rf"^-\s*\*\*({CLAUSE_ID})\*\*\s*(?:\*\(([^)]*)\)\*)?\s*(?:[—\-]\s+)?(.*)$"
)
_ATTR_RE = re.compile(
    r"^\s+-\s*(status|supersedes|superseded[-_]by|tags|note)\s*:\s*(.*)$", re.IGNORECASE
)
_ID_LIST_SPLIT = re.compile(r"[,\s]+")

_STATUSES = {CLAUSE_ACTIVE, CLAUSE_DRAFT, CLAUSE_SUPERSEDED, CLAUSE_WITHDRAWN}


def _ids(raw: str) -> tuple[str, ...]:
    return tuple(x for x in _ID_LIST_SPLIT.split(raw.strip()) if x)


def _norm_text(text: str) -> str:
    """Normalize a clause's normative text before hashing: collapse whitespace only.

    Re-wrapping a paragraph must NOT look like a requirement change (it would fire a
    false drift on every clause the author re-flowed), but a word change must.
    """
    return " ".join(text.split())


def clause_version(text: str) -> str:
    """Per-clause pin. Deliberately NOT the whole-file hash: editing clause 7 must not
    invalidate the pins of clauses 1..6 — that granularity is what makes drift useful."""
    return hash_text(_norm_text(text))


def contract_version(clauses: tuple[Clause, ...]) -> str:
    """Structural pin of the registry: ids + per-clause versions + statuses."""
    return hash_text("\n".join(f"{c.id}:{c.version}:{c.status}" for c in clauses))


def _apply_marker(cur: dict, marker: str) -> None:
    """Parse an inline `*(...)*` marker: semicolon-separated `<keyword> [ids...]`."""
    for part in marker.split(";"):
        part = part.strip()
        if not part:
            continue
        head, _, rest = part.partition(" ")
        key = head.strip().lower()
        if key in _STATUSES:
            cur["status"] = key
        elif key in ("superseded-by", "superseded_by"):
            cur["superseded_by"] += _ids(rest)
        elif key == "supersedes":
            cur["supersedes"] += _ids(rest)
        elif key == "tags":
            cur["tags"] += _ids(rest)
        else:                       # unknown token -> a free-form note, never silent
            cur["notes"] += (part,)


def _apply_attr(cur: dict, key: str, value: str) -> None:
    key = key.lower().replace("_", "-")
    value = value.strip()
    if key == "status":
        # `status: superseded-by C-1.4` is the same statement as the inline marker
        head, _, rest = value.partition(" ")
        if head.lower() in ("superseded-by", "superseded_by"):
            cur["superseded_by"] += _ids(rest)
        elif value.lower() in _STATUSES:
            cur["status"] = value.lower()
        else:
            cur["notes"] += (f"status: {value}",)
    elif key == "superseded-by":
        cur["superseded_by"] += _ids(value)
    elif key == "supersedes":
        cur["supersedes"] += _ids(value)
    elif key == "tags":
        cur["tags"] += _ids(value)
    else:
        cur["notes"] += (value,)


def _finish(cur: dict) -> Clause:
    text = _norm_text(cur["text"])
    status = cur["status"]
    superseded_by = tuple(sorted(set(cur["superseded_by"])))
    # A clause with successors IS superseded — the marker is redundant, the edge is truth.
    if superseded_by and status == CLAUSE_ACTIVE:
        status = CLAUSE_SUPERSEDED
    cid = cur["id"]
    return Clause(
        id=cid,
        text=text,
        version=clause_version(text),
        status=status,
        superseded_by=superseded_by,
        supersedes=tuple(sorted(set(cur["supersedes"]))),
        parent=cid.rsplit(".", 1)[0] if "." in cid else "",
        group=cur["group"],
        tags=tuple(sorted(set(cur["tags"]))),
        source_line=cur["line"],
    )


def parse(text: str) -> Contract:
    """contract.md -> Contract. Deterministic, document order preserved."""
    title = ""
    group = ""
    clauses: list[Clause] = []
    cur: dict | None = None

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            clauses.append(_finish(cur))
            cur = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not title:
            mt = _TITLE_RE.match(raw)
            if mt and not raw.startswith("##"):
                title = mt.group(1).strip()
                continue

        mh = _HEADING_RE.match(raw) if raw.startswith("##") else None
        if mh:
            flush()
            gid, gtitle = (mh.group(1) or "").strip(), (mh.group(2) or "").strip()
            group = f"{gid} {gtitle}".strip() if gid else gtitle
            continue

        mc = _CLAUSE_RE.match(raw)
        if mc:
            flush()
            cur = {"id": mc.group(1), "text": mc.group(3) or "", "status": CLAUSE_ACTIVE,
                   "superseded_by": (), "supersedes": (), "tags": (), "notes": (),
                   "group": group, "line": lineno}
            if mc.group(2):
                _apply_marker(cur, mc.group(2))
            continue

        if cur is None:
            continue

        ma = _ATTR_RE.match(raw)
        if ma:
            _apply_attr(cur, ma.group(1), ma.group(2))
            continue

        if raw.startswith("- ") or not raw.strip():
            # a non-clause top-level bullet or a blank line ends the clause block
            flush()
            continue

        if raw[:1] in (" ", "\t"):
            # wrapped continuation of the normative text — append, never drop
            cur["text"] = f"{cur['text']} {raw.strip()}"

    flush()

    if not clauses:
        raise ContractParseError(
            f"no clauses parsed (expected bullets like '- **{CLAUSE_ID}** — WHEN ... SHALL ...')"
        )

    seen: set[str] = set()
    for c in clauses:
        if c.id in seen:
            # identity is the whole point — a duplicate id makes every reference ambiguous
            raise ContractParseError(f"duplicate clause id {c.id} (line {c.source_line})")
        seen.add(c.id)

    clauses = _symmetrize(clauses)
    return Contract(title=title or "Contract", clauses=tuple(clauses),
                    version=contract_version(tuple(clauses)))


def _symmetrize(clauses: list[Clause]) -> list[Clause]:
    """Make the supersede relation symmetric: declaring it on either end is enough.

    Authors write `*(supersedes C-1.3)*` on the NEW clause (natural — that is the one
    they are typing) but readers of the OLD clause need the forward pointer to follow.
    Both directions are derived so the graph never depends on which end was annotated.
    """
    fwd: dict[str, set[str]] = {c.id: set(c.superseded_by) for c in clauses}
    back: dict[str, set[str]] = {c.id: set(c.supersedes) for c in clauses}
    known = set(fwd)
    for cid, preds in list(back.items()):
        for p in preds:
            if p in known:
                fwd[p].add(cid)
    for cid, succs in list(fwd.items()):
        for s in succs:
            if s in known:
                back[s].add(cid)

    out: list[Clause] = []
    import dataclasses
    for c in clauses:
        sb = tuple(sorted(fwd[c.id]))
        sp = tuple(sorted(back[c.id]))
        status = c.status
        if sb and status == CLAUSE_ACTIVE:
            status = CLAUSE_SUPERSEDED
        out.append(dataclasses.replace(c, superseded_by=sb, supersedes=sp, status=status))
    return out


def lint(contract: Contract) -> tuple[str, ...]:
    """Semantic checks on a parsed contract. Empty tuple = the contract is consistent."""
    issues: list[str] = []
    ids = {c.id for c in contract.clauses}

    for c in contract.clauses:
        if not c.text.strip():
            issues.append(f"{c.id}: empty clause text")
        if c.status not in _STATUSES:
            issues.append(f"{c.id}: unknown status {c.status!r}")
        for ref in c.superseded_by:
            if ref not in ids:
                issues.append(f"{c.id}: superseded-by unknown clause {ref}")
        for ref in c.supersedes:
            if ref not in ids:
                issues.append(f"{c.id}: supersedes unknown clause {ref}")
        if c.id in c.superseded_by or c.id in c.supersedes:
            issues.append(f"{c.id}: supersedes itself")
        if c.status == CLAUSE_SUPERSEDED and not c.superseded_by:
            issues.append(f"{c.id}: marked superseded but names no successor")
        if c.status == CLAUSE_WITHDRAWN and c.superseded_by:
            issues.append(f"{c.id}: withdrawn AND superseded — a clause is replaced or "
                          f"dropped, never both")

    for cid in _supersede_cycles(contract):
        issues.append(f"{cid}: supersede cycle — the chain never reaches a current clause")

    return tuple(issues)


def _supersede_cycles(contract: Contract) -> tuple[str, ...]:
    """Ids that sit on a supersede cycle (would make resolve() non-terminating without
    its visited-set guard, and means no current clause exists for that reference)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {c.id: WHITE for c in contract.clauses}
    bad: set[str] = set()

    def visit(cid: str) -> bool:
        color[cid] = GRAY
        cl = contract.by_id(cid)
        for nxt in (cl.superseded_by if cl else ()):
            if nxt not in color:
                continue
            if color[nxt] == GRAY or (color[nxt] == WHITE and visit(nxt)):
                bad.add(cid)
                color[cid] = BLACK
                return True
        color[cid] = BLACK
        return False

    for c in contract.clauses:
        if color[c.id] == WHITE:
            visit(c.id)
    return tuple(sorted(bad))


# --- migration: an existing spec.md is already 90% a contract --------------------

def import_from_spec(spec_text: str, *, section: str = "EARS Acceptance Criteria",
                     title: str = "") -> Contract:
    """Lift the EARS criteria of an existing Athena spec.md into a Contract.

    IDs are preserved VERBATIM (`R1.1` stays `R1.1`) — renaming them to `C-*` would
    break every `verifies:` already written in scenarios.md, which is exactly the rot
    the contract exists to prevent. New clauses get new ids; old ones keep theirs.
    """
    body = _slice_section(spec_text, section)
    if title:
        body = f"# Contract: {title}\n\n{body}"
    return parse(body)


def _slice_section(text: str, section: str) -> str:
    """Return the lines under `## <section>` up to the next `## ` heading (whole text
    if the section is absent — callers may hand us an already-sliced file)."""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("## ") and section.lower() in ln.lower():
            start = i + 1
            break
    if start is None:
        return text
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end])


def render(contract: Contract) -> str:
    """Contract -> canonical contract.md text (round-trips through parse())."""
    out = [f"# Contract: {contract.title}", ""]
    group = None
    for c in contract.clauses:
        if c.group != group:
            group = c.group
            if group:
                out += [f"## {group}", ""]
        marks: list[str] = []
        if c.status in (CLAUSE_DRAFT, CLAUSE_WITHDRAWN):
            marks.append(c.status)
        if c.superseded_by:
            marks.append("superseded-by " + " ".join(c.superseded_by))
        if c.supersedes:
            marks.append("supersedes " + " ".join(c.supersedes))
        marker = f" *({'; '.join(marks)})*" if marks else ""
        out.append(f"- **{c.id}**{marker} — {c.text}")
        if c.tags:
            out.append(f"  - tags: {', '.join(c.tags)}")
    out.append("")
    return "\n".join(out)


# --- pinning: bind an executable spec to the clause version it was written against ---

_VERIFIES_LINE = re.compile(r"^(\s*-\s*\*\*verifies:\*\*\s*`?)(.+?)(`?\s*)$", re.IGNORECASE)
_PINS_LINE = re.compile(r"^\s*-\s*\*\*pins:\*\*", re.IGNORECASE)


def pin_scenarios(scenarios_text: str, contract: Contract) -> tuple[str, dict]:
    """Insert/refresh `- **pins:** <clause_version>` under every `verifies:` line.

    The pin is what turns "the requirement changed" into a MECHANICAL signal instead of
    a memory exercise: `contract_report.drift()` compares the pin against the clause's
    live version. Pure: returns the new text plus a stats dict, writes nothing.
    """
    lines = scenarios_text.splitlines()
    out: list[str] = []
    pinned = updated = unknown = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = _VERIFIES_LINE.match(line)
        i += 1
        if not m:
            continue
        ref = m.group(2).strip()
        cl = contract.by_id(ref)
        if cl is None:
            unknown += 1
            continue
        indent = line[: len(line) - len(line.lstrip())]
        pin_line = f"{indent}- **pins:** {cl.version}"
        if i < len(lines) and _PINS_LINE.match(lines[i]):
            if lines[i].strip() != pin_line.strip():
                updated += 1
            i += 1                       # replace the stale pin
        else:
            pinned += 1
        out.append(pin_line)
    text = "\n".join(out)
    if scenarios_text.endswith("\n"):
        text += "\n"
    return text, {"pinned": pinned, "updated": updated, "unknown_refs": unknown}
