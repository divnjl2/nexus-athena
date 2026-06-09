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


def _athena_label_refs(argv: tuple[str, ...]) -> list[str]:
    return [a for i, a in enumerate(argv)
            if i > 0 and argv[i - 1] == "--label" and a.startswith(f"{EXTERNAL_KEY_PREFIX}:")]


def execute(result: CompileResult, *, run) -> None:
    """
    Run the compiled commands, resolving external labels -> real bd issue IDs at runtime.

    The compiler is pure (no runtime IDs), so it emits label-based references in
    `--parent` / `bd dep add <X>` / `--blocked-by`. Real bd resolves those by ISSUE ID,
    not label (verified: `bd show <label>` 404s) — so the effectful layer captures each
    `bd create` id (via --json) and substitutes. Seeded from the existing graph so
    relationships to already-present issues resolve on replan too.
    """
    label_to_id: dict[str, str] = {}
    try:
        for it in json.loads(run(["bd", "list", "--label", EXTERNAL_KEY_PREFIX, "--json"]) or "[]"):
            iid = it.get("id")
            for lbl in it.get("labels", []):
                if iid and lbl.startswith(f"{EXTERNAL_KEY_PREFIX}:"):
                    label_to_id[lbl] = iid
    except Exception:
        pass

    def resolve(tok: str) -> str:
        return label_to_id.get(tok, tok)

    for cmd in result.commands:
        argv: list[str] = []
        i, src = 0, list(cmd.argv)
        while i < len(src):
            if src[i] in ("--parent", "--blocked-by") and i + 1 < len(src):
                argv += [src[i], resolve(src[i + 1])]; i += 2
            else:
                argv.append(src[i]); i += 1
        if argv[:3] == ["bd", "dep", "add"] and len(argv) > 3:   # positional target after `add`
            argv[3] = resolve(argv[3])

        is_create = argv[:2] == ["bd", "create"]
        out = run(argv + ["--json"] if is_create else argv)
        if is_create:
            try:
                new_id = json.loads(out).get("id", "")
            except Exception:
                new_id = ""
            if new_id:
                for lbl in _athena_label_refs(cmd.argv):
                    label_to_id[lbl] = new_id
