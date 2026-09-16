"""v3.10 the way in — one short document at the root, and names that disclose in order.

Each test is the executable spec of one C-4.* clause in features/core-layer/contract.md.
These specs read the repository itself: the entry document is a product artifact of this
repo the same way the binding guard's scenarios.md is.
"""
from __future__ import annotations

import argparse
import pathlib
import re

import athena

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _choices(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def test_the_root_has_an_entry_document_under_thirty_lines():
    """C-4.1 — one short document at the root leads to the core, the contract and the check."""
    entry = ROOT / "CLAUDE.md"
    assert entry.exists()
    text = entry.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 30, "an entry longer than a screen is a README"
    for needle in ("CORE.md", "contract.md", "athena.py check"):
        assert needle in text, needle


def test_design_history_lives_under_docs_history_not_the_root():
    """C-4.2 — file names are part of the disclosure order; history is not the way in."""
    assert list(ROOT.glob("athena-*plan*.md")) == []
    assert len(list((ROOT / "docs" / "history").glob("athena-*plan*.md"))) >= 7


def test_every_command_the_entry_names_is_one_the_cli_accepts():
    """C-4.3 — an entry that names a command the CLI rejects is rot on the first line."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    named = re.findall(r"python athena\.py ([a-z][a-z-]*)(?: ([a-z][a-z-]*))?", text)
    assert named, "the entry names at least one command"
    top = _choices(athena.build_parser())
    for cmd, sub in named:
        assert cmd in top, cmd
        nested = _choices(top[cmd])
        if sub and nested:
            assert sub in nested, f"{cmd} {sub}"
