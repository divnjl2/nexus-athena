"""v3.16 the foundry — the ladder (C-5) and provenance (C-6).

Each test is the executable spec of one clause in features/foundry-layer/contract.md.
"""
from __future__ import annotations

import json


def test_pre_dispatch_features_are_logged_per_task():
    """C-5.1 — packet tokens, files owned, clause count, spec count, lines owned, prior
    attempts; lines owned counts only the task's files in the map."""
    from lib.ladder import features
    clause_map = {"clauses": {"C-2.1": {"lib/a.py": [1, 2, 3], "lib/b.py": [7]}, "C-2.3": {"lib/a.py": [9]}}}
    f = features(packet_chars=8000, files=["lib/a.py", "lib/b.py"], clauses=["C-2.1", "C-2.3"],
                 specs=["S2.1", "S2.3"], clause_map=clause_map, prior_attempts=1)
    assert f == {"packet_tokens": 2000, "files_owned": 2, "clause_count": 2, "spec_count": 2,
                 "lines_owned": 5, "prior_attempts": 1}
    assert features(packet_chars=0, files=[], clauses=[], specs=[], clause_map={}, prior_attempts=0)["lines_owned"] == 0


def test_a_rung_escalates_on_two_reds_or_a_fail_fast_signal_with_a_handoff():
    """C-5.2 — two red attempts on the rung escalate; so does one attempt with a fail-fast
    signal; one plain red does not; the handoff is files, last test output and notes, capped."""
    from lib.ladder import handoff, should_escalate
    red = {"green": False, "rung": "3b"}
    assert should_escalate([red, red], signals={}) == (True, "red twice on 3b")
    assert should_escalate([red], signals={}) == (False, "")
    assert should_escalate([red], signals={"turns": 40, "p90_turns": 25}) == (True, "turns 40 past p90 25")
    assert should_escalate([red], signals={"repeated_calls": 4}) == (True, "same tool call repeated 4 times")
    assert should_escalate([red], signals={"turns": 20, "median_turn": 12, "writes": 0}) == (True, "no write after turn 12")
    assert should_escalate([{"green": True, "rung": "3b"}], signals={"turns": 99, "p90_turns": 1}) == (False, "")
    attempt = {"changed_files": ["lib/a.py"], "red": [{"cmd": "python -m pytest t.py -q", "tail": "E  assert 1 == 2"}],
               "last_words": "I could not find the function", "rung": "3b"}
    text = handoff(attempt, cap=2000)
    assert "lib/a.py" in text and "assert 1 == 2" in text and "could not find" in text and "3b" in text
    big = {**attempt, "last_words": "x" * 5000}
    assert len(handoff(big, cap=2000)) <= 2000


def test_the_rung_table_reports_win_rate_and_gpu_minutes_and_disables_a_losing_rung():
    """C-5.3 — per (rung, class): attempts, greens, win rate, GPU minutes per green; a rung
    under the floor for a class is disabled for that class only."""
    from lib.ladder import enabled_rungs, rung_table
    rec = [{"rung": "3b", "cls": "A", "green": True, "duration_ms": 60000},
           {"rung": "3b", "cls": "A", "green": True, "duration_ms": 120000},
           {"rung": "3b", "cls": "B", "green": False, "duration_ms": 900000},
           {"rung": "3b", "cls": "B", "green": False, "duration_ms": 900000},
           {"rung": "9b", "cls": "B", "green": True, "duration_ms": 300000},
           {"rung": "9b", "cls": "B", "green": False, "duration_ms": 300000}]
    t = rung_table(rec)
    assert t[("3b", "A")] == {"n": 2, "green": 2, "win_rate": 1.0, "gpu_min_per_green": 1.5}
    assert t[("3b", "B")] == {"n": 2, "green": 0, "win_rate": 0.0, "gpu_min_per_green": None}
    assert t[("9b", "B")] == {"n": 2, "green": 1, "win_rate": 0.5, "gpu_min_per_green": 10.0}
    assert enabled_rungs(t, ladder=["3b", "9b", "opus"], floor=0.2) == {"A": ["3b", "9b", "opus"], "B": ["9b", "opus"]}


