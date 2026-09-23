"""
Athena markers — code pointing back at a clause, and the map confirming it (v3.8).

The clause map answers "which lines does this requirement reach", derived from execution.
The reverse annotation — a comment in the source naming the requirement it implements — is
the oldest trick in requirements tracing, and there is no reason to invent a third notation
for it. Two live grammars exist:

    OpenFastTrace   `// [impl->dsn~validate-authentication-request~1]`
    StrictDoc       `# @relation(REQ-1, scope=function)`

This module reads StrictDoc's, for two reasons: it takes arbitrary ids (ours are `C-9.22`,
not `type~name~revision`), and its scopes — file, class, function, range_start/range_end,
line — are exactly the granularity the clause map already computes.

What is OURS is the check. An annotation is a claim, and everywhere else in this frame a
claim is worth what its evidence is worth, so a marker is verified three ways: the clause
exists, the clause is live, and THE MAP AGREES that this requirement actually reaches the
lines the marker claims. A comment naming a clause over code no spec of that clause ever
executes is precisely the decorative traceability this layer exists to refuse.

Freeze-line: PURE and stdlib-only (`ast` is stdlib). Reading files is the caller's job.
"""
from __future__ import annotations

import ast
import re

SCHEMA = "athena.markers/1"

#: StrictDoc's marker. Ids are comma-separated; `scope=` is optional and defaults to the
#: narrowest useful claim rather than the widest, because a marker that quietly means "this
#: whole file" is a claim nobody intended to make.
_MARKER = re.compile(
    r"@relation\(\s*(?P<ids>[^),]+(?:\s*,\s*[^),=]+)*)\s*"
    r"(?:,\s*scope\s*=\s*(?P<scope>[a-z_]+)\s*)?\)", re.IGNORECASE)

SCOPES = ("line", "function", "class", "file", "range_start", "range_end")
DEFAULT_SCOPE = "line"


#: A fenced block or an inline code span is a MENTION of the notation, not a use of it.
_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"`[^`]*`")


def _demote_mentions(lines: list) -> list:
    """PURE: blank out code spans and fenced blocks, keeping the line count intact.

    The same distinction `critique` already draws between using a word and quoting one. This
    module documents its own notation, and the first scan of this repository dutifully
    reported the EXAMPLES in these docstrings as three broken markers. Whatever is shown
    inside backticks is being talked about, not asserted.
    """
    out, fenced = [], False
    for raw in lines:
        if _FENCE.match(raw):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else _CODE_SPAN.sub("", raw))
    return out


def scan(text: str, *, path: str = "") -> tuple[dict, ...]:
    """PURE: every `@relation(...)` in a source text, in document order.

    Line numbers are 1-based, matching the clause map. One marker naming three clauses
    yields three rows: downstream everything reasons about (clause, line) pairs. Markers
    shown inside backticks or a fenced block are mentions and are skipped.
    """
    out: list[dict] = []
    for lineno, raw in enumerate(_demote_mentions(text.splitlines()), start=1):
        for m in _MARKER.finditer(raw):
            scope = (m.group("scope") or DEFAULT_SCOPE).lower()
            for cid in [x.strip() for x in m.group("ids").split(",") if x.strip()]:
                out.append({"clause": cid, "scope": scope, "line": lineno, "path": path})
    return tuple(out)


def _python_spans(text: str) -> tuple[list, list]:
    """PURE: (function spans, class spans) as (start, end, name) — 1-based, inclusive.

    Empty when the text does not parse: a marker in a file this module cannot read is
    reported as unresolved rather than silently credited with the whole file.
    """
    funcs: list = []
    classes: list = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return funcs, classes
    for node in ast.walk(tree):
        end = getattr(node, "end_lineno", None) or getattr(node, "lineno", 0)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append((node.lineno, end, node.name))
        elif isinstance(node, ast.ClassDef):
            classes.append((node.lineno, end, node.name))
    return funcs, classes


