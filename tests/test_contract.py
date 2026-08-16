"""v3.3 contract layer — clause identity, supersede/branching, per-clause pins, migration.

Each test is the executable spec of ONE clause in `features/contract-layer/contract.md`
(the contract this repo keeps about its own contract layer). The clause id is named in the
test docstring, and `features/contract-layer/scenarios.md` binds it with a run_cmd — so
`athena contract coverage` can be run against Athena itself.
"""
import dataclasses

import pytest

from lib.ast import CLAUSE_DRAFT, CLAUSE_SUPERSEDED, CLAUSE_WITHDRAWN, Contract
from lib.contract import (ContractParseError, clause_version, contract_version,
                          import_from_spec, lint, parse, pin_scenarios, render)

BASIC = """# Contract: Demo

## C-1 — Initial state

- **C-1.1** — WHEN a new game starts THE SYSTEM SHALL place the snake at its
  starting cells near the centre.
- **C-1.2** *(draft)* — WHEN a new game starts THE SYSTEM SHALL seed the RNG.
- **C-1.3** *(superseded-by C-1.4 C-1.5)* — WHEN a new game starts THE SYSTEM SHALL set the score to zero.
- **C-1.4** — WHEN a new game starts THE SYSTEM SHALL set the score to zero.
- **C-1.5** *(supersedes C-1.3)* — WHEN a new game starts THE SYSTEM SHALL set the multiplier to one.
  - tags: scoring
- **C-2.9** *(withdrawn)* — THE SYSTEM SHALL play a sound on death.
"""


def test_clause_ids_are_unique_and_immutable():
    """C-1.1 — every clause gets a stable id; a duplicate id is rejected outright."""
    c = parse(BASIC)
    assert [x.id for x in c.clauses] == ["C-1.1", "C-1.2", "C-1.3", "C-1.4", "C-1.5", "C-2.9"]
    with pytest.raises(ContractParseError, match="duplicate clause id"):
        parse(BASIC + "\n- **C-1.1** — WHEN something THE SYSTEM SHALL do it twice.\n")


def test_old_reference_still_resolves_after_supersede():
    """C-1.2 — a clause with successors is superseded, and the OLD id keeps resolving."""
    c = parse(BASIC)
    old = c.by_id("C-1.3")
    assert old.status == CLAUSE_SUPERSEDED
    assert old.superseded_by == ("C-1.4", "C-1.5")
    assert [x.id for x in c.resolve("C-1.3")] == ["C-1.4", "C-1.5"]
    assert c.by_id("C-1.2").status == CLAUSE_DRAFT
    assert c.by_id("C-2.9").status == CLAUSE_WITHDRAWN


def test_supersede_relation_is_symmetric_from_either_end():
    """C-1.3 — declaring the link on the new OR the old clause yields the same graph."""
    from_new = parse("""# Contract: X

- **C-1** — THE SYSTEM SHALL do the old thing.
- **C-2** *(supersedes C-1)* — THE SYSTEM SHALL do the new thing.
""")
    from_old = parse("""# Contract: X

- **C-1** *(superseded-by C-2)* — THE SYSTEM SHALL do the old thing.
- **C-2** — THE SYSTEM SHALL do the new thing.
""")
    for c in (from_new, from_old):
        assert c.by_id("C-1").superseded_by == ("C-2",)
        assert c.by_id("C-2").supersedes == ("C-1",)
        assert c.by_id("C-1").status == CLAUSE_SUPERSEDED
        assert [x.id for x in c.resolve("C-1")] == ["C-2"]


def test_branched_clause_resolves_transitively_to_all_current_clauses():
    """C-1.4 — a reference follows the chain through several hops and both branches."""
    c = parse("""# Contract: X

- **C-1** *(superseded-by C-2)* — THE SYSTEM SHALL v1.
- **C-2** *(superseded-by C-3 C-4)* — THE SYSTEM SHALL v2.
- **C-3** — THE SYSTEM SHALL v3a.
- **C-4** — THE SYSTEM SHALL v3b.
""")
    assert [x.id for x in c.resolve("C-1")] == ["C-3", "C-4"]
    assert [x.id for x in c.live()] == ["C-3", "C-4"]


