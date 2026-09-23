"""v3.3 the reverse direction — the frame judging the WORDING its authors produce.

The structural lint checks the wiring (ids, refs, cycles). It cannot see the two ways an
LLM reliably ruins a requirement: CONFLATION ("...SHALL validate the input and SHALL log the
error" is two requirements wearing one id, and no single spec proves it) and INFLATION
(near-duplicate clauses that look like coverage). `critique()` is that second pass.

Each test is the executable spec of one C-7.* clause in features/contract-layer/contract.md.
"""
from __future__ import annotations

import pathlib
import re

import athena
from lib.contract import critique, lint, parse


def _codes(text: str, clause: str | None = None) -> list[str]:
    found = critique(parse(text))
    return [f["code"] for f in found if clause is None or f["clause"] == clause]


def test_a_clause_with_two_obligations_is_reported_as_not_atomic():
    """C-7.1 — one clause proves one thing; two SHALLs cannot be proved by one spec."""
    text = """# Contract: X

- **C-1.1** — WHEN input arrives THE SYSTEM SHALL validate it and SHALL log a rejection.
- **C-1.2** — WHEN input arrives THE SYSTEM SHALL validate it.
"""
    assert "not_atomic" in _codes(text, "C-1.1")
    assert _codes(text, "C-1.2") == []
    # the word SHALL used as a NOUN must not count as an obligation (the rules about the
    # rules have to be writable)
    meta = """# Contract: X

- **C-1.1** — WHEN a clause states more than one SHALL obligation THE SYSTEM SHALL report it.
"""
    assert "not_atomic" not in _codes(meta, "C-1.1")


def test_obligations_joined_with_and_shall_are_reported_as_conjoined():
    """C-7.2 — the conjunction is the tell; ordinary lists are not."""
    conjoined = """# Contract: X

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer and shall also record the answer.
"""
    assert "conjoined" in _codes(conjoined, "C-1.1")
    listing = """# Contract: X

- **C-1.1** — WHEN asked THE SYSTEM SHALL return the id, the status, and the timestamp.
"""
    assert "conjoined" not in _codes(listing, "C-1.1")


def test_unprovable_wording_is_reported_as_vague():
    """C-7.3 — "properly" cannot be a run_cmd; quoted mentions are exempt."""
    vague = """# Contract: X

- **C-1.1** — WHEN input arrives THE SYSTEM SHALL handle it properly, as needed.
"""
    assert "vague" in _codes(vague, "C-1.1")
    mention = """# Contract: X

- **C-1.1** — WHEN a clause uses wording such as "properly" THE SYSTEM SHALL report it.
"""
    assert "vague" not in _codes(mention, "C-1.1")


def test_identical_wording_is_reported_as_duplication_not_coverage():
    """C-7.4 — inflation looks like coverage until you compare the sentences."""
    text = """# Contract: X

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer.
- **C-2.7** — WHEN asked THE SYSTEM SHALL answer.
"""
    found = critique(parse(text))
    dupes = [f for f in found if f["code"] == "duplicate_of"]
    assert [d["clause"] for d in dupes] == ["C-2.7"]
    assert "C-1.1" in dupes[0]["detail"]


def test_superseded_and_withdrawn_wording_is_exempt_from_the_quality_pass():
    """C-7.5 — policing dead text would punish the discipline the format asks for."""
    text = """# Contract: X

- **C-1.1** *(superseded-by C-1.2)* — WHEN asked THE SYSTEM SHALL answer and SHALL log it.
- **C-1.2** — WHEN asked THE SYSTEM SHALL answer.
- **C-1.3** *(withdrawn)* — WHEN asked THE SYSTEM SHALL handle it properly.
"""
    assert _codes(text) == []


def test_wording_findings_are_advisory_unless_the_caller_asks_for_a_gate(tmp_path, capsys):
    """C-7.6 — a linter that fails the build on style gets switched off."""
    p = tmp_path / "contract.md"
    p.write_text("""# Contract: X

- **C-1.1** — WHEN input arrives THE SYSTEM SHALL validate it and SHALL log a rejection.
""", encoding="utf-8")
    c = parse(p.read_text(encoding="utf-8"))
    assert lint(c) == ()                      # the WIRING is fine
    assert critique(c)                        # the WORDING is not

    assert athena.main(["contract", "lint", str(p)]) == 0
    advisory = capsys.readouterr().out
    assert "not_atomic" in advisory and '"passed": true' in advisory.lower()

    assert athena.main(["contract", "lint", str(p), "--strict"]) == 1
    assert "not_atomic" in capsys.readouterr().out


def test_a_multi_line_note_stays_out_of_the_normative_text_and_version():
    """C-7.7 — a note leaking into the sentence corrupts both the wording and the pin."""
    without = """# Contract: X

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer.
"""
    with_note = """# Contract: X

- **C-1.1** — WHEN asked THE SYSTEM SHALL answer.
  - note: this was decided in 2026 after a long argument that
    spilled onto a second line and must not become a requirement.
"""
    a, b = parse(without).by_id("C-1.1"), parse(with_note).by_id("C-1.1")
    assert b.text == a.text
    assert b.version == a.version              # the pin does not move because of a note
    assert "argument" not in b.text


