"""v3.11 ids for parallel authors — lanes, so two branches never allocate the same id.

Each test is the executable spec of one C-4.* clause in features/team-layer/contract.md.
"""
from __future__ import annotations

import json

import athena
from lib.allocate import LANE_SIZE, lane_from_env, next_id
from lib.contract import parse as parse_contract

CONTRACT = parse_contract("""# Contract: X

## C-3 — Things

- **C-3.1** — WHEN a THE SYSTEM SHALL b.
- **C-3.4** — WHEN c THE SYSTEM SHALL d.
- **C-3.2003** — WHEN e THE SYSTEM SHALL f.

## C-4 — Others

- **C-4.1** — WHEN g THE SYSTEM SHALL h.
""")


def test_the_next_id_is_one_no_clause_carries():
    """C-4.1 — after the highest number in the group's lane, never a reuse, never a gap-fill."""
    assert next_id(CONTRACT, "C-3") == "C-3.5"
    assert next_id(CONTRACT, "C-4") == "C-4.2"
    assert next_id(CONTRACT, "C-9") == "C-9.1", "a new group starts at one"
    assert CONTRACT.by_id(next_id(CONTRACT, "C-3")) is None


def test_two_lanes_never_draw_from_the_same_range():
    """C-4.2 — lane N owns N*1000 .. N*1000+999; a lane that already has ids continues after
    its own highest, not after the other lane's."""
    assert LANE_SIZE == 1000
    assert next_id(CONTRACT, "C-3", lane=2) == "C-3.2004"
    assert next_id(CONTRACT, "C-3", lane=1) == "C-3.1001"
    assert next_id(CONTRACT, "C-4", lane=3) == "C-4.3001"
    taken = set()
    contract = CONTRACT
    for lane in (0, 2, 0, 2, 1):
        cid = next_id(contract, "C-3", lane=lane)
        assert cid not in taken
        taken.add(cid)
        contract = parse_contract(
            "# Contract: X\n\n## C-3 — Things\n\n"
            + "".join(f"- **{c}** — WHEN x THE SYSTEM SHALL y.\n"
                      for c in sorted({c.id for c in contract.clauses} | {cid})))


def test_the_lane_comes_from_the_environment_or_zero(tmp_path, monkeypatch, capsys):
    """C-4.3 — an author or a long-lived branch sets ATHENA_LANE once; nothing set means
    lane zero, the hand-written lane."""
    assert lane_from_env({"ATHENA_LANE": "2"}) == 2
    assert lane_from_env({}) == 0
    assert lane_from_env({"ATHENA_LANE": "junk"}) == 0
    path = tmp_path / "contract.md"
    path.write_text("# Contract: X\n\n## C-3 — Things\n\n- **C-3.1** — WHEN a THE SYSTEM SHALL b.\n",
                    encoding="utf-8")
    monkeypatch.setenv("ATHENA_LANE", "2")
    assert athena.main(["contract", "next-id", str(path), "C-3"]) == 0
    assert json.loads(capsys.readouterr().out.strip())["id"] == "C-3.2001"
    monkeypatch.delenv("ATHENA_LANE")
    assert athena.main(["contract", "next-id", str(path), "C-3"]) == 0
    assert json.loads(capsys.readouterr().out.strip())["id"] == "C-3.2"
