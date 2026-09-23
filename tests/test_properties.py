"""v3.11 properties — the parser, the pins and the batch key proved over generated inputs,
not examples.

Each test is the executable spec of one C-7.* clause in features/team-layer/contract.md.
"""
from __future__ import annotations

import shlex

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from lib.ast import SOURCES
from lib.contract import ContractParseError, clause_version, lint, parse, render
from lib.spec_runner import batch_key

WORDS = ["spec", "clause", "ledger", "map", "runs", "reports", "the", "start", "record",
         "again", "twice", "once"]
TAGS = ["slow", "security", "performance", "isolated"]

words = st.lists(st.sampled_from(WORDS), min_size=1, max_size=5)


@st.composite
def contracts(draw):
    n = draw(st.integers(min_value=1, max_value=6))
    numbers = draw(st.lists(st.integers(min_value=1, max_value=60), min_size=n, max_size=n,
                            unique=True))
    lines = ["# Contract: Generated", "", "## C-1 — Things", ""]
    withdrawn: set[int] = set()
    for i, num in enumerate(numbers):
        trigger = " ".join(draw(words))
        act = " ".join(draw(words))
        marks = []
        status = draw(st.sampled_from(["active", "active", "draft", "withdrawn"]))
        if status != "active":
            marks.append(status)
        if status == "withdrawn":
            withdrawn.add(num)
        earlier = [m for m in numbers[:i] if m not in withdrawn]
        if earlier and status != "withdrawn" and draw(st.booleans()):
            marks.append(f"supersedes C-1.{draw(st.sampled_from(earlier))}")
        marker = f" *({'; '.join(marks)})*" if marks else ""
        lines.append(f"- **C-1.{num}**{marker} — WHEN {trigger} THE SYSTEM SHALL {act}.")
        if draw(st.booleans()):
            lines.append("  - tags: " + ", ".join(draw(st.lists(st.sampled_from(TAGS),
                                                              min_size=1, max_size=2, unique=True))))
        if draw(st.booleans()):
            lines.append(f"  - source: {draw(st.sampled_from(SOURCES))}")
    return "\n".join(lines) + "\n"


def _shape(contract):
    return [(c.id, c.status, c.source, c.tags, c.supersedes, c.superseded_by)
            for c in contract.clauses]


@settings(max_examples=60, deadline=None)
@given(contracts())
def test_any_contract_survives_render_and_parse(text):
    """C-7.1 — render(parse(x)) is a canonicaliser, never a data-loss step, for any contract
    the grammar admits."""
    first = parse(text)
    again = parse(render(first))
    assert _shape(again) == _shape(first)


@settings(max_examples=60, deadline=None)
@given(st.lists(st.sampled_from(WORDS), min_size=3, max_size=12), st.data())
def test_rewrapping_never_moves_a_clause_version(ws, data):
    """C-7.2 — a version hashes the words, not the whitespace between them."""
    flat = " ".join(ws)
    pieces = []
    for i, w in enumerate(ws):
        if i:
            pieces.append(data.draw(st.sampled_from([" ", "  ", "\n  ", "   \n  "])))
        pieces.append(w)
    wrapped = "".join(pieces)
    a = parse(f"# Contract: X\n\n- **C-1.1** — WHEN {flat} THE SYSTEM SHALL act.\n")
    b = parse(f"# Contract: X\n\n- **C-1.1** — WHEN {wrapped} THE SYSTEM SHALL act.\n")
    assert a.clauses[0].version == b.clauses[0].version
    assert clause_version(flat) == clause_version(" ".join(flat.split()))


@settings(max_examples=60, deadline=None)
@given(st.lists(st.sampled_from(WORDS), min_size=3, max_size=12), st.data())
def test_a_changed_word_always_moves_the_version(ws, data):
    """C-7.3 — a word is the unit of meaning; changing one is a new requirement."""
    i = data.draw(st.integers(min_value=0, max_value=len(ws) - 1))
    other = data.draw(st.sampled_from(WORDS))
    assume(other != ws[i])
    changed = list(ws)
    changed[i] = other
    assert clause_version(" ".join(ws)) != clause_version(" ".join(changed))


@settings(max_examples=60, deadline=None)
@given(st.integers(min_value=2, max_value=7), st.data())
def test_resolution_terminates_on_any_supersede_graph(n, data):
    """C-7.4 — cycles included: resolve returns for every id, and lint returns a report."""
    edges = data.draw(st.lists(st.tuples(st.integers(1, n), st.integers(1, n)), max_size=12))
    lines = ["# Contract: G", ""]
    for i in range(1, n + 1):
        lines.append(f"- **C-1.{i}** — WHEN step {i} THE SYSTEM SHALL act.")
        for a, b in edges:
            if a == i and b != i:
                lines.append(f"  - superseded-by: C-1.{b}")
    contract = parse("\n".join(lines) + "\n")
    for c in contract.clauses:
        assert isinstance(contract.resolve(c.id), tuple)
    assert isinstance(lint(contract), tuple)


@settings(max_examples=100, deadline=None)
@given(st.text(max_size=400))
def test_arbitrary_text_raises_nothing_but_the_parse_error(text):
    """C-7.5 — contract.md is untrusted input; the only failure it may cause is the parse
    error the gate knows how to report."""
    try:
        parse(text)
    except ContractParseError:
        pass


@settings(max_examples=60, deadline=None)
@given(st.sampled_from(["pytest", "python -m pytest"]),
       st.lists(st.tuples(st.sampled_from(WORDS), st.sampled_from(WORDS)), min_size=1, max_size=3,
                unique=True),
       st.lists(st.sampled_from(["-q", "-v", "-p no:cacheprovider", "--tb=short"]),
                max_size=3, unique=True),
       st.data())
def test_batching_keeps_prefix_and_nodes_equal_to_the_tokens(prog, pairs, opts, data):
    """C-7.6 — prefix plus nodes is the token multiset of the command: nothing is dropped,
    nothing is invented, and the nodes are exactly the nodes."""
    nodes = [f"tests/test_{a}.py::test_{b}" for a, b in pairs]
    tail = nodes + opts
    order = data.draw(st.permutations(tail))
    cmd = " ".join([prog] + order)
    key = batch_key(cmd)
    assert key is not None
    prefix, got = key
    assert sorted(list(prefix) + list(got)) == sorted(shlex.split(cmd))
    assert set(got) == set(nodes)
