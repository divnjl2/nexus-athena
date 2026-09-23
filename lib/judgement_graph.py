"""
Athena judgement graph — a judge's steps as provenance, not as a log file (v3.9).

`judge_decisions.json` is a flat file: a verdict per pair and, until now, nothing about how
the verdict was reached. Splitting the call in two made the reasoning a first-class artifact,
and an artifact with an id belongs where the rest of this frame's provenance lives — the same
graph that already holds `kind:clause` and `kind:scenario` nodes. Then "why did the judge say
that" is a graph walk instead of a grep.

Two rules keep it honest:

  * The graph is an INDEX. A node carries the verdict and the FINGERPRINT of the reasoning;
    the text stays in the decisions artifact. Thirty thousand tokens per node would turn a
    provenance graph into a slow blob store, and `bd` on Dolt is slow enough already.
  * A judgement node is ADVISORY, like the judge itself. It is labelled `kind:judgement` and
    linked with `related`, never with `validates` — the edge that means "this proves that" is
    reserved for evidence a runner produced.

Freeze-line: PURE. It emits the commands; running them is `bd_client`'s job.
"""
from __future__ import annotations

from lib.plan2beads import EXTERNAL_KEY_PREFIX, Command

SCHEMA = "athena.judgement_graph/1"


def judgement_key(slug: str, pair_id: str) -> str:
    """PURE: the external key of one judgement node. Stable per (project, pair)."""
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:judgement:{pair_id}"


def clause_key(slug: str, clause_id: str) -> str:
    """PURE: the clause node a judgement points at — the same key plan2beads allocates."""
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:clause:{clause_id}"


def scenario_key(slug: str, spec_id: str) -> str:
    """PURE: the scenario node a judgement points at."""
    return f"{EXTERNAL_KEY_PREFIX}:{slug}:scenario:{spec_id}"


def compile_judgements(records, *, slug: str, pin: dict | None = None,
                       existing_keys: frozenset = frozenset()) -> tuple[Command, ...]:
    """PURE: judgement records -> bd commands. Idempotent against `existing_keys`.

    Each record becomes one node plus up to two `related` edges — to the clause it judged and
    to the spec it judged. Edges are emitted only when BOTH ends are already in the graph:
    a judgement about a clause this project never compiled is still worth recording, and
    inventing the missing end would be worse than an orphan node.

    `pin` is the model/prompt/temperature stamp. It rides on the node as labels, so a verdict
    can never be read without the conditions that produced it.
    """
    cmds: list[Command] = []
    stamp = pin or {}
    for rec in sorted(records, key=lambda r: r.get("pair", "")):
        pair_id = rec.get("pair", "")
        if not pair_id:
            continue
        jkey = judgement_key(slug, pair_id)
        if jkey in existing_keys:
            continue
        labels = [
            "--label", jkey,
            "--label", EXTERNAL_KEY_PREFIX,
            "--label", "kind:judgement",
            "--label", f"decision:{rec.get('decision', 'unknown')}",
        ]
        if rec.get("reasoning_sha"):
            labels += ["--label", f"reasoning:{rec['reasoning_sha']}"]
        for field in ("model", "prompt_sha", "variant"):
            if stamp.get(field):
                labels += ["--label", f"judge:{field}:{stamp[field]}"]
        body = rec.get("reason", "") or "(no reason given)"
        if rec.get("counterexample"):
            body += f"\n\ncounterexample: {rec['counterexample']}"
        body += f"\n\nreasoning: {rec.get('reasoning_chars', 0)} chars, kept in the decisions artifact"
        cmds.append(Command((
            "bd", "create",
            "--no-inherit-labels",
            "--title", f"judgement:{pair_id}",
            *labels,
            "--description", body,
        )))
        for end in (clause_key(slug, rec.get("clause", "")) if rec.get("clause") else "",
                    scenario_key(slug, rec.get("spec", "")) if rec.get("spec") else ""):
            # `related`, never `validates`: an advisory verdict does not get the edge that
            # means proof. The mutation runner earns that one; a model does not.
            if end and end in existing_keys:
                cmds.append(Command(("bd", "dep", "add", jkey, end, "--type", "related")))
    return tuple(cmds)


def summarize(records) -> dict:
    """PURE: what a run of judgements put in the graph, for the report line."""
    rows = list(records)
    by_decision: dict = {}
    for r in rows:
        by_decision[r.get("decision", "unknown")] = by_decision.get(
            r.get("decision", "unknown"), 0) + 1
    reasoned = [r for r in rows if r.get("reasoning_sha")]
    return {
        "schema": SCHEMA,
        "judgements": len(rows),
        "by_decision": dict(sorted(by_decision.items())),
        "with_reasoning": len(reasoned),
        "reasoning_chars": sum(r.get("reasoning_chars", 0) for r in reasoned),
    }
