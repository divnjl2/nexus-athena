"""v3.11 budgets and the record of runs — a latency clause with a stopwatch, and metrics
read out of every run instead of remembered.

Each test is the executable spec of one C-6.* clause in features/team-layer/contract.md.
"""
from __future__ import annotations

import json
import pathlib
import time

import athena
from lib.metrics import iterations_to_green, parse_runs, record

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(passed, failed, ms=100, ts="2026-09-23T10:00:00+00:00"):
    return record({"passed": passed, "failed": failed, "total": passed + failed,
                   "duration_ms": ms}, ts=ts)


def test_the_gate_over_this_repository_answers_within_two_seconds(capsys):
    """C-6.1 — the cheap lane is only cheap if it stays cheap; this is the stopwatch."""
    t0 = time.perf_counter()
    rc = athena.main(["gate", "--root", str(ROOT)])
    elapsed = time.perf_counter() - t0
    out = json.loads(capsys.readouterr().out.strip())
    # the budget is about the ANSWER, not its colour: a red contract is the gate's job to
    # report, and this spec must not depend on the ledger it is itself recorded in
    assert rc in (0, 1) and len(out["contracts"]) >= 2, out
    assert elapsed < 2.0, f"gate took {elapsed:.2f}s"


def test_a_spec_run_appends_one_run_record(tmp_path, monkeypatch):
    """C-6.2 — every run leaves one line: the counts, the duration, when."""
    feature = tmp_path / "f"
    assert athena.main(["init", str(feature), "--title", "Demo"]) == 0
    runs = feature / ".athena" / "runs.jsonl"
    assert not runs.exists()
    scen = feature / "scenarios.md"
    for i in (1, 2):
        rc = athena.main(["spec", "run", str(scen), "--contract", str(feature / "contract.md"),
                          "--cwd", str(tmp_path), "-o", str(feature / ".athena" / "spec_ledger.json"),
                          "--env", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1"])
        assert rc == 0
        lines = [ln for ln in runs.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == i
        rec = json.loads(lines[-1])
        assert rec["total"] == 1 and rec["passed"] == 1 and rec["failed"] == 0
        assert "duration_ms" in rec and rec["ts"]


def test_metrics_report_iterations_to_green_and_mean_duration():
    """C-6.3 — iterations to green is the number from the operator's own success metrics;
    it is read from the record, never estimated."""
    runs = [_run(1, 1, 100), _run(1, 1, 300), _run(2, 0, 200),
            _run(2, 0, 200), _run(1, 1, 400), _run(2, 0, 200)]
    rep = iterations_to_green(runs)
    assert rep["runs"] == 6 and rep["green_runs"] == 3 and rep["red_runs"] == 3
    assert rep["cycles"] == [3, 2]
    assert rep["mean_iterations_to_green"] == 2.5
    assert rep["mean_duration_ms"] == 233
    assert iterations_to_green([])["runs"] == 0
    assert iterations_to_green([_run(1, 1)])["cycles"] == [], "an open cycle is not a number yet"
    assert iterations_to_green([_run(1, 1)])["open_cycle"] == 1


def test_a_malformed_run_record_is_skipped_and_the_answer_still_comes():
    """C-6.4 — a broken line is counted as skipped, never crashes the report."""
    text = json.dumps(_run(1, 1)) + "\n{not json\n\n" + json.dumps(_run(2, 0)) + "\n" + json.dumps({"x": 1}) + "\n"
    records, skipped = parse_runs(text)
    assert len(records) == 2 and skipped == 2
    rep = iterations_to_green(records)
    assert rep["cycles"] == [2]
