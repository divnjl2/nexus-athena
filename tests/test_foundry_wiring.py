"""v3.17 the foundry wired into the loop (C-11): provenance in every record, the mutation
stage in the merge queue, memory in the packet, the ladder and live lane admission in the
daemon. Each test is the executable spec of one clause in features/foundry-layer/contract.md.
"""
from __future__ import annotations

import hashlib
import json


def test_a_dispatch_record_carries_provenance_built_from_the_executor_and_the_packet():
    """C-11.1 — the block names the model the executor resolves to, the thinking level as the
    sampling, the rendered packet's and the tool set's digests and the frame's version; a
    record made with it carries it; the fields the frame cannot know are named missing."""
    from lib.dispatch import record
    from lib.provenance import missing_provenance, provenance_for
    pk = "# Task T1.1\nthe packet as rendered\n"
    prov = provenance_for("pi-omni9", packet_text=pk, thinking="low", tools="read,bash,edit,write",
                          athena_version="3.17", runtime_version="0.21.0", seed=None)
    assert prov["model"]["id"] == "omnicoder-9b" and prov["model"]["weights"] is None
    assert prov["runtime"] == {"name": "vllm", "version": "0.21.0"}
    assert prov["sampling"] == {"thinking": "low", "seed": None}
    assert prov["packet_sha256"] == hashlib.sha256(pk.encode("utf-8")).hexdigest()
    assert prov["tools_sha256"] == hashlib.sha256(b"read,bash,edit,write").hexdigest()
    assert prov["relay_version"] == "3.17"
    assert missing_provenance({"provenance": prov}) == ("model.weights", "sampling.seed")
    rec = record("T1.1", "pi-omni9", {"landed": True, "green": True, "passed": True, "changed_files": ["lib/a.py"]},
                 duration_ms=10, tokens={}, ts="2026-09-26T10:00:00Z", workspace="w", provenance=prov)
    assert rec["provenance"] == prov
    assert "provenance" not in record("T1.1", "pi-9b", {}, duration_ms=0, tokens={}, ts="t")
    assert provenance_for("pi-3b", packet_text="", thinking="", tools="", athena_version="3.17")["runtime"]["name"] == "llama.cpp"
    assert provenance_for("claude", packet_text="", thinking="", tools="", athena_version="3.17")["model"]["id"] == "claude"


def test_the_merge_queue_has_a_mutation_stage_between_check_and_fast_forward():
    """C-11.2 — the stages are named in order with `mutation` after `check`; the stage's verdict
    comes from the changed lines through the clause map and the sweep's results; a survivor
    on an added line refuses at `mutation` with the clause named; and the changed lines are
    read out of a unified diff."""
    from lib.refinery import STAGES, changed_lines_from_diff, mutation_stage
    assert STAGES == ("admit", "rebase", "check", "mutation", "fast-forward")
    diff = ("diff --git a/lib/x.py b/lib/x.py\n--- a/lib/x.py\n+++ b/lib/x.py\n"
            "@@ -10,0 +11,2 @@\n+    a = 1\n+    b = 2\n@@ -30 +32 @@\n-    old\n+    new\n"
            "diff --git a/lib/new.py b/lib/new.py\nnew file mode 100644\n--- /dev/null\n+++ b/lib/new.py\n@@ -0,0 +1,2 @@\n+x = 1\n+y = 2\n")
    assert changed_lines_from_diff(diff) == {"lib/x.py": [11, 12, 32], "lib/new.py": [1, 2]}
    clause_map = {"clauses": {"C-2.1": {"lib/x.py": [11, 12, 32]}}}
    results = [{"path": "lib/x.py", "line": 11, "kind": "constant", "killed": True},
               {"path": "lib/x.py", "line": 12, "kind": "constant", "killed": False}]
    v = mutation_stage(changed_lines_from_diff(diff), clause_map, results, threshold=0.7)
    assert v["ok"] is False and v["stage"] == "mutation" and v["clause"] == "C-2.1"
    assert v["survivor"] == {"path": "lib/x.py", "line": 12, "kind": "constant"}
    assert "lib/new.py" in v["unowned"]
    ok = mutation_stage(changed_lines_from_diff(diff), clause_map, [{**results[1], "killed": True}, results[0]], threshold=0.7)
    assert ok["ok"] is True and ok["scores"]["C-2.1"]["score"] == 1.0
    assert mutation_stage({}, clause_map, [], threshold=0.7)["ok"] is True


