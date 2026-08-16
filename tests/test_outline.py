"""v3.6 the derived outline — the artifacts saying how the system is put together.

An audit read this repo's artifacts alone and reconstructed the design correctly, then said
the honest part: every sentence about the PARTS had to be inferred. `outline` closes that
without adding a document to maintain — it reads the shape out of the clause map, which is
itself read out of the code's execution.

Each test is the executable spec of one C-11.* clause in features/contract-layer/contract.md.
"""
from __future__ import annotations

from lib.contract import parse as parse_contract
from lib.contract_report import coverage
from lib.outline import outline, render

CONTRACT = parse_contract("""# Contract: Two halves

## C-1 — Parsing

- **C-1.1** — WHEN a clause is read THE SYSTEM SHALL keep its id.
- **C-1.2** *(withdrawn)* — WHEN asked THE SYSTEM SHALL guess.

## C-2 — Reporting

- **C-2.1** — WHEN a report is rendered THE SYSTEM SHALL name the unproved clauses.
- **C-2.2** — WHEN a total is shown THE SYSTEM SHALL count only live clauses.
""")

#: C-1 lives in parser.py, C-2 in report.py; shared.py is executed by both on the way in.
CMAP = {"schema": "athena.clause_map/3", "clauses": {
    "C-1.1": {"lib/parser.py": [1, 2, 3, 4], "lib/shared.py": [1, 2, 3, 4, 5, 6, 7, 8, 9]},
    "C-2.1": {"lib/report.py": [10, 11], "lib/shared.py": [1, 2, 3, 4, 5, 6, 7, 8, 9]},
    "C-2.2": {"lib/report.py": [12], "lib/shared.py": [1, 2]},
}}


def _outline(cmap=CMAP, scenarios=()):
    return outline(CONTRACT, coverage(CONTRACT, scenarios), cmap)


def test_the_outline_names_each_group_home_by_exclusivity_not_by_reach():
    """C-11.22 — the module a group OWNS, not the one its specs merely pass through.
    Ranking by line count made the parser the home of every group, because every spec runs
    it on the way to anything else: that is execution reach, and it is not architecture."""
    o = _outline()
    c1 = o["groups"]["C-1 Parsing"]
    c2 = o["groups"]["C-2 Reporting"]

    home1 = [f["path"] for f in c1["files"] if not f["shared"]]
    home2 = [f["path"] for f in c2["files"] if not f["shared"]]
    assert home1 == ["lib/parser.py"], "shared.py has 9 lines here and parser.py 4"
    assert home2 == ["lib/report.py"]

    shared = [f["path"] for f in c1["files"] if f["shared"]]
    assert shared == ["lib/shared.py"], "a module every group reaches is infrastructure"


def test_the_outline_separates_the_four_statuses_and_counts_proofs():
    """C-11.23 — a withdrawn clause is not owed a proof and must not be counted live; the
    outline is where the status vocabulary of this format is actually visible."""
    o = _outline()
    c1 = o["groups"]["C-1 Parsing"]
    assert (c1["live"], c1["withdrawn"]) == (1, 1)
    assert o["live"] == 3 and o["clauses"] == 4

    assert c1["proved"] == 0 and c1["unproved"] == ["C-1.1"], "no specs were supplied"
    text = render(o)
    assert "1 withdrawn" in text and "unproved: C-1.1" in text
    assert "home: lib/parser.py (4 lines)" in text
    assert "shared: lib/shared.py" in text


def test_the_outline_says_so_when_there_is_no_map():
    """C-11.24 — without a clause map the outline still answers about the contract, and
    says the architecture column is missing rather than rendering an empty one."""
    o = _outline(cmap={})
    assert o["groups"]["C-1 Parsing"]["files"] == []
    assert "run `athena contract map`" in render(o)


def test_a_module_many_groups_reach_is_still_a_home_when_it_holds_lines_only_one_owns():
    """C-11.25 — exclusivity is measured per LINE, not per file. Counting how many groups
    touch a module called lib/contract.py shared for everyone, so the parser group and the
    critique group — both of which genuinely live there — came out homeless."""
    cmap = {"schema": "athena.clause_map/4", "clauses": {
        # both groups execute the same entry lines of one module; each also owns a stretch
        # of it that nobody else does.
        "C-1.1": {"lib/core.py": [1, 2, 3, 10, 11, 12]},
        "C-2.1": {"lib/core.py": [1, 2, 3, 20, 21]},
    }}
    o = outline(CONTRACT, coverage(CONTRACT, ()), cmap)
    c1 = o["groups"]["C-1 Parsing"]["files"]
    c2 = o["groups"]["C-2 Reporting"]["files"]

    assert [f["path"] for f in c1 if not f["shared"]] == ["lib/core.py"]
    assert [f["path"] for f in c2 if not f["shared"]] == ["lib/core.py"]
    assert c1[0]["exclusive"] == 3 and c1[0]["lines"] == 6
    assert c2[0]["exclusive"] == 2 and c2[0]["lines"] == 5
