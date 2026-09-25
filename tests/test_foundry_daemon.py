"""v3.16 the foundry — the daemon (C-3) and lanes that admit by capacity (C-4).

Each test is the executable spec of one clause in features/foundry-layer/contract.md.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

READY = [{"id": "athena:demo:T1.2", "priority": 2, "created_at": "2026-09-25T10:00:00Z"},
         {"id": "athena:demo:T1.1", "priority": 1, "created_at": "2026-09-25T10:00:01Z"},
         {"id": "athena:demo:T2.1", "priority": 1, "created_at": "2026-09-25T09:00:00Z"},
         {"id": "athena:other:T9.9", "priority": 0, "created_at": "2026-09-25T08:00:00Z"}]


def test_a_tick_takes_the_highest_priority_ready_task_no_lane_runs_and_names_its_worktree():
    """C-3.1 — priority first, then age, never a task already running, never another slug;
    the worktree name carries task id and packet digest, stable across restarts."""
    from lib.daemon import next_task, worktree_name
    assert next_task(READY, slug="demo", running=set()) == "T2.1"
    assert next_task(READY, slug="demo", running={"T2.1"}) == "T1.1"
    assert next_task(READY, slug="demo", running={"T2.1", "T1.1", "T1.2"}) == ""
    assert next_task([], slug="demo", running=set()) == ""
    name = worktree_name("T1.1", "a" * 40)
    assert name == worktree_name("T1.1", "a" * 40) and name.startswith("T1.1-") and len(name) <= 24
    assert worktree_name("T1.1", "b" * 40) != name and "/" not in name and "\\" not in name


def test_a_stale_heartbeat_releases_the_claim_and_counts_a_crashed_attempt():
    """C-3.2 — claims older than the lease are stale; the release plan names the pid to kill
    and the attempt counter to bump; fresh claims are left alone."""
    from lib.daemon import stale_claims
    claims = {"T1.1": {"heartbeat": "2026-09-25T10:00:00Z", "pid": 111, "attempts": 1},
              "T1.2": {"heartbeat": "2026-09-25T10:09:30Z", "pid": 222, "attempts": 0}}
    stale = stale_claims(claims, now="2026-09-25T10:10:00Z", lease_s=300)
    assert stale == [{"task": "T1.1", "pid": 111, "attempts": 2, "reason": "heartbeat 600s old, lease 300s"}]
    assert stale_claims(claims, now="2026-09-25T10:04:00Z", lease_s=300) == []


def test_on_restart_a_green_worktree_is_offered_not_run_again():
    """C-3.3 — a worktree whose last record for its task is green goes to the refinery; a red
    or unrecorded one is run; the record is matched on task and workspace."""
    from lib.daemon import resume_plan
    records = [{"task": "T1.1", "workspace": "w/T1.1-aaaa", "green": False},
               {"task": "T1.1", "workspace": "w/T1.1-aaaa", "green": True},
               {"task": "T1.2", "workspace": "w/T1.2-bbbb", "green": True},
               {"task": "T1.2", "workspace": "w/T1.2-bbbb", "green": False},
               {"task": "T2.1", "workspace": "w/elsewhere", "green": True}]
    plan = resume_plan({"T1.1": "w/T1.1-aaaa", "T1.2": "w/T1.2-bbbb", "T2.1": "w/T2.1-cccc"}, records)
    assert plan == {"offer": ["T1.1"], "run": ["T1.2", "T2.1"]}


def test_every_daemon_action_is_one_ledger_line_and_actions_per_task_are_capped():
    """C-3.4 — the line carries tick, task, action, reason and time; the cap counts this task's
    actions in the last hour and refuses the next one past it."""
    from lib.daemon import action_allowed, ledger_line
    line = ledger_line(tick=7, task="T1.1", action="dispatch", reason="ready, lane 9b admitted", ts="2026-09-25T10:00:00Z")
    assert line == {"tick": 7, "task": "T1.1", "action": "dispatch", "reason": "ready, lane 9b admitted", "ts": "2026-09-25T10:00:00Z"}
    rows = [ledger_line(tick=i, task="T1.1", action="nudge", reason="r", ts=f"2026-09-25T10:{i:02d}:00Z") for i in range(6)]
    assert action_allowed(rows, task="T1.1", now="2026-09-25T10:30:00Z", cap_per_hour=6) is False
    assert action_allowed(rows, task="T1.1", now="2026-09-25T11:30:00Z", cap_per_hour=6) is True
    assert action_allowed(rows, task="T1.2", now="2026-09-25T10:30:00Z", cap_per_hour=6) is True


def test_the_daemon_command_prints_its_tick_without_running_when_dry():
    """C-3.5 — `athena daemon --dry-run --ready-json <file>` reports the pick and the lane
    decision as text and exits 0, or says nothing is ready and exits 1; nothing is dispatched."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        ready = pathlib.Path(td) / "ready.json"
        ready.write_text(json.dumps(READY), encoding="utf-8")
        argv = [sys.executable, str(ROOT / "athena.py"), "daemon", "features/refinery-layer/contract.md",
                "--front", "features/refinery-layer/plan.md", "--slug", "demo", "--ready-json", str(ready),
                "--executor", "pi-9b", "--dry-run", "--text"]
        p = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert p.returncode == 0, p.stdout + p.stderr
        assert "daemon: T2.1" in p.stdout and "pi-9b" in p.stdout and "dry" in p.stdout.lower()
        ready.write_text("[]", encoding="utf-8")
        p = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert p.returncode == 1 and "nothing ready" in p.stdout


