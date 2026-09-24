"""v3.15 the senior's brief — a reading of the task by a stronger reader, carried in the next
packet; no code, only where to cut and what to avoid.

Executable spec of C-8.4 in features/executor-layer/contract.md.
"""
from __future__ import annotations


def test_a_brief_is_asked_from_the_packet_and_the_checkpoint_and_carried_in_the_next_packet():
    """C-8.4 — the brief prompt holds the packet and the last checkpoint and asks for a plan
    without code; the brief is carried in the packet as its own section, ahead of the spec
    status; an empty brief changes nothing."""
    from lib.brief import brief_prompt, clean_brief, packet_with_brief
    packet = "# Task T1.1 — do b\n\n## The requirement\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\n"
    checkpoint = "## Checkpoint from iteration 3 (task T1.1)\nStill red:\n  - pytest x exit 1 -> AssertionError\n"
    prompt = brief_prompt(packet, checkpoint)
    assert packet.strip() in prompt and checkpoint.strip() in prompt
    assert "no code" in prompt.lower() or "do not write code" in prompt.lower()
    assert "file" in prompt.lower() and "function" in prompt.lower()
    assert brief_prompt(packet, "").count("Checkpoint") == 0

    raw = "Sure, here is the plan:\n\n1. In lib/x.py, function `b`, add the branch.\n2. Do not touch the tests.\n\n```python\nprint('never')\n```\nDONE"
    brief = clean_brief(raw)
    assert "lib/x.py" in brief and "```" not in brief and "print(" not in brief
    assert not brief.lower().startswith("sure")
    assert clean_brief("   ") == "" and clean_brief("DONE") == ""

    pk = {"text": packet, "chars": len(packet), "budget_chars": 36000, "over_budget": False}
    with_brief = packet_with_brief(pk, brief)
    assert "## Brief from the senior" in with_brief["text"]
    assert with_brief["text"].index("## The requirement") < with_brief["text"].index("## Brief from the senior")
    assert "lib/x.py" in with_brief["text"] and with_brief["chars"] == len(with_brief["text"])
    assert with_brief["brief"] == brief
    assert packet_with_brief(pk, "") is pk