BAD = """# Contract: Known-bad

- **C-1.1** — WHEN input arrives THE SYSTEM should validate it.
- **C-1.2** — WHEN input arrives THE SYSTEM SHALL accept JSON and/or XML.
- **C-1.3** — WHEN input is rejected the error SHALL be logged.
- **C-1.4** — WHEN input arrives THE SYSTEM SHALL validate it (TBD which fields).
- **C-1.5** — WHEN the suite runs THE SYSTEM SHALL finish quickly by batching the specs.
- **C-1.6** — WHEN under load THE SYSTEM SHALL stay as responsive as possible.
- **C-1.7** — WHEN input arrives THE SYSTEM SHALL validate it and SHALL log a rejection.
- **C-1.8** — Some prose with no obligation at all.
- **C-1.9** — WHEN input arrives THE SYSTEM SHALL validate it and SHALL log a rejection.
- **C-1.10** — WHEN a request arrives over the network interface during the business day and the account is in good standing and no maintenance window is active THE SYSTEM SHALL record the request in the audit journal together with the actor, the timestamp, the originating address and the correlation identifier.
"""


def test_a_preference_is_not_an_obligation():
    """C-7.9 — should/may/can leave "is it required?" unanswerable (RFC 2119 keeps them
    for the non-binding case)."""
    assert "weak_modal" in _codes(BAD, "C-1.1")
    assert "weak_modal" not in _codes(BAD, "C-1.2")


def test_and_or_makes_the_obligation_undecidable():
    """C-7.10 — "and/or" hides two requirements behind one sentence."""
    assert "and_or" in _codes(BAD, "C-1.2")


def test_a_passive_obligation_without_an_actor_is_reported():
    """C-7.11 — "SHALL be logged" — by whom? A spec needs someone to hold responsible."""
    assert "ambiguous_passive" in _codes(BAD, "C-1.3")
    assert "ambiguous_passive" not in _codes(BAD, "C-1.2")


def test_a_placeholder_marks_the_requirement_as_unwritten():
    """C-7.12 — TBD is an admission, and it must not sit silently in a live clause."""
    assert "placeholder" in _codes(BAD, "C-1.4")


def test_a_clause_that_dictates_the_mechanism_is_reported():
    """C-7.13 — "by ...ing" is HOW, and HOW belongs in design; this frame made exactly that
    mistake in draft clause C-3.9 and measurement refuted the mechanism."""
    assert "names_mechanism" in _codes(BAD, "C-1.5")
    assert "names_mechanism" not in _codes(BAD, "C-1.7")


def test_an_unquantified_quality_has_no_exit_code():
    """C-7.14 — "as responsive as possible" cannot be a run_cmd."""
    assert "unquantified" in _codes(BAD, "C-1.6")


def test_every_rule_the_linter_defines_fires_on_the_known_bad_contract():
    """C-7.15 — a check that can never fire is decoration; this is the dead-rule guard."""
    import lib.contract as contract_mod

    fired = {f["code"] for f in critique(parse(BAD))}
    # every code the module can emit, harvested from the source so a NEW rule that nobody
    # exercises fails this spec instead of rotting quietly
    src = pathlib.Path(contract_mod.__file__).read_text(encoding="utf-8")
    defined = set(re.findall(r'"code":\s*"(\w+)"', src)) | set(
        re.findall(r'code = "(\w+)" if', src)) | set(re.findall(r'else "(\w+)"', src))
    missing = defined - fired
    assert not missing, f"rules that never fire on known-bad input: {sorted(missing)}"


def test_the_frames_own_contract_passes_its_own_quality_bar():
    """C-7.8 — the rules are applied to the file that states them, not only to examples."""
    own = pathlib.Path(__file__).resolve().parents[1] / "features" / "contract-layer" / "contract.md"
    contract = parse(own.read_text(encoding="utf-8"))
    assert lint(contract) == ()
    assert critique(contract) == (), "the contract layer must obey the rules it defines"


def test_a_clause_without_an_ears_trigger_is_reported_as_non_conforming():
    """C-7.16 — "THE SYSTEM SHALL log errors" hides WHEN it must, so nothing can trigger
    the check; a ubiquitous "THE SYSTEM SHALL ..." opening is legal EARS and passes."""
    implicit = """# Contract: X

- **C-1.1** — The service SHALL retry the request.
"""
    assert "no_ears_shape" in _codes(implicit, "C-1.1")
    ubiquitous = """# Contract: X

- **C-1.1** — THE SYSTEM SHALL retry the request at most three times.
"""
    assert "no_ears_shape" not in _codes(ubiquitous, "C-1.1")
