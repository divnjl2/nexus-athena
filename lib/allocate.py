"""
Athena allocate — clause ids for parallel authors, drawn from lanes (v3.11).

An id is allocated once and never reused. Two agents on two branches both take `C-3.19`
and the merge yields a duplicate id, which the parser refuses. Beads solved this for tasks
with hash ids; the clause grammar has no room for a hash and readable numbers are part of
the point. So (ADR-0003): lane zero allocates below one thousand, lane N allocates from
N*1000 .. N*1000+999. An author or a long-lived branch takes a lane through `ATHENA_LANE`.

Freeze-line: PURE. The environment is passed in.
"""
from __future__ import annotations

from collections.abc import Mapping

LANE_SIZE = 1000
ENV_VAR = "ATHENA_LANE"


def lane_from_env(env: Mapping) -> int:
    """PURE: the lane `ATHENA_LANE` names, else zero (C-4.3). Junk reads as zero."""
    try:
        lane = int(str(env.get(ENV_VAR, "0")).strip() or "0")
    except ValueError:
        return 0
    return lane if lane >= 0 else 0


def lane_of(number: int) -> int:
    return number // LANE_SIZE


def next_id(contract, group: str, lane: int = 0) -> str:
    """PURE: the next unused id of `group` in `lane` (C-4.1, C-4.2).

    After the highest number the lane already holds, never a gap-fill (a reused number is
    a reused id). A new group starts at the lane's first number.
    """
    if lane < 0:
        lane = 0
    taken = []
    for c in contract.clauses:
        parent, _, last = c.id.rpartition(".")
        if parent == group and last.isdigit() and lane_of(int(last)) == lane:
            taken.append(int(last))
    start = lane * LANE_SIZE + 1
    n = max(taken) + 1 if taken else start
    if lane_of(n) != lane:
        raise ValueError(f"lane {lane} of {group} is exhausted at {n - 1}")
    return f"{group}.{n}"