def test_a_verdict_carries_the_provenance_of_what_produced_it():
    """C-6.1 — model identity, runtime, sampling and seed, packet digest, tool set digest and
    relay version, in one block the record carries."""
    from lib.provenance import provenance
    p = provenance(model_id="omnicoder-9b", weights_digest="sha256:abc", runtime="vllm", runtime_version="0.21.0",
                   sampling={"temperature": 0.6, "top_p": 0.95, "max_tokens": 8192}, seed=7,
                   packet_sha="p" * 64, tools_sha="t" * 64, relay_version="3.16")
    assert p == {"model": {"id": "omnicoder-9b", "weights": "sha256:abc"},
                 "runtime": {"name": "vllm", "version": "0.21.0"},
                 "sampling": {"temperature": 0.6, "top_p": 0.95, "max_tokens": 8192, "seed": 7},
                 "packet_sha256": "p" * 64, "tools_sha256": "t" * 64, "relay_version": "3.16"}


def test_a_merged_verdict_becomes_an_in_toto_statement_with_a_slsa_shaped_predicate():
    """C-6.2 — Statement v1 with the merged tree as subject and predicate athena/verdict/v1
    whose buildDefinition and runDetails carry the record's provenance and outcome."""
    from lib.provenance import provenance, statement
    rec = {"task": "T2.1", "executor": "pi-omni9#a", "green": True, "ts": "2026-09-25T10:00:00Z",
           "duration_ms": 61000, "workspace": "w/T2.1-abcd",
           "provenance": provenance(model_id="omnicoder-9b", weights_digest="sha256:abc", runtime="vllm",
                                    runtime_version="0.21.0", sampling={"temperature": 0.6}, seed=7,
                                    packet_sha="p" * 64, tools_sha="t" * 64, relay_version="3.16")}
    st = statement(rec, subject_digest="9" * 40, base_commit="1" * 40)
    assert st["_type"] == "https://in-toto.io/Statement/v1"
    assert st["subject"] == [{"name": "tree", "digest": {"gitTree": "9" * 40}}]
    assert st["predicateType"] == "athena/verdict/v1"
    bd, rd = st["predicate"]["buildDefinition"], st["predicate"]["runDetails"]
    assert bd["externalParameters"] == {"task": "T2.1", "packet_sha256": "p" * 64}
    assert bd["internalParameters"]["model"] == {"id": "omnicoder-9b", "weights": "sha256:abc"}
    assert bd["internalParameters"]["sampling"]["seed"] == 7
    assert bd["resolvedDependencies"] == [{"name": "base", "digest": {"gitCommit": "1" * 40}}]
    assert rd["builder"] == {"id": "athena/pi-omni9#a"} and rd["metadata"]["startedOn"] == "2026-09-25T10:00:00Z"
    assert rd["byproducts"] == {"green": True, "duration_ms": 61000}
    json.dumps(st)


def test_a_record_missing_provenance_names_the_missing_fields():
    """C-6.3 — every missing field named, dotted, in a stable order; a complete record misses
    nothing; a record without the block misses all of them."""
    from lib.provenance import missing_provenance, provenance
    full = {"provenance": provenance(model_id="m", weights_digest="w", runtime="r", runtime_version="1",
                                     sampling={"temperature": 0}, seed=0, packet_sha="p", tools_sha="t", relay_version="v")}
    assert missing_provenance(full) == ()
    partial = {"provenance": {"model": {"id": "m"}, "runtime": {"name": "r"}, "sampling": {}}}
    assert missing_provenance(partial) == ("model.weights", "runtime.version", "sampling.seed",
                                           "packet_sha256", "tools_sha256", "relay_version")
    assert len(missing_provenance({})) == 9
