"""v3.5 the binding guard — a spec must prove the clause it NAMES.

An audit found C-8.1 (cobertura source-root resolution) bound to `test_is_test_classifier`,
a test about something else entirely. The clause was reported as proved for months of
commits. Root cause: the generator's regex used `.*?` under DOTALL, so it skipped a whole
function body and paired one function NAME with a LATER clause docstring.

This guard closes the class rather than the instance: every binding in scenarios.md is
resolved to the actual pytest node and the node's docstring must name the same clause.
"""
from __future__ import annotations

import ast
import pathlib
import re

FEATURE = pathlib.Path(__file__).resolve().parents[1] / "features" / "contract-layer"
_BLOCK = re.compile(
    r"### (S[\d.]+).*?\n- \*\*verifies:\*\* (\S+).*?\n(?:.*?\n)?- \*\*run_cmd:\*\* `([^`]+)`")


def _bindings():
    return _BLOCK.findall(FEATURE.joinpath("scenarios.md").read_text(encoding="utf-8"))


def test_every_spec_resolves_to_a_test_that_names_the_same_clause():
    """C-11.19 — a binding nobody checks is how a clause gets reported as proved by a test
    that never mentions it."""
    repo = FEATURE.parents[1]
    problems = []
    for spec_id, clause, cmd in _bindings():
        node = next((tok for tok in cmd.split() if "::" in tok), "")
        path, _, func = node.partition("::")
        target = repo / path
        if not node or not target.exists():
            problems.append(f"{spec_id}: run_cmd names no reachable pytest node ({cmd})")
            continue
        tree = ast.parse(target.read_text(encoding="utf-8"))
        fn = next((n for n in tree.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func),
                  None)
        if fn is None:
            problems.append(f"{spec_id}: {path} has no {func}")
            continue
        doc = ast.get_docstring(fn) or ""
        if not doc.startswith(clause + " "):
            problems.append(f"{spec_id} verifies {clause} but {func} documents {doc[:12]!r}")
    assert not problems, "mis-bound specs:\n  " + "\n  ".join(problems)


def test_the_guard_would_notice_a_mis_binding():
    """C-11.20 — a guard that cannot fail proves nothing; this is its negative control."""
    repo = FEATURE.parents[1]
    spec_id, clause, cmd = _bindings()[0]
    node = next(tok for tok in cmd.split() if "::" in tok)
    path, _, func = node.partition("::")
    tree = ast.parse((repo / path).read_text(encoding="utf-8"))
    fn = next(n for n in tree.body
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func)
    doc = ast.get_docstring(fn) or ""
    assert doc.startswith(clause + " "), "sanity: the first binding is correct"
    # the same comparison against a DIFFERENT clause must fail — that is the whole check
    assert not doc.startswith("C-99.99 ")
