"""Executable checks for safe baseline continuation."""
import pytest

from evals.self_improve.baseline_batch import cell_action


def test_resume_skips_proved_cells_and_never_overwrites_partial_attempts(tmp_path):
    """C-3.13: a resume cannot silently repeat an existing candidate or gate."""
    cell = {"task_id": "astropy__astropy-8872", "arm": "codex",
            "split": "development"}
    candidate = (tmp_path / "artifacts" / "development" /
                 cell["task_id"] / cell["arm"] / "1")
    assert cell_action(cell, set(), tmp_path) == "candidate"
    candidate.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="partial candidate"):
        cell_action(cell, set(), tmp_path)
    for name in ("candidate.json", "candidate.patch", "attempt.json", "input.json"):
        (candidate / name).write_text("preserved")
    assert cell_action(cell, set(), tmp_path) == "gate"
    (candidate / "gate").mkdir()
    with pytest.raises(RuntimeError, match="unfinished gate"):
        cell_action(cell, set(), tmp_path)
    assert cell_action(cell, {(cell["task_id"], cell["arm"])}, tmp_path) == "skip"
