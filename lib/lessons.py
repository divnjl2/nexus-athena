"""
Athena lessons — a lesson is a clause born from a failure signal, and it is learned only while
its proof still passes after the pyramid changed (v3.10).

The criterion comes from the post this layer answers: a lesson is learned when it changes a
future decision or check AND the old broken task passes again after the whole pyramid was
reconfigured. The first half is the `source:` attribute on a clause; the second half is this
module — derive the lesson set from the contract (never from a separate list that rots) and
rerun exactly the specs that prove it.

Two rules keep the set honest:

  * A lesson is DERIVED. Any clause whose `source:` is a failure signal (review, audit,
    incident, ledger, mutation) is one; `design` is authored intent and is not. There is no
    lessons/ folder to maintain, so there is nothing to forget to maintain.
  * A superseded lesson is carried FORWARD. The wrong guess stays on the record with its
    source (C-3.9 of the contract layer is the canonical case); what is rerun is the proof of
    whatever replaced it, found through `resolve()`.

Freeze-line: PURE. Running the specs is `spec_runner`'s job; the CLI wires them.
"""
from __future__ import annotations

from lib.ast import CLAUSE_WITHDRAWN, Contract, Scenario

SCHEMA = "athena.lessons/1"

#: Every source that is a failure signal. A clause born from one is a lesson.
FAILURE_SOURCES = ("review", "audit", "incident", "ledger", "mutation")


def lessons(contract: Contract) -> tuple[dict, ...]:
    """PURE: the lesson set of a contract, document order (C-3.1, C-3.2).

    Withdrawn clauses are skipped: a retracted requirement is not a lesson anybody keeps. A
    superseded one is kept, resolved forward to the live clauses that carry it today.
    """
    out: list[dict] = []
    for c in contract.clauses:
        if c.source not in FAILURE_SOURCES or c.status == CLAUSE_WITHDRAWN:
            continue
        live = tuple(x.id for x in contract.resolve(c.id) if x.is_live)
        out.append({"origin": c.id, "source": c.source, "live": live, "text": c.text,
                    "superseded": bool(c.superseded_by)})
    return tuple(out)


def specs_for(contract: Contract, scenarios: tuple[Scenario, ...],
              lesson_set: tuple[dict, ...] | None = None) -> tuple[Scenario, ...]:
    """PURE: the specs bound to the LIVE lesson clauses, document order, no duplicates (C-3.3).

    A spec still pointing at the superseded wording is not part of the rerun — it proves the
    old requirement, and crediting it would be the same manufactured green the coverage
    report refuses.
    """
    lesson_set = lessons(contract) if lesson_set is None else lesson_set
    wanted = {cid for item in lesson_set for cid in item["live"]}
    return tuple(s for s in scenarios if s.requirement_key.strip() in wanted)


def report(contract: Contract, scenarios: tuple[Scenario, ...], results, *,
           skipped=()) -> dict:
    """PURE: per-lesson status out of a run — kept | forgotten | unproved | skipped
    (C-3.4, C-3.5, C-3.6).

    `results` may be `SpecResult`s or ledger rows; only the scenario id and the verdict are
    read. A spec with no verdict counts as not kept: silence is never proof. `skipped` names
    the specs the CALLER left out on purpose (a `--skip-tag` lane); a lesson whose every spec
    is there is `skipped`, which is neither proof nor silence and does not fail the report.
    """
    skipped = set(skipped)
    verdict: dict[str, bool] = {}
    for r in results:
        if isinstance(r, dict):
            verdict[r.get("scenario", "")] = bool(r.get("passed"))
        else:
            verdict[getattr(r, "scenario_id", "")] = bool(getattr(r, "passed", False))
    bound: dict[str, list[str]] = {}
    for s in scenarios:
        bound.setdefault(s.requirement_key.strip(), []).append(s.id)

    rows: list[dict] = []
    for item in lessons(contract):
        specs = [sid for cid in item["live"] for sid in bound.get(cid, [])]
        if not item["live"] or not specs:
            status = "unproved"
        elif any(sid in verdict and not verdict[sid] for sid in specs):
            status = "forgotten"                      # a red verdict, whatever else ran
        elif all(sid in skipped for sid in specs):
            status = "skipped"                        # C-3.6: left out on purpose
        elif any(sid not in verdict and sid not in skipped for sid in specs):
            status = "forgotten"                      # never ran, and nobody chose that
        else:
            status = "kept"
        rows.append({**item, "specs": specs, "status": status})

    counts = {k: sum(1 for r in rows if r["status"] == k)
              for k in ("kept", "forgotten", "unproved", "skipped")}
    return {
        "schema": SCHEMA,
        "lessons": rows,
        "counts": counts,
        "passed": counts["forgotten"] == 0 and counts["unproved"] == 0,
    }


def render(rep: dict) -> str:
    """PURE: the human view — one line per lesson, the status first."""
    lines = ["# lessons — the old failures, rerun"]
    if not rep["lessons"]:
        lines.append("  (no clause carries a failure-signal source yet)")
    for row in rep["lessons"]:
        carried = "" if row["live"] == (row["origin"],) else f" -> {', '.join(row['live']) or 'nothing live'}"
        lines.append(f"  {row['status']:9} {row['origin']}{carried}  [{row['source']}]  "
                     f"specs={', '.join(row['specs']) or '-'}")
    c = rep["counts"]
    lines.append(f"\nkept={c['kept']}  forgotten={c['forgotten']}  unproved={c['unproved']}"
                 f"  skipped={c.get('skipped', 0)}")
    lines.append(f"passed: {rep['passed']}")
    return "\n".join(lines)
