"""v3.16 the foundry — oracles of the second kind (C-9) and the sandbox (C-10).

Each test is the executable spec of one clause in features/foundry-layer/contract.md.
"""
from __future__ import annotations

import json


def test_an_import_clause_renders_an_import_linter_contract_and_its_run_command():
    """C-9.1 — "shall not import" becomes a forbidden contract, "layers" a layers contract,
    one .importlinter with both, and the command that checks it."""
    from lib.oracles import importlinter_config
    clauses = [{"id": "C-9.1", "text": "THE lib.oracles package SHALL NOT import lib.daemon."},
               {"id": "C-3.7", "text": "THE lib package SHALL NOT import athena."},   # review: any id, the shape is in the text
               {"id": "C-9.2", "text": "THE SYSTEM SHALL keep the layers athena, lib.refinery, lib.dispatch in that order."},
               {"id": "C-9.3", "text": "WHEN x THE SYSTEM SHALL do y."}]
    ini, cmd = importlinter_config(clauses, root_package="lib")
    assert "[importlinter]" in ini and "root_package = lib" in ini
    assert "[importlinter:contract:C-9.1]" in ini and "type = forbidden" in ini
    assert "name = C-9.1" in ini   # review: lint-imports refuses a contract without a name
    assert "source_modules = lib.oracles" in ini and "forbidden_modules = lib.daemon" in ini
    assert "[importlinter:contract:C-9.2]" in ini and "type = layers" in ini
    assert "athena" in ini and "lib.refinery" in ini and "lib.dispatch" in ini
    assert "C-9.3" not in ini
    assert "[importlinter:contract:C-3.7]" in ini and "forbidden_modules = athena" in ini
    assert cmd.startswith("lint-imports") and "--config" in cmd


def test_a_time_budget_clause_renders_a_benchmark_command_against_a_stored_baseline():
    """C-9.2 — "within N% of its baseline" becomes a compare-fail benchmark command on the
    clause's mark; a clause without a budget renders nothing."""
    from lib.oracles import benchmark_command
    c = {"id": "C-9.2", "text": "WHEN the merge check runs THE SYSTEM SHALL complete within 20% of its baseline."}
    cmd = benchmark_command(c, baseline="0001_base")
    assert cmd == "python -m pytest -m bench_C_9_2 --benchmark-compare=0001_base --benchmark-compare-fail=median:20% --benchmark-min-rounds=5 -q"
    assert benchmark_command({"id": "C-1.1", "text": "WHEN x THE SYSTEM SHALL do y."}, baseline="b") == ""


def test_a_command_that_would_update_a_snapshot_baseline_is_refused():
    """C-9.3 — the snapshot-update flags of the golden tools are refused with the reason; a
    plain test command passes."""
    from lib.oracles import forbidden_command
    assert forbidden_command(["python", "-m", "pytest", "--snapshot-update", "-q"]) == "updates the snapshot baseline: --snapshot-update"
    assert forbidden_command(["python", "-m", "pytest", "--force-regen"]) == "updates the snapshot baseline: --force-regen"
    assert forbidden_command(["python", "-m", "pytest", "--benchmark-save=x"]) == "updates the benchmark baseline: --benchmark-save"
    assert forbidden_command(["python", "-m", "pytest", "tests/t.py", "-q"]) is None
    assert forbidden_command([]) is None


def test_the_sandbox_wraps_a_command_with_the_worktree_writable_and_the_lane_ports_open():
    """C-10.1 — the config allows writes in the worktree only, reads on the toolchain, no
    network but the loopback lane ports; the argv runs the command through the runtime."""
    from lib.sandbox import sandbox_argv, sandbox_config
    cfg = sandbox_config(worktree="D:/w/T1", allow_read=["C:/Python311", "D:/repo"], lane_ports=[8417, 8419])
    assert cfg["filesystem"]["allowWrite"] == ["D:/w/T1"]
    assert set(cfg["filesystem"]["allowRead"]) == {"C:/Python311", "D:/repo", "D:/w/T1"}
    assert cfg["network"]["allowedDomains"] == [] and cfg["network"]["allowLocalPorts"] == [8417, 8419]
    json.dumps(cfg)
    argv = sandbox_argv(["python", "-m", "pytest", "-q"], config_path="D:/w/T1/.athena/sandbox.json")
    assert argv[:2] == ["srt", "--settings"] and argv[2] == "D:/w/T1/.athena/sandbox.json"
    assert argv[3] == "--" and argv[4:] == ["python", "-m", "pytest", "-q"]


def test_without_a_sandbox_the_frame_says_so_and_runs_unsandboxed_only_when_allowed():
    """C-10.2 — flag required + unavailable: refuse; flag on + unavailable: run unsandboxed
    and say so; flag off: run plain; available: sandboxed."""
    from lib.sandbox import sandbox_decision
    assert sandbox_decision(available=False, flag="required") == (False, False, "sandbox required but unavailable")
    assert sandbox_decision(available=False, flag="on") == (True, False, "sandbox unavailable, running unsandboxed")
    assert sandbox_decision(available=True, flag="on") == (True, True, "sandboxed")
    assert sandbox_decision(available=True, flag="required") == (True, True, "sandboxed")
    assert sandbox_decision(available=False, flag="off") == (True, False, "sandbox off")
    assert sandbox_decision(available=True, flag="off") == (True, False, "sandbox off")
