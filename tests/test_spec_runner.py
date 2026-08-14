"""v3.3 executable-spec runner — ordering, timeout handling, ledger schema, degradation.

Each test is the executable spec of one C-3.* clause in features/contract-layer/contract.md.
The effectful boundary (`subprocess`, `perf_counter`) is injected, so the suite never shells
out and the assertions are deterministic.
"""
from __future__ import annotations

import json
import os
import subprocess

from lib.ast import Scenario
from lib.contract import parse as parse_contract
from lib.spec_runner import (SpecResult, default_jobs, load_ledger, make_ledger, run_specs,
                             select, totals, write_ledger)

CONTRACT = parse_contract("""# Contract: Demo

- **C-1.1** — WHEN it starts THE SYSTEM SHALL do the first thing.
- **C-1.2** — WHEN it starts THE SYSTEM SHALL do the second thing.
""")


def _scen(n, clause, cmd="true", pin=""):
    return Scenario(id=f"S{n}", requirement_key=clause, gwt_text="Given/When/Then",
                    run_cmd=cmd, clause_version=pin)


def test_results_keep_document_order_regardless_of_completion_order():
    """C-3.1 — two runs of the same suite must diff cleanly, so order is by document."""
    import time

    scenarios = tuple(_scen(i, "C-1.1", cmd=f"cmd{i}") for i in range(6))

    def slow_first(cmd, *, cwd, timeout):
        # earlier specs finish LAST — completion order is the reverse of document order
        time.sleep(0.02 * (6 - int(cmd[-1])))
        return 0, ""

    res = run_specs(scenarios, jobs=6, executor=slow_first)
    assert [r.scenario_id for r in res] == [f"S{i}" for i in range(6)]
    assert all(r.passed for r in res)


def test_a_hung_spec_is_red_and_never_aborts_the_run(monkeypatch):
    """C-3.2 — a timeout makes ONE spec red; the ledger stays complete."""
    def boom(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="sleep 999", timeout=1)

    monkeypatch.setattr(subprocess, "run", boom)
    res = run_specs((_scen(1, "C-1.1", cmd="sleep 999"), _scen(2, "C-1.2")), jobs=2, timeout=1)
    assert [(r.scenario_id, r.passed, r.exit_code) for r in res] == \
           [("S1", False, 124), ("S2", False, 124)]
    assert "TIMEOUT" in res[0].output_tail


def test_missing_command_is_red_with_the_os_error(monkeypatch):
    """C-3.3 — an unrunnable run_cmd is a red spec, not a crashed runner."""
    def boom(*a, **kw):
        raise OSError("no such tool")

    monkeypatch.setattr(subprocess, "run", boom)
    res = run_specs((_scen(1, "C-1.1", cmd="nope"),))
    assert res[0].exit_code == 127 and not res[0].passed
    assert "no such tool" in res[0].output_tail


def test_a_dangerous_or_unparseable_run_cmd_is_refused_and_recorded_red(monkeypatch):
    """C-3.13 — a run_cmd is an LLM-hop output: refuse it, and say why in the ledger."""
    calls = []
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **kw: calls.append((a, kw)) or _Ok())
    res = run_specs((_scen(1, "C-1.1", cmd="pytest -q; rm -rf /"),
                     _scen(2, "C-1.1", cmd='pytest -q "unterminated'),
                     _scen(3, "C-1.1", cmd="   ")), jobs=1)
    assert [(r.scenario_id, r.passed, r.exit_code) for r in res] == [
        ("S1", False, 126), ("S2", False, 126), ("S3", False, 126)]
    assert "shell metacharacter" in res[0].output_tail
    assert "unparseable" in res[1].output_tail and "empty" in res[2].output_tail
    assert calls == [], "a refused command must never reach subprocess"


def test_an_accepted_run_cmd_is_tokenized_and_never_shelled(monkeypatch):
    """C-3.14 — the accepted path runs argv-style with shell=False."""
    calls = []
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **kw: calls.append((a, kw)) or _Ok())
    res = run_specs((_scen(1, "C-1.2", cmd="pytest tests/test_x.py::test_y -q"),), jobs=1)
    assert res[0].passed
    assert calls[0][0][0] == ["pytest", "tests/test_x.py::test_y", "-q"]
    assert calls[0][1]["shell"] is False


class _Ok:
    returncode = 0
    stdout = ""
    stderr = ""