def claimed_lines(marker: dict, text: str, *, partner: dict | None = None) -> tuple[int, ...]:
    """PURE: the lines a marker claims, resolved against the file it sits in.

    line          the next non-blank line after the comment — the statement it labels
    function      the innermost def enclosing the marker (Python)
    class         the innermost class enclosing it (Python)
    file          every line
    range_start   from this marker to its matching `range_end` (`partner`)
    range_end     nothing on its own; the pair is reported from its start

    An unresolvable scope returns () and the caller reports it: a marker whose claim cannot
    be worked out must not be quietly treated as covering something.
    """
    lines = text.splitlines()
    n = len(lines)
    scope, at = marker["scope"], marker["line"]

    if scope == "file":
        return tuple(range(1, n + 1))
    if scope == "line":
        for i in range(at, n):                      # 0-based index at == the NEXT line
            if lines[i].strip():
                return (i + 1,)
        return ()
    if scope == "range_start":
        if not partner or partner["line"] <= at:
            return ()
        return tuple(range(at + 1, partner["line"]))
    if scope == "range_end":
        return ()
    if scope in ("function", "class"):
        funcs, classes = _python_spans(text)
        spans = funcs if scope == "function" else classes
        enclosing = [s for s in spans if s[0] <= at <= s[1]]
        if not enclosing:
            return ()
        start, end, _ = min(enclosing, key=lambda s: s[1] - s[0])   # innermost
        return tuple(range(start, end + 1))
    return ()


def pair_ranges(markers: tuple[dict, ...]) -> dict:
    """PURE: {id(range_start marker): range_end marker} matched per clause, in order.

    Nesting is not supported and is not silently guessed at: starts and ends of one clause
    are zipped in document order, and an unmatched start resolves to no lines at all.
    """
    out: dict = {}
    by_clause: dict = {}
    for m in markers:
        if m["scope"] in ("range_start", "range_end"):
            by_clause.setdefault((m["path"], m["clause"]), []).append(m)
    for group in by_clause.values():
        starts = [m for m in group if m["scope"] == "range_start"]
        ends = [m for m in group if m["scope"] == "range_end"]
        for s, e in zip(starts, ends):
            out[id(s)] = e
    return out


def check(markers: tuple[dict, ...], contract, clause_map: dict, sources: dict) -> dict:
    """PURE: verify every marker against the contract AND the derived map.

    Five outcomes, because they call for different fixes:

      ok           the clause is live and the map says it reaches the claimed lines
      unknown      the marker names a clause this contract does not define
      retired      the clause is superseded or withdrawn — the marker outlived its rule
      unowned      the map says this requirement does NOT reach the lines claimed. The
                   annotation is decorative: no spec of that clause executes this code.
      unresolved   the scope could not be worked out (a `function` scope in a file that does
                   not parse, an unmatched range) — reported, never credited
    """
    owned = (clause_map or {}).get("clauses") or {}
    pairs = pair_ranges(markers)
    ok, unknown, retired, unowned, unresolved = [], [], [], [], []

    for m in markers:
        row = {"clause": m["clause"], "path": m["path"], "line": m["line"],
               "scope": m["scope"]}
        if m["scope"] == "range_end":
            continue
        clause = contract.by_id(m["clause"]) if contract is not None else None
        if clause is None:
            unknown.append(row)
            continue
        if not clause.is_live:
            retired.append({**row, "status": clause.status})
            continue
        text = sources.get(m["path"])
        if text is None:
            unresolved.append({**row, "why": "source not read"})
            continue
        claim = claimed_lines(m, text, partner=pairs.get(id(m)))
        if not claim:
            unresolved.append({**row, "why": f"cannot resolve scope={m['scope']}"})
            continue
        reaches = set((owned.get(m["clause"]) or {}).get(_norm(m["path"]), ()))
        hit = sorted(set(claim) & reaches)
        if hit:
            ok.append({**row, "lines": len(claim), "confirmed": len(hit)})
        else:
            unowned.append({**row, "lines": len(claim),
                            "why": "no spec of this clause executes the lines it claims"})

    return {
        "schema": SCHEMA,
        "markers": len(ok) + len(unknown) + len(retired) + len(unowned) + len(unresolved),
        "ok": ok, "unknown": unknown, "retired": retired,
        "unowned": unowned, "unresolved": unresolved,
        "passed": not (unknown or retired or unowned),
    }


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip().lstrip("./")
