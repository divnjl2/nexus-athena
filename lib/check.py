"""
Athena check — the whole loop as one answer (v3.5).

Everything the contract layer can tell you already existed as eight commands in a sequence
nobody remembers: lint, coverage, spec run, todo, drift, contract_bound, map_fresh, mutate.
A tool that requires its user to hold the order in their head is a library, not a product.

`run_check` composes them into ONE verdict with ONE exit code, and — this is the part that
matters — it says WHICH leg failed, because the two legs answer different questions:

    specs -> code    is every requirement proved, by a spec that is bound, pinned, green
                     and rooted in the clause it claims?   (lint, coverage, ledger, drift)
    code -> specs    is there code no requirement demands, and do those specs actually
                     prove anything?                        (map freshness, mutation)

Freeze-line: this module is PURE. It takes the reports the other modules produce and folds
them into a verdict; every effectful step (running specs, shelling to coverage) stays in the
CLI. That is what makes the verdict itself golden-testable.
"""
from __future__ import annotations

#: Ordered so the first failure is the most upstream cause, not the loudest symptom.
LEGS = ("contract", "specs_to_code", "code_to_specs")


def _step(name: str, ok: bool, detail: dict, *, leg: str, blocking: bool = True) -> dict:
    return {"step": name, "leg": leg, "ok": bool(ok), "blocking": blocking, "detail": detail}


