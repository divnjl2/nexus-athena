"""Executable specs for the frozen real-task corpus."""
import copy

import pytest

from evals.self_improve.corpus import acceptance, fingerprint, inputs, select, verify


def _rows():
    return [{"instance_id": f"repo{i}__task{j}", "repo": f"org/repo{i}",
             "base_commit": f"sha{i}{j}", "problem_statement": f"bug {i}/{j}",
             "hints_text": "", "FAIL_TO_PASS": [f"test_{i}_{j}"],
             "PASS_TO_PASS": [], "test_patch": f"diff {i}/{j}"}
            for i in range(12) for j in range(4)]


def test_stratified_corpus_has_36_real_task_slots_and_separate_holdout():
    """C-1.1: a fixed selection assigns two development and one holdout task per repo."""
    rows = _rows()
    manifest = select(rows)
    assert len(manifest["tasks"]) == 36
    assert sum(t["split"] == "development" for t in manifest["tasks"]) == 24
    assert sum(t["split"] == "holdout" for t in manifest["tasks"]) == 12
    assert manifest == select(list(reversed(rows)))
    assert len({t["id"] for t in manifest["tasks"]}) == 36


def test_pinned_corpus_rejects_changed_inputs_and_acceptance():
    """C-1.2: drift in the issue or independent gate invalidates the frozen corpus."""
    rows = _rows()
    manifest = select(rows)
    verify(manifest, rows)
    for field, value in (("problem_statement", "changed"),
                         ("test_patch", "changed"), ("base_commit", "changed")):
        changed = copy.deepcopy(rows)
        changed[0][field] = value
        with pytest.raises(ValueError):
            verify(manifest, changed)
    assert fingerprint(inputs(rows[0])) != fingerprint(acceptance(rows[0]))


def test_corpus_fails_closed_on_insufficient_repository_diversity():
    """C-1.3: an incomplete source cannot silently become a smaller benchmark."""
    with pytest.raises(ValueError):
        select(_rows()[:-4])