def test_ledger_carries_versions_and_totals(tmp_path):
    """C-3.4 — the ledger pins contract + scenario versions and rolls up pass/fail."""
    results = (
        SpecResult("S1", "C-1.1", True, 0, 10, clause_version="aaa", run_cmd="true"),
        SpecResult("S2", "C-1.2", False, 1, 20, clause_version="bbb", run_cmd="false",
                   output_tail="boom"),
    )
    led = make_ledger(results, contract=CONTRACT, scenario_version="scv1", ts="2026-08-14T00:00:00+00:00")
    assert led["schema"] == "athena.spec_ledger/1"
    assert led["contract_version"] == CONTRACT.version and led["scenario_version"] == "scv1"
    assert led["totals"] == {"total": 2, "passed": 1, "failed": 1, "duration_ms": 30}
    assert led["results"][1]["output_tail"] == "boom"

    p = write_ledger(led, tmp_path / ".athena" / "spec_ledger.json")
    assert json.loads(p.read_text(encoding="utf-8")) == led
    assert load_ledger(p) == led


def test_ledger_is_deterministic_for_the_same_results():
    """C-3.5 — same results + same injected ts -> byte-identical JSON (golden-able)."""
    results = (SpecResult("S1", "C-1.1", True, 0, 10),)
    a = make_ledger(results, contract=CONTRACT, ts="T")
    b = make_ledger(results, contract=CONTRACT, ts="T")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_absent_or_corrupt_ledger_degrades_to_unrun(tmp_path):
    """C-3.6 — no verdict is 'unrun', never a crash: reports must still answer."""
    assert load_ledger(tmp_path / "nope.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_ledger(bad) == {}
    listy = tmp_path / "list.json"
    listy.write_text("[1,2]", encoding="utf-8")
    assert load_ledger(listy) == {}


def test_the_worker_pool_is_sized_from_the_machines_cores(monkeypatch):
    """C-3.15 — specs are processes, so an 8-worker default on an 18-core box is pure waste."""
    monkeypatch.setattr(os, "cpu_count", lambda: 36)
    assert default_jobs() == 36
    monkeypatch.setattr(os, "cpu_count", lambda: None)      # unknowable -> safe floor
    assert default_jobs() == 4
    monkeypatch.setattr(os, "cpu_count", lambda: 256)       # capped, never unbounded
    assert default_jobs() == 64


def test_pinned_env_is_merged_over_the_inherited_environment(monkeypatch):
    """C-3.16 — a spec runs in the developer's real env PLUS what the caller pins."""
    seen = {}

    def fake_run(argv, **kw):
        seen.update(kw)
        return _Ok()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(os, "environ", {"PATH": "/usr/bin", "HOME": "/home/x"})
    run_specs((_scen(1, "C-1.1", cmd="pytest -q"),),
              env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    assert seen["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert seen["env"]["PATH"] == "/usr/bin"        # merged, never replacing
    assert seen["env"]["HOME"] == "/home/x"


def test_specs_can_be_included_or_excluded_by_clause_tag():
    """C-3.12 — one slow spec must not hold the fast lane hostage."""
    contract = parse_contract("""# Contract: Lanes

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer fast.
- **C-1.2** — WHEN asked THE SYSTEM SHALL answer via a real backend.
  - tags: slow, integration
""")
    scenarios = (_scen(1, "C-1.1"), _scen(2, "C-1.2"))
    fast = select(scenarios, contract=contract, skip_tags=("slow",))
    assert [s.id for s in fast] == ["S1"]
    slow = select(scenarios, contract=contract, only_tags=("integration",))
    assert [s.id for s in slow] == ["S2"]
    # without a contract the tag filters are inert, never silently dropping specs
    assert select(scenarios, skip_tags=("slow",)) == scenarios


def test_select_filters_by_clause_or_spec_prefix():
    """C-3.7 — running one area's specs is the fast inner loop."""
    scenarios = (_scen(1, "C-1.1"), _scen(2, "C-2.1"), _scen(3, "C-2.9"))
    assert [s.id for s in select(scenarios, clause_prefix="C-2")] == ["S2", "S3"]
    assert [s.id for s in select(scenarios, scenario_prefix="S1")] == ["S1"]
    assert select(scenarios) == scenarios


def test_empty_spec_set_is_an_empty_run_not_an_error():
    """C-3.8 — filtering everything out yields an empty, still-valid ledger."""
    assert run_specs(()) == ()
    assert totals(()) == {"total": 0, "passed": 0, "failed": 0, "duration_ms": 0}
