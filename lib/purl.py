"""
Athena purl — naming a codebase so a map cannot be mistaken for another one (v3.8).

The clause map is derived by running specs against code. Which code was never recorded, and
an audit showed what that costs: checking a scaffolded project from inside this repository
judged it against THIS repository's map. The fix is not a new declaration block — it is a
name, and a standard one already exists.

`purl` (package-url, now ECMA-427, and what SPDX uses) names a package or repository
independently of where anyone checked it out:

    pkg:github/divnjl2/nexus-athena@bae35c6
    pkg:pypi/requests@2.31.0
    pkg:generic/internal-service

This module implements the SUBSET this frame needs — parse, normalise, compare-ignoring-
version — deliberately as ~40 stdlib lines rather than a dependency, because `lib/` is
stdlib-only by design. `packageurl-python` is the full implementation if anything here ever
needs to grow beyond identity comparison.
"""
from __future__ import annotations

import re

_PURL = re.compile(
    r"^pkg:(?P<type>[a-zA-Z][a-zA-Z0-9.+-]*)/"
    r"(?P<rest>[^@?#]+)"
    r"(?:@(?P<version>[^?#]+))?"
    r"(?:\?(?P<qualifiers>[^#]*))?"
    r"(?:#(?P<subpath>.*))?$")


class PurlError(ValueError):
    """A string offered as a package URL is not one."""


def parse(raw: str) -> dict:
    """PURE: purl string -> {type, namespace, name, version}. Raises on anything else.

    Strict on purpose. A silently-accepted non-purl would give the map a subject nobody can
    compare, which is the same as having no subject while looking like it has one.
    """
    m = _PURL.match((raw or "").strip())
    if not m:
        raise PurlError(f"refused: not a package URL: {raw!r}")
    parts = [p for p in m.group("rest").split("/") if p]
    if not parts:
        raise PurlError(f"refused: package URL has no name: {raw!r}")
    return {
        "type": m.group("type").lower(),
        "namespace": "/".join(parts[:-1]),
        "name": parts[-1],
        "version": (m.group("version") or "").strip(),
    }


def render(parsed: dict) -> str:
    """PURE: the canonical string for a parsed purl, version included when present."""
    ns = f"{parsed['namespace']}/" if parsed.get("namespace") else ""
    ver = f"@{parsed['version']}" if parsed.get("version") else ""
    return f"pkg:{parsed['type']}/{ns}{parsed['name']}{ver}"


def identity(raw: str) -> str:
    """PURE: the purl WITHOUT its version — what "the same codebase" means.

    Version is deliberately dropped: a map derived at one commit still describes the same
    project at the next, and the per-clause digests already answer whether the code moved.
    Comparing versions here would make every commit look like a different codebase.
    """
    return render({**parse(raw), "version": ""})


def same_subject(a: str, b: str) -> bool:
    """PURE: do two purls name the same codebase? Unknown on either side is not a match.

    An absent subject is NOT treated as agreement: this returns False, and the caller decides
    whether an unstated subject is an error or simply nothing to check. Silence is not proof
    here either.
    """
    if not a or not b:
        return False
    try:
        return identity(a) == identity(b)
    except PurlError:
        return False
