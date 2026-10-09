"""Executable specs for the frozen real-task corpus."""
import copy

import pytest

from evals.self_improve.corpus import acceptance, fingerprint, inputs, select, verify


def _rows():
    return [{"instance_id": f"repo{i}__task{j}", "repo": f"org/repo{i}",
             "base_commit": f"sha{i}{j}", "problem_statement": f"bug {i}/{j}",
             "hints_text": "", "FAIL_TO_PASS": [f"test_{i}_{j}"],
             "PASS_TO_PASS": [], "test_patch": f"diff {i}/{j}",
             "image": f"image-{i}-{j}", "eval_script": f"pytest test_{i}_{j}",
             "environment_setup_commit": f"env{i}{j}", "eval_type": "pytest",
             "log_parser": "pytest"}
            for i in range(10) for j in range(5)]


def test_stratified_corpus_has_40_real_task_slots_and_separate_holdout():
    """C-1.4: a fixed selection assigns three development and one holdout task per repo."""
    rows = _rows()
    manifest = select(rows)
    assert len(manifest["tasks"]) == 40
    assert sum(t["split"] == "development" for t in manifest["tasks"]) == 30
    assert sum(t["split"] == "holdout" for t in manifest["tasks"]) == 10
    assert manifest == select(list(reversed(rows)))
    assert len({t["id"] for t in manifest["tasks"]}) == 40


def test_pinned_corpus_rejects_changed_inputs_and_acceptance():
    """C-1.2: drift in the issue or independent gate invalidates the frozen corpus."""
    rows = _rows()
    manifest = select(rows)
    verify(manifest, rows)
    for field, value in (("problem_statement", "changed"),
                         ("test_patch", "changed"), ("base_commit", "changed"),
                         ("image", "changed"), ("eval_script", "changed")):
        changed = copy.deepcopy(rows)
        changed[0][field] = value
        with pytest.raises(ValueError):
            verify(manifest, changed)
    assert fingerprint(inputs(rows[0])) != fingerprint(acceptance(rows[0]))


def test_corpus_fails_closed_on_insufficient_repository_diversity():
    """C-1.5: an incomplete source cannot silently become a smaller benchmark."""
    with pytest.raises(ValueError):
        select(_rows()[:-5])
