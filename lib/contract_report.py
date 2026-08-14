"""
Athena contract_report — the three cheap questions a contract makes answerable (v3.3).

  1. coverage()  "which requirements have no executable spec?"
  2. todo()      "what is still left to implement?"      (live clauses whose specs are red/unrun)
  3. drift()     "where did requirement, spec and code diverge?"

All three are PURE, deterministic, stdlib-only and LINEAR in the number of clauses — that
is the whole point of paying for stable clause ids up front. No LLM reads the code to
answer them; the answer falls out of (contract x scenarios x ledger).

The one judgement call, made deliberately:

  A spec that still points at a SUPERSEDED clause does NOT count as coverage of that
  clause's successors. It was written against the old wording, so crediting it would
  manufacture a green light nobody earned. It is reported separately as `redirected` —
  the reference still RESOLVES (that is what supersede chains buy), but the successor
  needs its own proof.
"""
from __future__ import annotations

from lib.ast import CLAUSE_DRAFT, CLAUSE_WITHDRAWN, Contract, Scenario

_STATUS_ORDER = ("unspecified", "red", "unrun", "stale", "done")


def _bind(contract: Contract, scenarios: tuple[Scenario, ...]) -> dict:
    """clause id -> the scenarios that name it DIRECTLY (document order)."""
    out: dict[str, list[Scenario]] = {c.id: [] for c in contract.clauses}
    for s in scenarios:
        key = s.requirement_key.strip()
        if key in out:
            out[key].append(s)
    return out


def _ledger_index(ledger: dict | None) -> dict:
    return {r.get("scenario", ""): r for r in (ledger or {}).get("results", [])}


def coverage(contract: Contract, scenarios: tuple[Scenario, ...]) -> dict:
    """Q1 — which clauses are proved by at least one executable spec, and which are not."""
    bound = _bind(contract, scenarios)
    known = set(bound)

    uncovered, covered, draft_uncovered = [], [], []
    for c in contract.clauses:
        specs = [s.id for s in bound[c.id]]
        if c.status == CLAUSE_DRAFT:
            (covered if specs else draft_uncovered).append(c.id)
            continue
        if not c.is_live:
            continue                       # superseded/withdrawn: not owed a proof
        (covered if specs else uncovered).append(c.id)

    orphan, redirected = [], []
    for s in scenarios:
        key = s.requirement_key.strip()
        if key not in known:
            orphan.append({"scenario": s.id, "clause": key, "reason": "unknown_clause"})
            continue
        cl = contract.by_id(key)
        if cl is None:                     # defensive: index and clause list disagree
            continue
        if cl.status == CLAUSE_WITHDRAWN:
            orphan.append({"scenario": s.id, "clause": key, "reason": "withdrawn_clause"})
        elif cl.superseded_by:
            redirected.append({"scenario": s.id, "clause": key,
                               "now": [x.id for x in contract.resolve(key)]})

    live = [c.id for c in contract.live()]
    return {
        "live_clauses": len(live),
        "covered": covered,
        "uncovered": uncovered,
        "draft_uncovered": draft_uncovered,
        "orphan_specs": orphan,
        "redirected_specs": redirected,
        "coverage_rate": round(len([c for c in covered if c in live]) / len(live), 4) if live else 1.0,
        "passed": not uncovered and not orphan,
    }


def todo(contract: Contract, scenarios: tuple[Scenario, ...],
         ledger: dict | None = None) -> dict:
    """Q2 — what is left to build. Every live clause lands in exactly one bucket:

      unspecified — no executable spec exists yet   (write the spec first)
      red         — specs exist and at least one fails (implement / fix)
      unrun       — specs exist, the ledger has no verdict (run them)
      done        — every bound spec is green
    """
    bound = _bind(contract, scenarios)
    idx = _ledger_index(ledger)

    buckets: dict[str, list] = {k: [] for k in _STATUS_ORDER}
    # draft clauses are NOT live (nothing is owed a proof yet) but they are still work the
    # answer must name — a requirement written down and then invisible is the rot this
    # whole layer exists to prevent.
    buckets["draft"] = [{"clause": c.id, "text": c.text} for c in contract.clauses
                        if c.status == CLAUSE_DRAFT]
    for c in contract.live():
        specs = bound[c.id]
        if not specs:
            buckets["unspecified"].append({"clause": c.id, "text": c.text})
            continue
        verdicts = [idx.get(s.id) for s in specs]
        failing = [s.id for s, v in zip(specs, verdicts) if v is not None and not v.get("passed")]
        if failing:
            buckets["red"].append({
                "clause": c.id, "text": c.text, "failing_specs": failing,
                "run_cmds": [s.run_cmd for s in specs if s.id in failing],
            })
        elif any(v is None for v in verdicts):
            buckets["unrun"].append({"clause": c.id,
                                     "specs": [s.id for s, v in zip(specs, verdicts) if v is None]})
        else:
            # green, but possibly green against an OLDER wording of the clause. Without this
            # bucket `todo` answers "nothing left" while `drift` says "not in sync" — the
            # report would be lying in exactly the case the contract exists to catch.
            stale = [s.id for s, v in zip(specs, verdicts)
                     if (s.clause_version and s.clause_version != c.version)
                     or (v.get("clause_version") and v["clause_version"] != c.version)]
            if stale:
                buckets["stale"].append({"clause": c.id, "text": c.text, "stale_specs": stale})
            else:
                buckets["done"].append({"clause": c.id})

    return {
        **buckets,
        "counts": {k: len(v) for k, v in buckets.items()},
        # `remaining` counts LIVE work only; drafts are backlog, tracked separately so a
        # gate on "remaining == 0" does not block on requirements nobody promised yet.
        # A stale clause IS remaining work: its proof no longer matches its wording.
        "remaining": (len(buckets["unspecified"]) + len(buckets["red"])
                      + len(buckets["unrun"]) + len(buckets["stale"])),
        "backlog": len(buckets["draft"]),
        "ledger_ts": (ledger or {}).get("ts", ""),
    }


