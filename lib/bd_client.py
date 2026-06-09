"""
Athena bd_client — the ONLY place with subprocess / I/O.

The pure compiler (plan2beads) never touches the world; idempotency is injected
via `existing_keys`. This module fetches those keys from a real `bd` and executes
the compiled commands. `run` is injected (real subprocess in prod, fake in tests)
so nothing here needs a live bd to be unit-tested.
"""
from __future__ import annotations

import json

from lib.plan2beads import CompileResult, EXTERNAL_KEY_PREFIX


def fetch_existing_keys(slug: str, *, run) -> frozenset[str]:
    """
    run: callable(list[str]) -> stdout. Returns the external keys
    (athena:<slug>:epicN / athena:<slug>:T#.#) already present in the graph, so the
    pure compiler can skip re-creating them (idempotent upsert).

    We query by the bare, EXACT `athena` label — every Athena epic and issue carries
    it — and filter to this slug in Python. We deliberately do NOT rely on `bd` doing
    a prefix match on `athena:<slug>:`, whose semantics are CLI-version-dependent and
    would silently disable idempotency if it were exact-match.
    """
    out = run(["bd", "list", "--label", EXTERNAL_KEY_PREFIX, "--json"])
    issues = json.loads(out or "[]")
    prefix = f"{EXTERNAL_KEY_PREFIX}:{slug}:"
    keys: set[str] = set()
    for it in issues:
        for lbl in it.get("labels", []):
            if lbl.startswith(prefix):
                keys.add(lbl)
    return frozenset(keys)


def execute(result: CompileResult, *, run) -> None:
    """Run the compiled commands in order. Effectful — not covered by golden tests."""
    for cmd in result.commands:
        run(list(cmd.argv))
