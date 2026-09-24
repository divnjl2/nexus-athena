"""v3.14 the queue — the next ready task comes from bd, is claimed, and is dispatched.

Executable spec of C-7.3 in features/executor-layer/contract.md.
"""
from __future__ import annotations

import json

READY = json.dumps([
    {"id": "athena:demo:T1.2", "title": "second", "status": "open", "priority": 2,
     "created_at": "2026-09-24T10:00:00Z"},
    {"id": "athena:demo:T1.1", "title": "first", "status": "open", "priority": 1,
     "created_at": "2026-09-24T09:00:00Z"},
    {"id": "athena:other:T3.3", "title": "elsewhere", "status": "open", "priority": 0,
     "created_at": "2026-09-24T08:00:00Z"},
    {"id": "athena:demo:T2.1", "title": "later", "status": "open", "priority": 1,
     "created_at": "2026-09-24T11:00:00Z"},
])


def test_the_next_ready_task_of_a_slug_is_picked_and_claimed():
    """C-7.3 — out of bd's ready list only this slug's tasks count; the lowest priority number
    wins, the earlier created one on a tie; the claim command names the key; an empty or
    foreign list yields nothing."""
    from lib.queue import claim_command, pick_ready, ready_command
    assert ready_command("demo") == ["bd", "ready", "--json"]
    assert pick_ready(READY, "demo") == "T1.1"
    assert pick_ready(READY, "other") == "T3.3"
    assert pick_ready(READY, "nobody") == ""
    assert pick_ready("", "demo") == "" and pick_ready("not json", "demo") == ""
    only_later = json.dumps([{"id": "athena:demo:T2.1", "priority": 3, "created_at": "x"}])
    assert pick_ready(only_later, "demo") == "T2.1"
    assert claim_command("demo", "T1.1") == ["bd", "update", "athena:demo:T1.1", "--claim"]