VLLM_METRICS = """# HELP vllm:num_requests_running Number of requests in model execution batches.
vllm:num_requests_running{model_name="qwen3.5-9b"} 2.0
vllm:num_requests_waiting{model_name="qwen3.5-9b"} 1.0
vllm:kv_cache_usage_perc{model_name="qwen3.5-9b"} 0.42
vllm:prefix_cache_queries_total{model_name="qwen3.5-9b"} 1000.0
vllm:prefix_cache_hits_total{model_name="qwen3.5-9b"} 650.0
"""


def test_vllm_metrics_and_llama_cpp_slots_parse_into_one_lane_state():
    """C-4.1 — running, waiting, kv_usage, prefix_hit_rate out of Prometheus text; slots give
    running and zero waiting with the rest unknown; garbage gives an empty state."""
    from lib.lanes import lane_state_from_metrics, lane_state_from_slots
    s = lane_state_from_metrics(VLLM_METRICS)
    assert s == {"running": 2, "waiting": 1, "kv_usage": 0.42, "prefix_hit_rate": 0.65}
    slots = [{"id": 0, "is_processing": True}, {"id": 1, "is_processing": False}]
    assert lane_state_from_slots(slots) == {"running": 1, "waiting": 0, "kv_usage": None, "prefix_hit_rate": None}
    assert lane_state_from_metrics("not metrics") == {}


def test_a_lane_admits_only_with_nothing_waiting_kv_under_the_ceiling_and_headroom():
    """C-4.2 — the three conditions, each refusal named; an unknown kv_usage does not block."""
    from lib.lanes import admit
    ok = {"running": 1, "waiting": 0, "kv_usage": 0.5, "prefix_hit_rate": 0.6}
    assert admit(ok, limit=4, kv_ceiling=0.85) == (True, "admitted")
    assert admit({**ok, "waiting": 2}, limit=4, kv_ceiling=0.85) == (False, "2 waiting")
    assert admit({**ok, "kv_usage": 0.9}, limit=4, kv_ceiling=0.85) == (False, "kv 0.90 over 0.85")
    assert admit({**ok, "running": 3}, limit=4, kv_ceiling=0.85) == (False, "running 3 of limit 4, no headroom")
    assert admit({**ok, "kv_usage": None}, limit=4, kv_ceiling=0.85) == (True, "admitted")
    assert admit({}, limit=4, kv_ceiling=0.85) == (False, "no lane state")


def test_a_shared_packet_prefix_is_routed_to_the_lane_that_last_served_it_while_warm():
    """C-4.3 — the key is the packet's static prefix; the warm lane wins within the window, the
    first lane otherwise; serving a prefix refreshes its warmth."""
    from lib.lanes import choose_lane, prefix_key, served
    a = "SYSTEM PREFIX " * 200 + "## The requirement A"
    b = "SYSTEM PREFIX " * 200 + "## The requirement B"
    assert prefix_key(a) == prefix_key(b) and prefix_key(a) != prefix_key("other " * 300)
    warm: dict = {}
    assert choose_lane(prefix_key(a), ["9b", "3b"], warm, now=1000.0, warm_s=600) == "9b"
    warm = served(warm, prefix_key(a), "3b", now=1000.0)
    assert choose_lane(prefix_key(b), ["9b", "3b"], warm, now=1300.0, warm_s=600) == "3b"
    assert choose_lane(prefix_key(b), ["9b", "3b"], warm, now=1700.0, warm_s=600) == "9b"


def test_two_server_errors_in_a_row_cool_a_lane_down_for_a_period():
    """C-4.4 — two consecutive 5xx start the cooldown; a 200 in between resets it; the lane is
    routable again when the period ends."""
    from lib.lanes import cooling
    events = [(100.0, 500), (110.0, 502)]
    assert cooling(events, now=120.0, period_s=120) == (True, "2 server errors, cooling until 230s")
    assert cooling(events, now=240.0, period_s=120) == (False, "")
    assert cooling([(100.0, 500), (105.0, 200), (110.0, 503)], now=120.0, period_s=120) == (False, "")
    assert cooling([], now=0.0, period_s=120) == (False, "")


def test_a_speculation_flag_is_admitted_only_when_verdicts_and_temperature_zero_outputs_agree():
    """C-4.5 — paired runs (plain, speculative) per task: equal verdicts and identical greedy
    outputs admit the flag; a differing verdict or a diverging token refuses it, naming the
    task and the first divergence."""
    from lib.lanes import speculation_verdict
    same = [{"task": "T2.1", "plain": {"green": True, "tokens": [1, 2, 3]}, "spec": {"green": True, "tokens": [1, 2, 3]}},
            {"task": "T2.3", "plain": {"green": False, "tokens": [9]}, "spec": {"green": False, "tokens": [9]}}]
    assert speculation_verdict(same) == (True, "2 tasks agree")
    verdict_differs = [{"task": "T2.1", "plain": {"green": True, "tokens": [1]}, "spec": {"green": False, "tokens": [1]}}]
    assert speculation_verdict(verdict_differs) == (False, "T2.1: verdict green without, red with")
    tokens_differ = [{"task": "T2.5", "plain": {"green": True, "tokens": [1, 2, 3, 4]}, "spec": {"green": True, "tokens": [1, 2, 7, 4]}}]
    assert speculation_verdict(tokens_differ) == (False, "T2.5: outputs diverge at token 2")
    shorter = [{"task": "T2.5", "plain": {"green": True, "tokens": [1, 2, 3]}, "spec": {"green": True, "tokens": [1, 2]}}]
    assert speculation_verdict(shorter) == (False, "T2.5: outputs diverge at token 2")
    assert speculation_verdict([]) == (False, "no paired runs")
