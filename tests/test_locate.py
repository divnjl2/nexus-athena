"""v3.15 localisation — a repo map cheap enough for a small window, and votes over files.

Executable spec of C-8.2 in features/executor-layer/contract.md.
"""
from __future__ import annotations


def test_a_repo_map_is_built_from_definitions_and_file_votes_are_merged(tmp_path):
    """C-8.2 — the map lists each Python file with its top-level definitions and line count,
    within a character budget, skipping vendored dirs; votes from several localiser samples
    merge by count then by first mention; a reply that is not a list yields nothing."""
    from lib.locate import merge_votes, parse_files_reply, repo_map
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "a.py").write_text("import os\n\ndef alpha():\n    pass\n\nclass Beta:\n    def run(self):\n        pass\n", encoding="utf-8")
    (tmp_path / "lib" / "b.py").write_text("def gamma(x):\n    return x\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.py").write_text("def never():\n    pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")

    text = repo_map(str(tmp_path), budget_chars=10000)
    assert "lib/a.py" in text and "alpha" in text and "Beta" in text and "gamma" in text
    assert "node_modules" not in text and "README" not in text
    assert "8 lines" in text or "(8)" in text

    tight = repo_map(str(tmp_path), budget_chars=40)
    assert len(tight) <= 60 and tight.rstrip().endswith("...")

    assert parse_files_reply('["lib/a.py", "lib/b.py"]') == ["lib/a.py", "lib/b.py"]
    assert parse_files_reply('Sure. ```json\n["lib/b.py"]\n```') == ["lib/b.py"]
    assert parse_files_reply("- lib/a.py\n- lib/b.py\n") == ["lib/a.py", "lib/b.py"]
    assert parse_files_reply("I do not know") == []
    assert parse_files_reply('["C-7.2", "athena.py", "not a path"]') == ["athena.py"]   # measured: a sample answered the clause id

    merged = merge_votes([["lib/a.py", "lib/b.py"], ["lib/b.py"], ["lib/b.py", "lib/c.py"]], top=2)
    assert merged == ["lib/b.py", "lib/a.py"]
    assert merge_votes([], top=5) == []
