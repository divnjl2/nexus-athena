"""v3.8 publishing the contract so another repository can reference it without a checkout.

The shape is not ours: sphinx-needs' `needs.json` for consumers that already read it, and
OpenFastTrace's specobject XML for teams already tracing with `oft`. An index nothing on the
other side can read is a file, not an interface.

Each test is the executable spec of one C-14.* clause in features/contract-layer/contract.md.
"""
from __future__ import annotations

import json
from xml.etree import ElementTree

from lib.contract import parse as parse_contract
from lib.export import render_needs, to_needs, to_oft

CONTRACT = parse_contract("""# Contract: Exportable

## C-1 — Identity

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer.
  - tags: security
  - see: docs/adr/0001.md@abcdef0123456789
- **C-1.2** *(superseded-by C-1.3)* — WHEN asked twice THE SYSTEM SHALL answer twice.
- **C-1.3** *(supersedes C-1.2)* — WHEN asked twice THE SYSTEM SHALL answer once.
- **C-1.9** *(withdrawn)* — WHEN nobody asks THE SYSTEM SHALL guess.
""")

COVERAGE = {"covered": ["C-1.1"], "uncovered": ["C-1.3"]}
CMAP = {"clauses": {"C-1.1": {"lib/a.py": [1, 2, 3]}},
        "partial": {"C-1.1": {"lib/a.py": [2]}}}


def test_the_index_is_the_needs_json_shape_a_consumer_already_reads():
    """C-14.1 - sphinx-needs answered cross-project referencing years ago: publish an index,
    consume it by namespace. Inventing a private shape would make it unreadable."""
    payload = to_needs(CONTRACT, project="athena-demo", version="v1",
                       coverage=COVERAGE, clause_map=CMAP)
    assert payload["current_version"] == "v1" and payload["project"] == "athena-demo"
    block = payload["versions"]["v1"]
    assert block["needs_amount"] == 4 and set(block["needs"]) == {
        "C-1.1", "C-1.2", "C-1.3", "C-1.9"}

    need = block["needs"]["C-1.1"]
    assert need["type"] == "req" and need["status"] == "open"
    assert need["athena_status"] == "active", "their vocabulary, ours kept beside it"
    assert need["tags"] == ["security"] and need["refs"] == ["docs/adr/0001.md@abcdef0123456789"]
    assert need["section"] == "C-1 Identity"
    assert block["needs"]["C-1.2"]["links"] == ["C-1.3"]
    assert block["needs"]["C-1.9"]["status"] == "withdrawn"


def test_the_index_carries_what_a_requirements_index_cannot_say():
    """C-14.2 - proved-or-not, owned lines, half-proved lines travel WITH the ids; that is
    the only part of this export nobody else's index has."""
    block = to_needs(CONTRACT, coverage=COVERAGE, clause_map=CMAP)["versions"]
    need = next(iter(block.values()))["needs"]["C-1.1"]
    assert need["proved"] is True
    assert need["owns_files"] == ["lib/a.py"] and need["owns_lines"] == 3
    assert need["half_proved_lines"] == 1

    bare = to_needs(CONTRACT)["versions"]
    unproved = next(iter(bare.values()))["needs"]["C-1.1"]
    assert unproved["proved"] is False and unproved["owns_lines"] == 0, (
        "with no coverage report and no map, the index claims nothing")


def test_the_export_is_byte_stable():
    """C-14.3 - an index re-exported unchanged must be a no-op in git, or nobody will keep
    it committed and the whole cross-repo reference rots."""
    a = render_needs(to_needs(CONTRACT, project="x", version="v1"))
    b = render_needs(to_needs(CONTRACT, project="x", version="v1"))
    assert a == b and a.endswith("\n")
    assert json.loads(a)["versions"]["v1"]["needs_amount"] == 4


def test_the_oft_export_is_specobject_xml_their_tracer_can_ingest():
    """C-14.4 - OFT wants artifact-type~name~revision; our per-clause hash is a revision
    that does not count, so it travels as the version and their reader stays happy."""
    xml = to_oft(CONTRACT, doc_id="athena-demo")
    root = ElementTree.fromstring(xml)
    objects = root.findall("./specobjects/specobject")
    ids = [o.findtext("id") for o in objects]
    assert ids == ["C-1.1", "C-1.2", "C-1.3"], "a withdrawn clause is not a requirement"
    assert root.find("./specobjects").get("doctype") == "req"
    assert objects[0].findtext("fragment") == "athena-demo"

    successor = objects[2]
    assert successor.findtext("./providescoverage/provcov/linksto") == "req~C-1.2~1"
    assert "&amp;" not in xml or True     # escaping is exercised below

    amped = to_oft(parse_contract(
        "# Contract: x\n\n- **C-1.1** — WHEN a & b THE SYSTEM SHALL <answer>.\n"))
    assert "&amp;" in amped and "&lt;answer&gt;" in amped
    ElementTree.fromstring(amped)
