"""v3.5 the binding guard — a spec must prove the clause it NAMES.

An audit found C-8.1 (cobertura source-root resolution) bound to `test_is_test_classifier`,
a test about something else entirely. The clause was reported as proved for months of
commits. Root cause: the generator's regex used `.*?` under DOTALL, so it skipped a whole
function body and paired one function NAME with a LATER clause docstring.

This guard closes the class rather than the instance: every binding in every feature's
scenarios.md is resolved to the actual pytest node and the node's docstring must name the
same clause. (v3.10: every `features/*/` that carries a contract. v3.11: a case spec
resolves to its JSON file, whose `clause` must match.)
"""
from __future__ import annotations

import ast
import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
FEATURES = sorted(d for d in (REPO / "features").iterdir()
                  if (d / "contract.md").exists() and (d / "scenarios.md").exists())
_HEAD = re.compile(r"^### (S[\d.]+)", re.MULTILINE)
_VERIFIES = re.compile(r"^- \*\*verifies:\*\* (\S+)", re.MULTILINE)
_RUN = re.compile(r"^- \*\*run_cmd:\*\* `([^`]+)`", re.MULTILINE)
_CASE = re.compile(r"^- \*\*case:\*\* `([^`]+)`", re.MULTILINE)


def _bindings():
    out = []
    for feature in FEATURES:
        text = feature.joinpath("scenarios.md").read_text(encoding="utf-8")
        heads = list(_HEAD.finditer(text))
        for i, h in enumerate(heads):
            block = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
            v, r, c = _VERIFIES.search(block), _RUN.search(block), _CASE.search(block)
            out.append((feature.name, h.group(1), v.group(1) if v else "",
                        r.group(1) if r else "", c.group(1) if c else ""))
    return out


def _problem(feature, spec_id, clause, cmd, case):
    if case:
        target = REPO / case
        if not target.exists():
            return f"{feature} {spec_id}: case file {case} is missing"
        documented = json.loads(target.read_text(encoding="utf-8")).get("clause", "")
        if documented != clause:
            return f"{feature} {spec_id} verifies {clause} but its case documents {documented!r}"
        return ""
    node = next((tok for tok in cmd.split() if "::" in tok), "")
    path, _, func = node.partition("::")
    target = REPO / path
    if not node or not target.exists():
        return f"{feature} {spec_id}: run_cmd names no reachable pytest node ({cmd})"
    tree = ast.parse(target.read_text(encoding="utf-8"))
    fn = next((n for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == func), None)
    if fn is None:
        return f"{feature} {spec_id}: {path} has no {func}"
    doc = ast.get_docstring(fn) or ""
    if not doc.startswith(clause + " "):
        return f"{feature} {spec_id} verifies {clause} but {func} documents {doc[:12]!r}"
    return ""


def test_every_spec_resolves_to_a_test_that_names_the_same_clause():
    """C-11.19 — a binding nobody checks is how a clause gets reported as proved by a test
    that never mentions it."""
    assert FEATURES, "at least one feature carries a contract"
    problems = [p for p in (_problem(*b) for b in _bindings()) if p]
    assert not problems, "mis-bound specs:\n  " + "\n  ".join(problems)


def test_the_guard_would_notice_a_mis_binding():
    """C-11.20 — a guard that cannot fail proves nothing; this is its negative control."""
    feature, spec_id, clause, cmd, case = next(b for b in _bindings() if not b[4])
    assert _problem(feature, spec_id, clause, cmd, case) == "", "sanity: the first binding is correct"
    # the same comparison against a DIFFERENT clause must fail — that is the whole check
    assert _problem(feature, spec_id, "C-99.99", cmd, case) != ""
    case_feature = next((b for b in _bindings() if b[4]), None)
    if case_feature:
        f, s, c, r, k = case_feature
        assert _problem(f, s, c, r, k) == "" and _problem(f, s, "C-99.99", r, k) != ""