def build(*, lint_issues=(), critique_warnings=(), coverage=None, ledger_totals=None,
          todo=None, drift=None, gates=None, mutation=None, judge=None,
          strict_wording: bool = False, missing_inputs=(), allow_partial: bool = False) -> dict:
    """PURE: fold every report into one verdict.

    `None` means "not run" — and an audit caught this file breaking its own rule: a step that
    did not run simply vanished from `steps`, `by_leg` computed `all()` over an EMPTY list,
    and a run with a mis-typed --map printed `verdict: PASS` having checked nothing. Silence
    read as proof, which is the exact failure this whole layer exists to prevent.

    So a leg that produced no evidence is now INCOMPLETE, not green, and `missing_inputs`
    (a path that was named but absent) is a hard failure — naming a file you do not have is
    a mistake, not a choice. `allow_partial` is the explicit opt-out for a fast lane that
    knowingly skips the reverse leg.
    """
    steps: list[dict] = []

    steps.append(_step("contract.lint", not lint_issues,
                       {"issues": list(lint_issues)}, leg="contract"))
    steps.append(_step("contract.wording", not critique_warnings,
                       {"warnings": list(critique_warnings)},
                       leg="contract", blocking=strict_wording))

    if coverage is not None:
        steps.append(_step("coverage", coverage.get("passed", False), {
            "live": coverage.get("live_clauses"),
            "uncovered": coverage.get("uncovered", []),
            "orphan_specs": coverage.get("orphan_specs", []),
            "redirected": len(coverage.get("redirected_specs", [])),
            "draft_uncovered": coverage.get("draft_uncovered", []),
        }, leg="specs_to_code"))

    if ledger_totals is not None:
        steps.append(_step("spec.run", ledger_totals.get("failed", 1) == 0, {
            "passed": ledger_totals.get("passed"), "total": ledger_totals.get("total"),
            "failed": ledger_totals.get("failed"),
        }, leg="specs_to_code"))

    if todo is not None:
        steps.append(_step("todo", todo.get("remaining", 1) == 0, {
            "counts": todo.get("counts", {}), "remaining": todo.get("remaining"),
            "backlog": todo.get("backlog"),
        }, leg="specs_to_code"))

    if drift is not None:
        steps.append(_step("drift", drift.get("in_sync", False), {
            k: drift.get("counts", {}).get(k) for k in
            ("spec_drift", "stale_proof", "missing_spec", "extra_spec", "unpinned")
        }, leg="specs_to_code"))

    for name, result in sorted((gates or {}).items()):
        steps.append(_step(f"seam.{name}", result.get("passed", False),
                           {"issues": result.get("issues", [])},
                           leg="code_to_specs" if name == "map_fresh" else "specs_to_code"))

    if mutation is not None:
        # A surviving mutant means a spec is green for code that no longer does what its
        # clause demands. Advisory by default: mutation is a sweep, and a partial sweep
        # must not fail a build. `--deep --strict` is what turns it into a gate.
        # Every outcome the runner can produce is shown. The first cut whitelisted three
        # keys and silently dropped `undetermined` — a run of 20 mutants where NONE was
        # decided rendered as a clean "ok mutation" row.
        steps.append(_step("mutation", mutation.get("survived", 0) == 0, {
            "mutants": mutation.get("mutants"), "killed": mutation.get("killed"),
            "survived": mutation.get("survived"),
            "undetermined": mutation.get("undetermined"),
            "unowned": mutation.get("unowned"),
            "note": mutation.get("note", ""),
            "survivors": [f"{s['path']}:{s['line']}" for s in mutation.get("survivors", [])][:10],
        }, leg="code_to_specs", blocking=bool(mutation.get("blocking"))))

    if judge is not None:
        # NEVER blocking. The judge is a local model; its verdicts are advisory until a
        # scored corpus says otherwise, and that door is `is_gate_eligible`, not this file.
        steps.append(_step("judge", judge.get("passes", False), {
            "recall": judge.get("recall"), "false_reject": judge.get("false_reject"),
            "gate_eligible": judge.get("passes", False),
        }, leg="code_to_specs", blocking=False))

    for path in sorted(missing_inputs):
        # A named-but-absent input used to make its whole step disappear. It is now its own
        # blocking step, so a typo in --map can never be mistaken for "nothing to check".
        steps.append(_step("input.missing", False, {"path": path},
                           leg="contract", blocking=True))

    failed = [s for s in steps if not s["ok"] and s["blocking"]]
    advisory = [s for s in steps if not s["ok"] and not s["blocking"]]

    by_leg: dict = {}
    for leg in LEGS:
        rows = [s for s in steps if s["leg"] == leg and s["blocking"]]
        by_leg[leg] = (all(s["ok"] for s in rows) if rows else
                       (True if allow_partial else "incomplete"))
    incomplete = [leg for leg, state in by_leg.items() if state == "incomplete"]

    return {
        "schema": "athena.check/2",
        "passed": not failed and not incomplete,
        "legs": by_leg,
        "incomplete": incomplete,
        "failed": [s["step"] for s in failed],
        "advisory": [s["step"] for s in advisory],
        "first_cause": failed[0]["step"] if failed else
                       (f"{incomplete[0]}: no evidence" if incomplete else ""),
        "steps": steps,
    }


def render(report: dict) -> str:
    """PURE: the human view — one line per step, the failing leg named, nothing else."""
    mark = {True: "ok  ", False: "FAIL"}
    lines = []
    for leg in LEGS:
        rows = [s for s in report["steps"] if s["leg"] == leg]
        leg_state = report["legs"].get(leg, True)
        if not rows:
            if leg_state == "incomplete":
                lines.append(f"[????] {leg}   nothing ran — no evidence either way")
            continue
        state = {True: "ok", False: "FAIL", "incomplete": "????"}[leg_state]
        lines.append(f"[{state}] {leg}")
        for s in rows:
            tag = mark[s["ok"]] if s["blocking"] else ("ok  " if s["ok"] else "warn")
            detail = ", ".join(f"{k}={v}" for k, v in s["detail"].items()
                               if v not in (None, [], {}, 0))
            lines.append(f"   {tag} {s['step']:22} {detail[:96]}")
    lines.append("")
    verdict = "PASS" if report["passed"] else (
        "INCOMPLETE" if report.get("incomplete") and not report["failed"] else "FAIL")
    lines.append(f"verdict: {verdict}"
                 + (f"  first cause: {report['first_cause']}" if report["first_cause"] else "")
                 + (f"  advisory: {', '.join(report['advisory'])}" if report["advisory"] else ""))
    return "\n".join(lines)