def test_supersede_cycle_is_linted_and_resolve_terminates():
    """C-1.5 — a cycle is reported by lint and never hangs resolve()."""
    c = parse("""# Contract: X

- **C-1** *(superseded-by C-2)* — THE SYSTEM SHALL a.
- **C-2** *(superseded-by C-1)* — THE SYSTEM SHALL b.
""")
    issues = lint(c)
    assert any("supersede cycle" in i for i in issues)
    assert c.resolve("C-1") == ()          # terminates; no current clause exists


def test_wrapped_clause_text_is_not_truncated():
    """C-1.6 — a continuation line is appended, not dropped (the silent-drop class)."""
    c = parse(BASIC)
    assert c.by_id("C-1.1").text.endswith("near the centre.")


def test_unknown_supersede_target_is_linted_not_crashed():
    """C-1.7 — a dangling reference is a lint issue, not a parse crash."""
    c = parse("""# Contract: X

- **C-2** *(supersedes C-9)* — THE SYSTEM SHALL do a thing.
""")
    assert any("unknown clause C-9" in i for i in lint(c))
    assert lint(parse(BASIC)) == ()


def test_clause_version_is_per_clause_not_whole_file():
    """C-2.1 — editing one clause must not move any other clause's pin."""
    c1 = parse(BASIC)
    edited = BASIC.replace("set the multiplier to one", "set the multiplier to two")
    c2 = parse(edited)
    assert c1.by_id("C-1.5").version != c2.by_id("C-1.5").version
    assert c1.by_id("C-1.1").version == c2.by_id("C-1.1").version
    assert c1.version != c2.version         # the REGISTRY pin does move


def test_reflowing_text_does_not_change_the_clause_version():
    """C-2.2 — re-wrapping a paragraph is not a requirement change."""
    one_line = "# C\n\n- **C-1** — WHEN a thing happens THE SYSTEM SHALL react to it.\n"
    wrapped = "# C\n\n- **C-1** — WHEN a thing happens THE SYSTEM SHALL\n  react to it.\n"
    assert parse(one_line).by_id("C-1").version == parse(wrapped).by_id("C-1").version
    assert clause_version("a  b") == clause_version("a\nb")


def test_pin_inserts_and_refreshes_the_clause_version_in_scenarios():
    """C-2.3 — pinning writes `pins:` under `verifies:` and replaces a stale pin."""
    c = parse(BASIC)
    scen = ("### S1.1 — snake placed\n"
            "- **verifies:** C-1.1\n"
            "- **run_cmd:** `pytest -q`\n"
            "- **Given** a new game\n")
    pinned, stats = pin_scenarios(scen, c)
    assert f"- **pins:** {c.by_id('C-1.1').version}" in pinned
    assert stats == {"pinned": 1, "updated": 0, "unknown_refs": 0}

    stale = pinned.replace(c.by_id("C-1.1").version, "0" * 16)
    repinned, stats2 = pin_scenarios(stale, c)
    assert repinned == pinned                       # idempotent refresh
    assert stats2["updated"] == 1 and stats2["pinned"] == 0

    _, stats3 = pin_scenarios(scen.replace("C-1.1", "C-9.9"), c)
    assert stats3["unknown_refs"] == 1


def test_scenario_parser_reads_the_pin():
    """C-2.4 — a pinned spec carries clause_version into the AST; unpinned stays empty."""
    from lib.scenario_parser import parse as parse_scenarios
    text = ("### S1.1 — t\n- **verifies:** C-1.1\n- **pins:** abc123def456\n"
            "- **run_cmd:** `pytest -q`\n- **Then** it works\n\n"
            "### S1.2 — u\n- **verifies:** C-1.4\n- **run_cmd:** `pytest -q`\n- **Then** ok\n")
    a, b = parse_scenarios(text)
    assert a.clause_version == "abc123def456"
    assert b.clause_version == ""

    # an indented line arriving BEFORE any Given/When/Then has nothing to continue: the
    # guard reads `gwt and indented and non-blank`, and mutation showed that turning that
    # first `and` into `or` makes this input raise IndexError with nobody watching.
    early = "\n".join(("### S2.1 - t",
                       "- **verifies:** C-1.1",
                       "- **run_cmd:** `pytest -q`",
                       "   stray indented prose with no marker",
                       "- **Then** it works",
                       ""))
    (only,) = parse_scenarios(early)
    assert only.id == "S2.1" and "it works" in only.gwt_text


