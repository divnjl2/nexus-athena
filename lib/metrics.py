"""
Athena metrics — the record of runs, and the numbers read out of it (v3.11).

The operator's own success metrics for agentic work are iterations to acceptance, time per
task and regressions after done. None of them was recorded anywhere. Now every spec run
appends one line to `<feature>/.athena/runs.jsonl` (C-6.2) and `athena metrics` reads
iterations-to-green and mean duration out of it (C-6.3). A malformed line is counted as
skipped, never a crash (C-6.4).

A cycle is the runs from the first red after a green (or from the start) up to and
including the next green: red, red, green is a cycle of three.

Freeze-line: PURE. Appending the line is the CLI's job.
"""
from __future__ import annotations

import json

SCHEMA = "athena.runs/1"


def record(totals: dict, *, ts: str) -> dict:
    """PURE: one run record out of a ledger's totals."""
    return {"schema": SCHEMA, "ts": ts,
            "total": int(totals.get("total", 0)), "passed": int(totals.get("passed", 0)),
            "failed": int(totals.get("failed", 0)),
            "duration_ms": int(totals.get("duration_ms", 0))}


def parse_runs(text: str) -> tuple[list[dict], int]:
    """PURE: runs.jsonl -> (records, skipped). A line that is not a run record is skipped."""
    records: list[dict] = []
    skipped = 0
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(rec, dict) or not all(isinstance(rec.get(k), int)
                                                for k in ("passed", "failed")):
            skipped += 1
            continue
        records.append(rec)
    return records, skipped


def _green(rec: dict) -> bool:
    return rec.get("failed", 0) == 0 and rec.get("total", rec.get("passed", 0)) > 0


def iterations_to_green(records: list[dict]) -> dict:
    """PURE: cycles of runs-to-green, the open cycle if the last run is red, mean duration."""
    cycles: list[int] = []
    reds = 0
    for rec in records:
        if _green(rec):
            if reds:
                cycles.append(reds + 1)
                reds = 0
        else:
            reds += 1
    green = sum(1 for r in records if _green(r))
    durations = [int(r.get("duration_ms", 0)) for r in records]
    return {
        "schema": SCHEMA,
        "runs": len(records),
        "green_runs": green,
        "red_runs": len(records) - green,
        "cycles": cycles,
        "open_cycle": reds,
        "mean_iterations_to_green": round(sum(cycles) / len(cycles), 2) if cycles else None,
        "mean_duration_ms": round(sum(durations) / len(durations)) if durations else 0,
        "last_ts": records[-1].get("ts", "") if records else "",
    }


def render(report: dict, *, skipped: int = 0) -> str:
    lines = ["# metrics — read from the record of runs",
             f"runs={report['runs']}  green={report['green_runs']}  red={report['red_runs']}"
             f"  skipped_lines={skipped}",
             f"cycles to green: {report['cycles'] or '-'}"
             + (f"  (open: {report['open_cycle']} red so far)" if report["open_cycle"] else ""),
             f"mean iterations to green: {report['mean_iterations_to_green']}",
             f"mean duration: {report['mean_duration_ms']} ms"]
    if report.get("last_ts"):
        lines.append(f"last run: {report['last_ts']}")
    return "\n".join(lines)
