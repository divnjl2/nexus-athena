"""v3.10 where a clause came from — `source:` as an attribute, so lessons are a linear scan.

Each test is the executable spec of one C-2.* clause in features/core-layer/contract.md.
"""
from __future__ import annotations

from lib.ast import SOURCES
from lib.contract import lint, parse, render
from lib.contract_report import sources

TEXT = """# Contract: Origins

## C-1 — Things

- **C-1.1** — WHEN the run starts THE SYSTEM SHALL record the start.
  - source: audit
  - note: found by an audit that read the ledger.
- **C-1.2** — WHEN the run ends THE SYSTEM SHALL record the end.
- **C-1.3** *(source ledger)* — WHEN the run is repeated THE SYSTEM SHALL keep both records.
- **C-1.4** — WHEN the run is cancelled THE SYSTEM SHALL record the cancel.
  - source: design
"""


def test_a_source_attribute_is_read_and_kept_out_of_the_text():
    """C-2.1 — the attribute lands on the clause; the normative sentence and its version are
    untouched, so adding an origin invalidates no pin."""
    c = parse(TEXT)
    assert c.by_id("C-1.1").source == "audit"
    assert c.by_id("C-1.1").text == "WHEN the run starts THE SYSTEM SHALL record the start."
    assert c.by_id("C-1.3").source == "ledger", "the inline marker form is the same statement"
    assert c.by_id("C-1.2").source == ""
    bare = parse(TEXT.replace("  - source: audit\n", ""))
    assert bare.by_id("C-1.1").version == c.by_id("C-1.1").version


def test_an_unknown_source_is_reported_in_lint():
    """C-2.2 — a source outside the vocabulary is a lint issue, not a silent new category."""
    issues = lint(parse(TEXT.replace("source: audit", "source: rumour")))
    assert any(i.startswith("C-1.1:") and "rumour" in i for i in issues)
    assert lint(parse(TEXT)) == ()
    assert set(("design", "review", "audit", "incident", "ledger", "mutation")) == set(SOURCES)


def test_the_source_attribute_round_trips_through_render():
    """C-2.3 — render(parse(x)) keeps the source, or canonicalising would be a data-loss step."""
    c = parse(TEXT)
    again = parse(render(c))
    assert [(x.id, x.source) for x in again.clauses] == [(x.id, x.source) for x in c.clauses]


def test_the_sources_report_lists_clauses_under_their_source():
    """C-2.4 — where lessons come from, as a linear scan in document order."""
    rep = sources(parse(TEXT))
    assert rep["by_source"] == {"audit": ["C-1.1"], "ledger": ["C-1.3"], "design": ["C-1.4"]}
    assert rep["counts"]["audit"] == 1 and rep["stated"] == 3


def test_a_clause_without_a_source_is_counted_as_unstated():
    """C-2.5 — a missing origin is reported, never guessed."""
    rep = sources(parse(TEXT))
    assert rep["unstated"] == ["C-1.2"] and rep["counts"]["unstated"] == 1
    assert "C-1.2" not in sum(rep["by_source"].values(), [])
