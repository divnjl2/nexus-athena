"""Perimeter layer, C-4: the rungs watched over time. Red until lib/drift.py exists."""
from __future__ import annotations


def _rows(rates, executor="pi-omni9", digest="d1", start=0):
    return [{"ts": f"2026-09-{27 + i:02d}T00:00:00", "executor": executor, "model": "omnicoder-9b", "runtime": "vllm 0.21.0",
             "set_digest": digest, "tasks": 10, "green": int(round(r * 10)), "rate": r} for i, r in enumerate(rates, start)]


def test_a_bench_run_appends_one_row_per_executor_with_the_sets_digest():
    """C-4.1 — one row per executor: ts, executor, model id, runtime version, set digest, tasks,
    green, rate; two runs of the same set share the digest."""
    from lib.drift import series_rows, set_digest
    table = {"pi-omni9": {"tasks": 10, "green": 8}, "pi-3b": {"tasks": 10, "green": 3}}
    prov = {"pi-omni9": {"model": "omnicoder-9b", "runtime": "vllm 0.21.0"}, "pi-3b": {"model": "nanbeige-3b", "runtime": "llama.cpp b9180"}}
    d1 = set_digest(["T2.1", "T2.2"], ["aaa", "bbb"])
    assert d1 == set_digest(["T2.2", "T2.1"], ["bbb", "aaa"]) and d1 != set_digest(["T2.1"], ["aaa"]) and len(d1) >= 12
    # review 27.09: the digest rides in a JSON row, so it is text, not bytes
    import json
    assert isinstance(d1, str) and json.dumps({"set_digest": d1})
    rows = series_rows(table, prov, ts="2026-09-27T01:00:00", set_digest=d1)
    assert [r["executor"] for r in rows] == ["pi-3b", "pi-omni9"]
    r = next(x for x in rows if x["executor"] == "pi-omni9")
    assert r == {"ts": "2026-09-27T01:00:00", "executor": "pi-omni9", "model": "omnicoder-9b", "runtime": "vllm 0.21.0",
                 "set_digest": d1, "tasks": 10, "green": 8, "rate": 0.8}
    assert json.dumps(rows)   # every row is a JSON line of the series
    assert series_rows({"x": {"tasks": 0, "green": 0}}, {}, ts="t", set_digest=d1)[0]["rate"] == 0.0


def test_a_drop_in_the_pass_rate_is_found_by_a_one_sided_cusum_and_dated():
    """C-4.2 — a flat series has no drop; a fall from 0.8 to 0.4 is found and its start index is at
    the fall; too few points is no verdict."""
    from lib.drift import cusum_drop
    assert cusum_drop([0.8] * 12, min_points=6) is None
    assert cusum_drop([0.8, 0.7, 0.9, 0.8, 0.8, 0.7, 0.9, 0.8, 0.8, 0.7], min_points=6) is None
    series = [0.8, 0.8, 0.9, 0.8, 0.8, 0.8, 0.4, 0.4, 0.3, 0.4]
    drop = cusum_drop(series, min_points=6)
    assert drop is not None and 5 <= drop["start"] <= 6 and drop["level"] < drop["ref"]
    assert cusum_drop([0.8, 0.4, 0.4], min_points=6) is None
    # a rise is not a drop
    assert cusum_drop([0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.9, 0.9, 0.9, 0.9], min_points=6) is None
    # review 27.09: a CUSUM accumulates — one bad night is not a drop, a recovered dip is not a drop,
    # the same low level held for several points is (the first landing fired on any point below the reference)
    steady = [0.8] * 8
    assert cusum_drop(steady + [0.2] + [0.8] * 3, min_points=6) is None
    assert cusum_drop(steady + [0.5, 0.5] + [0.8] * 6, min_points=6) is None
    held = cusum_drop(steady + [0.3] * 4, min_points=6)
    assert held is not None and 8 <= held["start"] <= 10


def test_a_drop_emits_the_bd_command_that_opens_a_bead_once():
    """C-4.3 — bd create with a title naming executor, model, runtime and the drop; the same drop
    twice yields the command once."""
    from lib.drift import drift_bead_command, drift_once
    finding = {"executor": "pi-omni9", "model": "omnicoder-9b", "runtime": "vllm 0.21.0", "ref": 0.82, "level": 0.4, "start": 6, "start_ts": "2026-10-03T00:00:00"}
    cmd = drift_bead_command("perimeter-layer", finding)
    assert cmd[:2] == ["bd", "create"]
    title = " ".join(cmd)
    for word in ("pi-omni9", "omnicoder-9b", "vllm 0.21.0", "0.82", "0.4", "2026-10-03"):
        assert word in title, word
    assert any(x.startswith("athena:perimeter-layer:drift:") for x in cmd)
    seen: set = set()
    first = drift_once([finding], seen, slug="perimeter-layer")
    again = drift_once([finding], seen, slug="perimeter-layer")
    assert len(first) == 1 and again == []


def test_a_change_of_the_set_is_reported_apart_from_a_change_of_the_rung():
    """C-4.4 — rows whose digest differs from the previous row are named as a set change and left
    out of the CUSUM, so a new set does not read as a drop."""
    from lib.drift import series_verdicts
    steady = _rows([0.8] * 6) + _rows([0.4] * 4, digest="d2", start=6)
    v = series_verdicts(steady, min_points=6)["pi-omni9"]
    assert v["set_changes"] and v["set_changes"][0]["from"] == "d1" and v["set_changes"][0]["to"] == "d2"
    assert v.get("drop") is None and v["verdict"] in ("ok", "too few points", "set changed")
    real = _rows([0.8] * 6 + [0.4] * 4)
    w = series_verdicts(real, min_points=6)["pi-omni9"]
    assert w["drop"] is not None and w["verdict"] == "drop" and w["set_changes"] == []
    # review 27.09: the drop is the CUSUM's own record, not a flag — the wiring prints where it began
    assert isinstance(w["drop"], dict) and {"start", "ref", "level"} <= set(w["drop"]) and 5 <= w["drop"]["start"] <= 7
    two = series_verdicts(real + _rows([0.9] * 8, executor="pi-3b"), min_points=6)
    assert set(two) == {"pi-omni9", "pi-3b"} and two["pi-3b"]["verdict"] == "ok"
