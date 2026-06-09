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
    run: callable(list[str]) -> stdout. Queries bd for already-existing athena
    labels for this plan slug, so the pure compiler can skip re-creating them.
    """
    out = run(["bd", "list", "--label", f"{EXTERNAL_KEY_PREFIX}:{slug}:", "--json"])
    issues = json.loads(out or "[]")
    keys: set[str] = set()
    for it in issues:
        for lbl in it.get("labels", []):
            if lbl.startswith(f"{EXTERNAL_KEY_PREFIX}:{slug}:"):
                keys.add(lbl)
    return frozenset(keys)


def execute(result: CompileResult, *, run) -> None:
    """Run the compiled commands in order. Effectful — not covered by golden tests."""
    for cmd in result.commands:
        run(list(cmd.argv))
