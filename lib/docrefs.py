"""
Athena docrefs — a clause leaning on another DOCUMENT, and noticing when it moves (v3.8).

A requirement rarely stands alone: it was decided in an ADR, it is operated by a runbook, it
paraphrases a standard. Those references rot silently — the target gets rewritten and the
clause keeps citing a paragraph that no longer says what it said.

Doorstop solved this years ago and named it, so this module borrows both the mechanism and
the vocabulary rather than inventing a third: a link carries the **fingerprint** of its
target at the moment it was reviewed, and a link whose target has changed since is a
**suspect link**. That is exactly what `pins:` already does for clause->spec inside this
frame; all that is new is pointing it at arbitrary documents.

    ```
    - **C-9.22** — WHEN a spec is run under coverage THE SYSTEM SHALL ...
      - see: docs/adr/0007-branch-evidence.md@3f9a1c02b7e3d5a8
      - see: https://coverage.readthedocs.io/en/latest/branch.html
    ```

A ref with no fingerprint is legal and reported as `unpinned` — the same way an unpinned spec
is legal. A ref this tool cannot read (an http URL, a vault note behind an API) is reported as
`external`: it is not a broken link, and pretending to have checked it would be worse than
saying nothing.

Freeze-line: PURE and stdlib-only. Reading the targets is the CLI's job.
"""
from __future__ import annotations

import hashlib
import re

#: `path@fingerprint` — the fingerprint is optional and always the LAST @-segment, so a
#: path that itself contains '@' (a scoped npm package, an email-ish filename) still parses.
_PINNED = re.compile(r"^(?P<target>.+?)@(?P<pin>[0-9a-f]{8,64})\s*$")

#: Anything this tool cannot open by path. Reported, never guessed at.
_EXTERNAL = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)

SCHEMA = "athena.docrefs/1"


def fingerprint(text: str) -> str:
    """PURE: the fingerprint of a referenced document. Same sha16 the clause pins use."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def parse_ref(raw: str) -> dict:
    """PURE: `- see:` value -> {target, pin, external}.

    Whitespace-tolerant and never raises: a malformed reference must show up in the report,
    not stop the parse of the contract that carries it.
    """
    raw = (raw or "").strip()
    m = _PINNED.match(raw)
    target = (m.group("target") if m else raw).strip()
    return {"target": target,
            "pin": m.group("pin") if m else "",
            "external": bool(_EXTERNAL.match(target))}


def render_ref(ref: dict) -> str:
    """PURE: the inverse of `parse_ref`, so re-pinning is a rewrite and not an append."""
    return f"{ref['target']}@{ref['pin']}" if ref.get("pin") else ref["target"]


def check(contract, sources: dict) -> dict:
    """PURE: resolve every clause reference against the documents that were read.

    `sources` is {target: text or None} — None meaning "this path does not exist". Reading
    them is the caller's job, which is what keeps this checkable without a filesystem.

    Four outcomes, kept apart because they call for different actions:

      ok        the target is there and its fingerprint still matches
      suspect   the target changed since the reference was reviewed  (Doorstop's word)
      broken    the reference names a document that is not there
      unpinned  a reference with no fingerprint — legal, and nothing can go stale about it
      external  a URL this tool will not pretend to have checked
    """
    ok, suspect, broken, unpinned, external = [], [], [], [], []
    for c in contract.clauses:
        for raw in c.refs:
            ref = parse_ref(raw)
            row = {"clause": c.id, "target": ref["target"], "pin": ref["pin"]}
            if ref["external"]:
                external.append(row)
                continue
            text = sources.get(ref["target"])
            if text is None:
                broken.append(row)
                continue
            if not ref["pin"]:
                unpinned.append(row)
                continue
            now = fingerprint(text)
            (ok if now == ref["pin"] else suspect).append({**row, "now": now})
    return {
        "schema": SCHEMA,
        "refs": len(ok) + len(suspect) + len(broken) + len(unpinned) + len(external),
        "ok": ok, "suspect": suspect, "broken": broken,
        "unpinned": unpinned, "external": external,
        # A suspect link is not a failure of the CODE, it is a claim that needs re-reading;
        # a broken one is a plain mistake. Both block, for different reasons, and the report
        # keeps them apart so the fix is obvious.
        "passed": not suspect and not broken,
    }


def targets(contract) -> tuple[str, ...]:
    """PURE: every local document this contract references, deduplicated in clause order."""
    seen: dict[str, None] = {}
    for c in contract.clauses:
        for raw in c.refs:
            ref = parse_ref(raw)
            if not ref["external"]:
                seen.setdefault(ref["target"], None)
    return tuple(seen)


def repin(contract, sources: dict) -> dict:
    """PURE: {clause id: {old raw ref: new raw ref}} for references whose target moved.

    Re-pinning is REVIEWING: the fingerprint says "I read this version and the clause still
    holds". So this returns the edits and lets the caller decide to write them, rather than
    quietly agreeing with whatever the document says today.
    """
    out: dict = {}
    for c in contract.clauses:
        for raw in c.refs:
            ref = parse_ref(raw)
            text = sources.get(ref["target"])
            if ref["external"] or text is None:
                continue
            now = fingerprint(text)
            if ref["pin"] != now:
                out.setdefault(c.id, {})[raw] = render_ref({**ref, "pin": now})
    return out


def apply_repin(contract_text: str, edits: dict) -> tuple[str, int]:
    """PURE: rewrite `- see:` lines in contract.md, in place. Returns (text, edits applied).

    Line-oriented and idempotent, like `pin_scenarios`: it replaces the value of the see
    bullet it finds, never appends a second one, so running it twice changes nothing the
    second time. Edits are matched on the RAW ref text, so an identical reference under two
    clauses is repinned under both.
    """
    wanted: dict = {}
    for per_clause in edits.values():
        wanted.update(per_clause)
    if not wanted:
        return contract_text, 0

    out, applied = [], 0
    for line in contract_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(("- see:", "- ref:")):
            head, _, value = stripped.partition(":")
            raw = value.strip()
            if raw in wanted:
                indent = line[:len(line) - len(line.lstrip())]
                out.append(f"{indent}- {head.lstrip('- ').strip()}: {wanted[raw]}")
                applied += 1
                continue
        out.append(line)
    return "\n".join(out) + ("\n" if contract_text.endswith("\n") else ""), applied
