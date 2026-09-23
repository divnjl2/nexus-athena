"""v3.9 the judge's steps as provenance: two calls, and the reasoning gets an id.

The 30k self-revision loop was cured by giving the thinking a place to END (measured: 32s and
1067 tokens against 932s and 30475). That split made the reasoning a first-class artifact, and
an artifact with an id belongs in the same graph as the clauses — as an INDEX, never as a
blob store, and never with an edge that means proof.

Each test is the executable spec of one C-16.* clause in features/contract-layer/contract.md.
"""
from __future__ import annotations

from lib.judge import Pair, judgement_record, stage1_prompt, stage2_prompt, strip_think
from lib.judgement_graph import (clause_key, compile_judgements, judgement_key, scenario_key,
                                 summarize)

PAIR = Pair(id="C-1.1/S1.1", clause_id="C-1.1",
            clause_text="WHEN asked THE SYSTEM SHALL answer.",
            spec_id="S1.1", spec_source="def test_x():\n    assert answer() == 1\n",
            label="proves")

REASONING = "<think>The test asserts the return value, so breaking it fails the test."


def test_the_thinking_is_given_a_place_to_end():
    """C-16.1 - the run was not being cut by a token budget; it was running into the context
    ceiling and being truncated mid-sentence, which is a lie the lane tells silently."""
    system, user = stage1_prompt(PAIR)
    plain_system, plain_user = system[:-len(system) + system.index("\n\nWork through")], user
    assert "<think>" in system and "</think>" in system
    assert "do not answer after it" in system
    assert user == plain_user, "the question itself is untouched — same pinned prompt"
    assert "max_tokens" not in system and "words" not in system.split("Work through")[1], (
        "the reasoning is given a terminator, not a budget")


def test_the_verdict_call_gets_the_analysis_as_data_and_only_a_shape_to_fill():
    """C-16.2 - a grammar applied from the first token measures the grammar; applied to the
    second call it constrains nothing but the answer."""
    _, user = stage2_prompt(PAIR, REASONING)
    assert user.startswith("Below is your own analysis")
    assert "breaking it fails the test" in user, "the analysis travels as data"
    assert "<think>" not in user, "the tags do not"
    assert '"verdict": "vacuous"|"proves"' in user and "counterexample" in user

    # count inside the ANALYSIS section only — the schema line carries an x of its own
    # ("counterexample"), and an assertion that trips over that is measuring the wrong thing
    long = "<think>" + ("x" * 9000)
    _, big = stage2_prompt(PAIR, long)
    carried = big.split("ANALYSIS:\n", 1)[1].split("\n\nAnswer JSON:", 1)[0]
    assert carried == "x" * 6000, "the TAIL is kept: the verdict lives at the end"


def test_a_stop_sequence_eats_the_closing_tag_and_that_is_not_malformed():
    """C-16.3 - stage 1 normally comes back OPEN, because the server stops ON the tag;
    treating that as broken would throw away the only thing the call produced."""
    assert strip_think("<think>abc") == "abc"
    assert strip_think("<think>abc</think>trailing") == "abc"
    assert strip_think("no tags at all") == "no tags at all"
    assert strip_think("") == ""


def test_the_record_keeps_the_verdict_and_a_handle_on_the_reasoning():
    """C-16.4 - the text stays in the decisions artifact; what travels is a fingerprint."""
    rec = judgement_record(PAIR, REASONING, {"decision": "proves", "reason": "asserts the value"})
    assert rec["pair"] == "C-1.1/S1.1" and rec["clause"] == "C-1.1" and rec["spec"] == "S1.1"
    assert rec["decision"] == "proves" and rec["reason"] == "asserts the value"
    assert len(rec["reasoning_sha"]) == 16 and rec["reasoning_chars"] > 20
    assert "reasoning" not in rec or rec.get("reasoning") is None, "no text in the record"

    empty = judgement_record(PAIR, "", {"decision": "error"})
    assert empty["reasoning_sha"] == "" and empty["reasoning_chars"] == 0


