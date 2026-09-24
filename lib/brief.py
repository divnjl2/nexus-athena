"""The senior's brief (C-8.4): a stronger reader's plan for a task the executor could not
land — where to cut, which function, what to avoid — carried in the next packet. The
brief holds no code: the executor types, the senior reads. AI21's junior/senior/principal
pipeline is the reference; here the senior is the 27B at low effort, the junior the 9B.

PURE throughout.
"""
from __future__ import annotations

import re

SECTION = "## Brief from the senior"


def brief_prompt(packet_text: str, checkpoint_text: str = "") -> str:
    """The question to the senior: the packet as the executor saw it, the last checkpoint
    when there is one, and the request for a plan without code."""
    parts = ["# Brief this task for a smaller executor", "",
             "You are the senior reader. A smaller model will type the change; you will not. "
             "Read the task below and, when there is one, the checkpoint of its failed attempts.",
             "", "## The task as the executor sees it", "", packet_text.strip()]
    if checkpoint_text and checkpoint_text.strip():
        parts += ["", "## What the executor tried and how it failed", "", checkpoint_text.strip()]
    parts += ["", "## What to answer",
              "Write a brief of at most 15 lines, no code and do not write code blocks: "
              "(1) the exact file and function or class to change, and where in it (after which definition, "
              "inside which branch); (2) the smallest edit that makes the red spec green, in words; "
              "(3) what the failed attempts did wrong, if any, and what to avoid; "
              "(4) which existing helper to reuse instead of rewriting. Nothing else."]
    return "\n".join(parts) + "\n"


def clean_brief(raw: str) -> str:
    """The brief as it goes into the packet: fenced code removed, chatter and a trailing
    DONE dropped, blank when nothing useful remains."""
    text = re.sub(r"```.*?```", "", raw or "", flags=re.DOTALL)
    lines = []
    for line in text.splitlines():
        s = line.rstrip()
        if not s.strip():
            if lines and lines[-1] != "":
                lines.append("")
            continue
        low = s.strip().lower()
        if low in ("done", "done."):
            continue
        if not lines and re.match(r"^(sure|certainly|here is|here's|okay|ok)\b", low):
            continue
        lines.append(s)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines).strip()


def packet_with_brief(pk: dict, brief: str) -> dict:
    """The packet plus the senior's brief as its own section; an empty brief leaves the
    packet untouched (the same object)."""
    if not (brief or "").strip():
        return pk
    text = pk["text"].rstrip("\n") + "\n\n" + SECTION + "\n" + brief.strip() + "\n"
    return {**pk, "text": text, "chars": len(text), "brief": brief.strip(),
            "over_budget": len(text) > pk.get("budget_chars", len(text) + 1)}