def test_the_packet_carries_the_repo_map_and_the_lessons_after_the_prefix():
    """C-11.3 — a packet gains a repository map section and a lessons section after the static
    prefix and before the requirement; the budget grows by what was added; an empty map or no
    lessons adds no section."""
    from lib.memory import packet_with_memory
    packet = "STATIC\n## The requirement\nbody\n"
    pk = {"text": packet, "chars": len(packet), "budget_chars": 36000, "over_budget": False}
    out = packet_with_memory(pk, repo_map="lib/a.py\n  def f()", lessons=[{"clause": "C-2.1", "file": "lib/a.py", "rule": "filter by task first"}])
    t = out["text"]
    assert t.index("STATIC") < t.index("## Repository map") < t.index("## Lessons") < t.index("## The requirement")
    assert "def f()" in t and "C-2.1: filter by task first (lib/a.py)" in t
    assert out["chars"] == len(t) and out["map_chars"] > 0 and out["lesson_count"] == 1
    rich = {**pk, "task": {"id": "T1"}, "checks": ["python -m pytest t.py -q"], "specs": [1]}
    kept = packet_with_memory(rich, repo_map="lib/a.py", lessons=[])
    assert kept["task"] == {"id": "T1"} and kept["checks"] == rich["checks"] and kept["specs"] == [1]   # review: every other key of the packet survives
    assert packet_with_memory(pk, repo_map="", lessons=[]) is pk


def test_the_daemon_climbs_the_ladder_on_the_escalation_rule_and_stops_at_its_top():
    """C-11.4 — the next rung after the current one, or none at the top; the handoff travels as
    the brief of the escalated dispatch; a disabled rung for the task's class is skipped."""
    from lib.ladder import next_rung
    ladder = ["pi-3b", "pi-omni9", "claude"]
    assert next_rung(ladder, "pi-3b") == "pi-omni9"
    assert next_rung(ladder, "pi-omni9") == "claude"
    assert next_rung(ladder, "claude") is None
    assert next_rung(ladder, "pi-9b") == "pi-3b"
    assert next_rung(ladder, "pi-3b", disabled={"pi-omni9"}) == "claude"
    assert next_rung([], "pi-3b") is None


def test_lane_endpoints_are_derived_from_the_executor_and_the_admission_reads_them():
    """C-11.5 — a pi executor's lane has a metrics or a slots endpoint next to its base url;
    a non-lane executor has none; the live state is read through an injected fetcher and
    falls back to an empty state when the fetch fails."""
    from lib.lanes import lane_endpoint, live_state
    assert lane_endpoint("pi-omni9", base_url="http://127.0.0.1:8006/v1") == ("metrics", "http://127.0.0.1:8006/metrics")
    assert lane_endpoint("pi-3b", base_url="http://127.0.0.1:8003/v1") == ("slots", "http://127.0.0.1:8003/slots")
    assert lane_endpoint("claude", base_url="") == ("", "")
    assert lane_endpoint("pi-9b", base_url="http://127.0.0.1:8417/v1") == ("metrics", "http://127.0.0.1:8417/metrics")   # review: the rule is the runtime, not a name list

    def fetch(url):
        if ":9999/" in url:
            raise OSError("down")
        if url.endswith("/metrics"):
            return 'vllm:num_requests_running{m="x"} 1.0\nvllm:num_requests_waiting{m="x"} 0.0\nvllm:kv_cache_usage_perc{m="x"} 0.2\n'
        if url.endswith("/slots"):
            return json.dumps([{"id": 0, "is_processing": False}])
        raise OSError("down")
    assert live_state("pi-omni9", "http://127.0.0.1:8006/v1", fetch=fetch)["running"] == 1
    assert live_state("pi-3b", "http://127.0.0.1:8003/v1", fetch=fetch) == {"running": 0, "waiting": 0, "kv_usage": None, "prefix_hit_rate": None}
    assert live_state("pi-9b", "http://127.0.0.1:9999/v1", fetch=fetch) == {}
    assert live_state("claude", "", fetch=fetch) == {}


def test_an_iteration_that_lost_green_checks_is_rolled_back_to_the_better_one():
    """C-11.6 — green count per iteration from its checks; a drop names the better iteration
    to restore and records the regression; equal or better restores nothing; the first
    iteration never rolls back."""
    from lib.dispatch import green_count, regression
    it1 = [{"cmd": "a", "exit": 0}, {"cmd": "b", "exit": 1}, {"cmd": "c", "exit": 1}]
    it2 = [{"cmd": "a", "exit": 0}, {"cmd": "b", "exit": 0}, {"cmd": "c", "exit": 1}]
    it3 = [{"cmd": "a", "exit": 1}, {"cmd": "b", "exit": 1}, {"cmd": "c", "exit": 1}]
    assert green_count(it1) == 1 and green_count(it2) == 2 and green_count(it3) == 0 and green_count([]) == 0
    assert regression([it1]) is None
    assert regression([it1, it2]) is None
    assert regression([it1, it2, it3]) == {"restore": 2, "from": 3, "green_before": 2, "green_after": 0}
    assert regression([it2, it1]) == {"restore": 1, "from": 2, "green_before": 2, "green_after": 1}
    assert regression([it1, it1]) is None
