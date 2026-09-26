"""Oracles of the second kind, foundry C-9.5: a time and memory budget as a spec."""
import tracemalloc

import pytest

from lib.memory import packet_with_memory, repo_map_for, select_lessons


def _fixture():
    pk = {"text": "STATIC " * 4000 + chr(10) + "# task" + chr(10) + "x" * 2000, "checks": ["a"], "files": ["lib/a.py"]}
    lessons = [{"clause": f"C-2.{i % 9 + 1}", "file": "lib/refinery.py", "rule": "r" * 80, "ts": "2026"} for i in range(60)]
    index = {f"lib/m{i}.py": {"defs": [f"f{j}" for j in range(20)], "imports": [f"lib.m{(i + 1) % 40}"]} for i in range(40)}
    return pk, lessons, index


def _pack(pk, lessons, index):
    rm = repo_map_for(index, seeds=["lib/m1.py"], budget_tokens=800)
    ls = select_lessons(lessons, clause_ids=["C-2.3"], files=["lib/refinery.py"], n=5)
    return packet_with_memory(pk, repo_map=rm, lessons=ls)


def test_packing_a_packet_with_memory_stays_within_its_time_and_memory_budget(benchmark):
    """C-9.5 — the budget is the spec: 5 ms mean over the rounds, 2 MB peak; a lane running beside
    the suite is noise a hundredfold below it, a quadratic packing is not."""
    pk, lessons, index = _fixture()
    out = benchmark.pedantic(_pack, args=(pk, lessons, index), rounds=20, iterations=5, warmup_rounds=1)
    assert len(out["text"]) > 30000 and out["checks"] == ["a"]
    assert benchmark.stats.stats.mean < 0.005, f"mean {benchmark.stats.stats.mean * 1000:.2f} ms over the 5 ms budget"
    tracemalloc.start()
    try:
        _pack(pk, lessons, index)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 2 * 1024 * 1024, f"peak {peak // 1024} KB over the 2 MB budget"


def test_the_budget_would_catch_a_quadratic_packing(benchmark):
    """C-9.5 — the negative control: a packing that walks the packet once per lesson line blows
    the time budget, so the spec can fail."""
    pk, lessons, index = _fixture()

    def quadratic():
        text = pk["text"]
        return sum(text.count("STATIC") for _ in range(2000))   # one full pass per lesson line, 60M chars
    benchmark.pedantic(quadratic, rounds=3, iterations=1)
    assert benchmark.stats.stats.mean >= 0.005
