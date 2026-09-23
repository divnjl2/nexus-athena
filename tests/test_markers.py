"""v3.8 code -> clause markers: StrictDoc's notation, this frame's verification.

The notation is borrowed on purpose (`@relation(ID, scope=...)`); what is ours is refusing
to take the annotation at its word. A marker is a CLAIM, and the clause map is the evidence:
if no spec of that clause executes the lines the marker points at, the annotation is
decorative and the gate says so.

Each test is the executable spec of one C-13.* clause in features/contract-layer/contract.md.
"""
from __future__ import annotations

from lib.contract import parse as parse_contract
from lib.markers import check, claimed_lines, pair_ranges, scan

CONTRACT = parse_contract("""# Contract: Markers

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer.
- **C-1.2** — WHEN asked twice THE SYSTEM SHALL answer twice.
- **C-1.9** *(withdrawn)* — WHEN nobody asks THE SYSTEM SHALL guess.
""")

SRC = '''"""Module doing a thing.

@relation(C-1.1, scope=file)
"""


class Answerer:
    """Answers.

    @relation(C-1.2, scope=class)
    """

    def answer(self):
        """One answer.

        @relation(C-1.1, scope=function)
        """
        return 1

    def twice(self):
        # @relation(C-1.2, scope=range_start)
        first = 1
        second = 2
        # @relation(C-1.2, scope=range_end)
        return first + second


def loose():
    # @relation(C-1.1, scope=line)

    return 42
'''


def test_the_marker_notation_is_strictdocs_and_is_read_whole():
    """C-13.1 - `@relation(ID, scope=...)` with ids comma-separated and the scope optional;
    a third notation for the oldest idea in requirements tracing would help nobody."""
    found = scan(SRC, path="lib/m.py")
    assert [(m["clause"], m["scope"], m["line"]) for m in found][:3] == [
        ("C-1.1", "file", 3), ("C-1.2", "class", 10), ("C-1.1", "function", 16)]
    assert {m["path"] for m in found} == {"lib/m.py"}

    # several ids in one marker become several rows; scope defaults to the NARROWEST claim
    multi = scan("# @relation(C-1.1, C-1.2)\nvalue = 1\n", path="x.py")
    assert [(m["clause"], m["scope"]) for m in multi] == [("C-1.1", "line"), ("C-1.2", "line")]
    assert scan("nothing here\n", path="x.py") == ()


def test_each_scope_resolves_to_the_lines_it_claims():
    """C-13.2 - the scopes are the granularity the clause map already speaks: a line, a
    function, a class, a range, a file."""
    found = scan(SRC, path="lib/m.py")
    by = {(m["clause"], m["scope"]): m for m in found}
    pairs = pair_ranges(found)

    assert claimed_lines(by[("C-1.1", "file")], SRC) == tuple(range(1, len(SRC.splitlines()) + 1))
    assert claimed_lines(by[("C-1.1", "function")], SRC) == (13, 14, 15, 16, 17, 18)
    assert claimed_lines(by[("C-1.2", "class")], SRC)[0] == 7  # the class stmt
    start = by[("C-1.2", "range_start")]
    assert claimed_lines(start, SRC, partner=pairs.get(id(start))) == (22, 23)
    # `line` labels the next NON-BLANK statement, so a blank line under the comment is fine
    assert claimed_lines(by[("C-1.1", "line")], SRC) == (31,)


def test_a_marker_the_map_does_not_back_is_decorative():
    """C-13.3 - the sharp one: an annotation is a claim, and if no spec of that clause
    executes the lines it points at, the traceability is decoration."""
    markers = scan(SRC, path="lib/m.py")
    sources = {"lib/m.py": SRC}
    cmap = {"schema": "athena.clause_map/5", "clauses": {
        "C-1.1": {"lib/m.py": [16, 17, 18]},      # only the `answer` body
        "C-1.2": {"lib/m.py": [22, 23]},          # only the range
    }}
    rep = check(markers, CONTRACT, cmap, sources)

    confirmed = {(r["clause"], r["scope"]) for r in rep["ok"]}
    assert ("C-1.1", "function") in confirmed and ("C-1.2", "range_start") in confirmed
    assert ("C-1.1", "line") in {(r["clause"], r["scope"]) for r in rep["unowned"]}, (
        "line 31 is claimed but no spec of C-1.1 reaches it")
    assert rep["unowned"][0]["why"].startswith("no spec of this clause")
    assert not rep["passed"]


def test_unknown_retired_and_unresolvable_markers_are_reported_apart():
    """C-13.4 - four ways a marker can be wrong, and they call for four different fixes."""
    src = ('# @relation(C-9.9, scope=line)\nx = 1\n'
           '# @relation(C-1.9, scope=line)\ny = 2\n'
           '# @relation(C-1.1, scope=function)\nz = 3\n')
    rep = check(scan(src, path="a.py"), CONTRACT, {"clauses": {}}, {"a.py": src})
    assert [r["clause"] for r in rep["unknown"]] == ["C-9.9"]
    assert [(r["clause"], r["status"]) for r in rep["retired"]] == [("C-1.9", "withdrawn")]
    assert [r["clause"] for r in rep["unresolved"]] == ["C-1.1"]
    assert "cannot resolve scope=function" in rep["unresolved"][0]["why"]
    assert rep["markers"] == 3 and not rep["passed"]

    # a source that was never read leaves only the markers that got past the contract
    # checks: an unknown or retired clause is decided without opening the file at all
    unread = check(scan(src, path="a.py"), CONTRACT, {"clauses": {}}, {})
    assert [r["why"] for r in unread["unresolved"]] == ["source not read"]
    assert len(unread["unknown"]) == 1 and len(unread["retired"]) == 1


def test_a_marker_shown_in_backticks_is_a_mention_not_a_marker():
    """C-13.5 - the same distinction the wording critique already draws. This module
    documents its own notation, and the first scan of this repository reported the EXAMPLES
    in its docstrings as three broken markers."""
    quoted = 'doc = "the notation is `@relation(C-1.1, scope=file)`"\nx = 1\n'
    assert scan(quoted, path="a.py") == ()

    fenced = ("Example:\n"
              "```\n"
              "# @relation(C-1.1, scope=line)\n"
              "```\n"
              "# @relation(C-1.2, scope=line)\n"
              "real = 1\n")
    live = scan(fenced, path="a.py")
    assert [(m["clause"], m["line"]) for m in live] == [("C-1.2", 5)], (
        "the fenced example is talked about; the bare one is asserted")
    assert claimed_lines(live[0], fenced) == (6,), "line numbers survive the blanking"