def test_render_round_trips_through_parse():
    """C-2.5 — render(parse(x)) preserves ids, statuses, links and the registry pin."""
    c = parse(BASIC)
    c2 = parse(render(c))
    assert [(x.id, x.status, x.superseded_by, x.supersedes) for x in c.clauses] == \
           [(x.id, x.status, x.superseded_by, x.supersedes) for x in c2.clauses]
    assert c.version == c2.version


def test_import_from_spec_preserves_ears_ids_verbatim():
    """C-6.1 — migrating an existing spec.md must NOT renumber anything."""
    spec = """# Specification: Thing

## Summary
Prose that must not become clauses. FR-1 mentioned inline.

## EARS Acceptance Criteria

### R1 — Initial state
- **R1.1** — WHEN it starts THE SYSTEM SHALL do the first thing.
- **R1.2** — WHEN it starts THE SYSTEM SHALL do the second thing.

## Clarifications
- some note
"""
    c = import_from_spec(spec, title="Thing")
    assert [x.id for x in c.clauses] == ["R1.1", "R1.2"]
    assert c.title == "Thing"
    assert all(x.group.startswith("R1") for x in c.clauses)


def test_empty_contract_is_rejected():
    """C-6.2 — a file with no clauses is a parse error, never an empty green contract."""
    with pytest.raises(ContractParseError, match="no clauses parsed"):
        parse("# Contract: Nothing\n\nJust prose.\n")


def test_contract_version_tracks_status_changes():
    """C-6.3 — withdrawing a clause moves the registry pin even if no text changed."""
    c = parse(BASIC)
    withdrawn = dataclasses.replace(c.clauses[0], status=CLAUSE_WITHDRAWN)
    other = Contract(title=c.title, clauses=(withdrawn,) + c.clauses[1:],
                     version=contract_version((withdrawn,) + c.clauses[1:]))
    assert other.version != c.version


# --- v3.3 reverse-leg findings: real behaviour that no clause demanded ----------

def test_attributes_may_be_sub_bullets_instead_of_inline_markers():
    """C-1.8 — the sub-bullet form is the same statement as the inline marker."""
    inline = parse("""# Contract: X

- **C-1** *(superseded-by C-2; draft)* — WHEN asked THE SYSTEM SHALL answer.
- **C-2** — WHEN asked THE SYSTEM SHALL answer twice.
  - tags: alpha, beta
""")
    sub = parse("""# Contract: X

- **C-1** — WHEN asked THE SYSTEM SHALL answer.
  - status: superseded-by C-2
- **C-2** — WHEN asked THE SYSTEM SHALL answer twice.
  - supersedes: C-1
  - tags: alpha, beta
  - note: whatever the author needs to remember
""")
    for c in (inline, sub):
        assert c.by_id("C-1").superseded_by == ("C-2",)
        assert c.by_id("C-2").supersedes == ("C-1",)
        assert c.by_id("C-2").tags == ("alpha", "beta")
    # the note never becomes part of the requirement
    assert "whatever" not in sub.by_id("C-2").text
    assert sub.by_id("C-2").version == inline.by_id("C-2").version


def test_lint_reports_an_empty_clause():
    """C-1.9 — an id with no sentence behind it is a broken reference waiting to happen."""
    issues = lint(parse("""# Contract: X

- **C-1** — WHEN asked THE SYSTEM SHALL answer.
- **C-2** —
"""))
    # named, and ONLY the empty one: reporting every clause as empty also "contains the
    # string" and would have passed the previous assertion. (Judge's counterexample,
    # executed: exit 0 with a false-positive storm.)
    assert any(i.startswith("C-2:") and "empty clause text" in i for i in issues)
    assert not any(i.startswith("C-1:") and "empty clause text" in i for i in issues)


def test_lint_reports_a_self_supersede():
    """C-1.10 — a clause replacing itself makes resolve() meaningless."""
    c = parse("""# Contract: X

- **C-1** *(supersedes C-1)* — WHEN asked THE SYSTEM SHALL answer.
""")
    assert any("supersedes itself" in i for i in lint(c))