def test_a_judgement_node_is_an_index_and_never_claims_proof():
    """C-16.5 - `related`, never `validates`: the edge that means "this proves that" is
    reserved for evidence a runner produced, and a model is not a runner."""
    rec = judgement_record(PAIR, REASONING, {"decision": "vacuous",
                                             "counterexample": "pytest -k x",
                                             "reason": "asserts nothing"})
    known = frozenset({clause_key("demo", "C-1.1"), scenario_key("demo", "S1.1")})
    cmds = compile_judgements([rec], slug="demo", existing_keys=known,
                              pin={"model": "qwen9b-opus", "prompt_sha": "abc123",
                                   "variant": "v2"})
    argvs = [list(c.argv) for c in cmds]

    create = argvs[0]
    assert create[:2] == ["bd", "create"]
    assert "kind:judgement" in create and "decision:vacuous" in create
    assert f"reasoning:{rec['reasoning_sha']}" in create
    assert "judge:model:qwen9b-opus" in create and "judge:variant:v2" in create
    body = create[create.index("--description") + 1]
    assert "counterexample: pytest -k x" in body
    assert "kept in the decisions artifact" in body and REASONING[8:20] not in body

    edges = [a for a in argvs if a[:3] == ["bd", "dep", "add"]]
    assert len(edges) == 2 and all(a[-2:] == ["--type", "related"] for a in edges)
    assert all("validates" not in a for a in argvs)
    assert {a[4] for a in edges} == known


def test_a_judgement_already_in_the_graph_is_emitted_no_second_time():
    """C-16.7 - idempotent against what the graph already holds, so re-running a judge run
    over a corpus it has already recorded costs nothing and duplicates nothing."""
    rec = judgement_record(PAIR, REASONING, {"decision": "proves"})
    assert compile_judgements([rec], slug="demo",
                              existing_keys=frozenset({judgement_key("demo", PAIR.id)})) == ()

    rep = summarize([rec, judgement_record(PAIR, "", {"decision": "error"})])
    assert rep["judgements"] == 2 and rep["by_decision"] == {"error": 1, "proves": 1}
    assert rep["with_reasoning"] == 1 and rep["reasoning_chars"] > 20


def test_a_judgement_whose_end_the_graph_lacks_is_still_recorded():
    """C-16.8 - a judgement about a clause this project never compiled is worth keeping;
    inventing the missing end would be worse than an orphan node."""
    rec = judgement_record(PAIR, REASONING, {"decision": "proves"})
    lonely = compile_judgements([rec], slug="demo", existing_keys=frozenset())
    argvs = [list(c.argv) for c in lonely]
    assert len(argvs) == 1 and argvs[0][:2] == ["bd", "create"], (
        "the node is kept; the edges are not invented")

    half = compile_judgements([rec], slug="demo",
                              existing_keys=frozenset({clause_key("demo", "C-1.1")}))
    edges = [list(c.argv) for c in half if list(c.argv)[:3] == ["bd", "dep", "add"]]
    assert len(edges) == 1 and edges[0][4] == clause_key("demo", "C-1.1"), (
        "the end that exists is linked; the one that does not is left alone")


def test_a_generation_that_cycles_is_told_apart_from_one_that_is_merely_long():
    """C-16.9 - the runaway is not long thinking, it is REPEATED thinking; that difference
    is what makes stopping it legitimate where a token budget would not be."""
    from lib.judge import looping

    cycle = ("So the test passes.\nSo the test is vacuous.\n\n"
             "Wait, I need to check if the requirement is violated.\n"
             "If I change the system to report for all clauses, it is not violated here.\n") * 12
    assert looping(cycle), "this is the verbatim shape the ceiling-hitting transcripts had"

    progress = "".join(f"Step {i}: a distinct aspect of the requirement, considered once.\n"
                       for i in range(80))
    assert not looping(progress), "long is not the same as looping"
    assert not looping("too short to judge") and not looping("")

    # conservative on purpose: two repeats of a span are not yet a cycle
    twice = ("the same sentence repeated, with nothing else around it at all. " * 2)
    assert not looping(twice * 1, probe=60, repeats=3)