def drift(contract: Contract, scenarios: tuple[Scenario, ...],
          ledger: dict | None = None) -> dict:
    """Q3 — requirement <-> spec <-> code divergence, per clause.

      spec_drift   the clause text changed after the spec was pinned to it: the spec
                   still passes, but it is proving the OLD requirement
      stale_proof  the ledger's green was earned under a clause version that is no
                   longer current — the proof predates the requirement
      missing_spec a live clause nothing verifies      ("нет пропущенных")
      extra_spec   a spec pointing at an unknown or withdrawn clause ("нет лишних")
      unpinned     a spec with no pin at all — drift CANNOT be detected for it
    """
    bound = _bind(contract, scenarios)
    idx = _ledger_index(ledger)
    known = set(bound)

    spec_drift, unpinned, stale_proof = [], [], []
    for s in scenarios:
        key = s.requirement_key.strip()
        cl = contract.by_id(key)
        if cl is None:
            continue                                   # counted as extra_spec below
        if not s.clause_version:
            unpinned.append({"scenario": s.id, "clause": key})
        elif s.clause_version != cl.version:
            spec_drift.append({"scenario": s.id, "clause": key,
                               "pinned": s.clause_version, "current": cl.version})
        rec = idx.get(s.id)
        if rec and rec.get("passed") and rec.get("clause_version") \
                and rec["clause_version"] != cl.version:
            stale_proof.append({"scenario": s.id, "clause": key,
                                "proved_version": rec["clause_version"],
                                "current": cl.version})

    cov = coverage(contract, scenarios)
    missing_spec = cov["uncovered"]
    extra_spec = cov["orphan_specs"]

    counts = {"spec_drift": len(spec_drift), "stale_proof": len(stale_proof),
              "missing_spec": len(missing_spec), "extra_spec": len(extra_spec),
              "unpinned": len(unpinned)}
    return {
        "contract_version": contract.version,
        "ledger_contract_version": (ledger or {}).get("contract_version", ""),
        "spec_drift": spec_drift,
        "stale_proof": stale_proof,
        "missing_spec": missing_spec,
        "extra_spec": extra_spec,
        "unpinned": unpinned,
        "counts": counts,
        # `unpinned` is NOT a divergence, it is missing instrumentation — it must not
        # flip in_sync to false, or a repo that never pinned looks permanently broken.
        "in_sync": not (spec_drift or stale_proof or missing_spec or extra_spec),
    }


def render(report: dict, *, title: str = "") -> str:
    """Compact human view of any of the three reports (the CLI emits JSON by default)."""
    lines: list[str] = ([f"# {title}"] if title else [])
    counts = report.get("counts")
    if isinstance(counts, dict):
        lines.append("  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if "coverage_rate" in report:            # coverage has no counts dict of its own
        lines.append(f"live={report.get('live_clauses')}  "
                     f"covered={len(report.get('covered', ()))}  "
                     f"uncovered={len(report.get('uncovered', ()))}  "
                     f"rate={report['coverage_rate']}")
    for key in ("uncovered", "unspecified", "red", "unrun", "stale", "draft", "spec_drift",
                "stale_proof", "missing_spec", "extra_spec", "orphan_specs",
                "redirected_specs", "draft_uncovered", "unpinned"):
        items = report.get(key)
        if not items:
            continue
        lines.append(f"\n{key} ({len(items)}):")
        for it in items:
            if isinstance(it, dict):
                head = it.get("clause") or it.get("scenario") or ""
                rest = ", ".join(f"{k}={v}" for k, v in sorted(it.items())
                                 if k not in ("clause", "text") and v)
                lines.append(f"  - {head}  {rest}".rstrip())
            else:
                lines.append(f"  - {it}")
    for flag in ("passed", "in_sync"):
        if flag in report:
            lines.append(f"\n{flag}: {report[flag]}")
    return "\n".join(lines)