def test_lint_reports_a_superseded_clause_with_no_successor():
    """C-1.11 — "superseded" without a target leaves every old reference dangling."""
    c = parse("""# Contract: X

- **C-1** — WHEN asked THE SYSTEM SHALL answer.
  - status: superseded
- **C-2** — WHEN asked twice THE SYSTEM SHALL answer twice.
- **C-3** *(supersedes C-2)* — WHEN asked twice THE SYSTEM SHALL answer differently.
  - status: superseded
""")
    issues = lint(c)
    # C-3 is the chained case: it REPLACES a predecessor and is itself marked superseded
    # with no successor named. A rule that accepts "names something in either direction"
    # goes silent exactly here — the most likely way a dangling chain actually occurs.
    assert any(i.startswith("C-3:") and "names no successor" in i for i in issues)
    # the issue must NAME the offending clause: a message that merely contains the phrase
    # would pass while pointing at the wrong clause. (Found by a local judge, confirmed by
    # executing its counterexample: the previous assertion stayed green when lint named
    # someone else.)
    assert any(i.startswith("C-1:") and "names no successor" in i for i in issues)
    assert not any(i.startswith("C-2:") for i in issues), "no false positive on a fine clause"


def test_lint_reports_a_clause_that_is_both_withdrawn_and_superseded():
    """C-1.12 — a requirement is replaced or dropped, never both; the reader cannot tell
    which one is true."""
    c = parse("""# Contract: X

- **C-1** *(withdrawn; superseded-by C-2)* — WHEN asked THE SYSTEM SHALL answer.
- **C-2** — WHEN asked THE SYSTEM SHALL answer twice.
""")
    assert any("withdrawn AND superseded" in i for i in lint(c))


def test_lint_reports_an_unknown_status():
    """C-1.13 — an unrecognised status must not silently read as active."""
    c = parse("""# Contract: X

- **C-1** — WHEN asked THE SYSTEM SHALL answer.
""")
    broken = dataclasses.replace(c.clauses[0], status="maybe")
    from lib.ast import Contract as _C
    assert any("unknown status" in i for i in lint(_C(title="X", clauses=(broken,))))


def test_import_takes_only_the_named_section_and_falls_back_to_the_whole_file():
    """C-6.4 — importing must not sweep prose, user stories or edge cases into the contract."""
    spec = """# Specification: Thing

## User Scenarios
- **US-1** — as a user I want things.

## EARS Acceptance Criteria
- **R1.1** — WHEN it starts THE SYSTEM SHALL do the thing.

## Clarifications
- **Q1** — resolved.
"""
    assert [c.id for c in import_from_spec(spec).clauses] == ["R1.1"]
    # a file that is already just criteria (no such heading) still imports
    bare = "- **R9.1** — WHEN it starts THE SYSTEM SHALL do the thing.\n"
    assert [c.id for c in import_from_spec(bare).clauses] == ["R9.1"]


def test_render_keeps_group_headings_and_tags():
    """C-6.5 — a rendered contract must stay human-editable, not just machine-parsable."""
    c = parse("""# Contract: X

## C-1 — Startup

- **C-1.1** — WHEN it starts THE SYSTEM SHALL boot.
  - tags: core

## C-2 — Shutdown

- **C-2.1** — WHEN it stops THE SYSTEM SHALL flush.
""")
    text = render(c)
    assert "## C-1 Startup" in text and "## C-2 Shutdown" in text
    assert "- tags: core" in text
    assert [x.group for x in parse(text).clauses] == [x.group for x in c.clauses]


def test_tags_may_be_declared_in_the_inline_marker():
    """C-1.14 — the marker accepts every attribute the sub-bullets do, so an author never
    has to remember which form supports what."""
    c = parse("""# Contract: X

- **C-1** *(draft; tags alpha beta)* — WHEN asked THE SYSTEM SHALL answer.
- **C-2** *(nonsense-token)* — WHEN asked THE SYSTEM SHALL answer twice.
""")
    assert c.by_id("C-1").tags == ("alpha", "beta")
    assert c.by_id("C-1").status == CLAUSE_DRAFT
    # an unrecognised token becomes a note instead of being silently swallowed
    assert c.by_id("C-2").status == "active"
    assert lint(c) == ()
