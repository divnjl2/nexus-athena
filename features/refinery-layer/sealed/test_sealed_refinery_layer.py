"""Sealed acceptance tier of the refinery layer (C-2.8 of the refinery, C-1.4 and C-1.5 of the foundry): run only
by the refinery's check, never in a packet or a dispatch verdict; an executor that edits this file is
never green. Second readings of clauses the visible specs already cover, phrased independently.
"""
from __future__ import annotations


def test_sealed_exit_zero_is_not_proof_and_admission_reads_only_the_last_record():
    """C-1.1, C-2.1 (sealed) — a skipped test or nothing run is red at exit zero and a real failure
    needs no extra reason; an offer is admitted on the last record of its task alone, and only the
    records of its own workspace count when one is named."""
    from lib.dispatch import skip_reason
    from lib.refinery import admit
    assert "skipped" in skip_reason({"exit": 0, "tail": "3 passed, 1 skipped in 0.1s"})
    assert skip_reason({"exit": 0, "tail": "no tests ran in 0.01s"})
    assert skip_reason({"exit": 1, "tail": "1 failed"}) == "" and skip_reason({"exit": 0, "tail": "2 passed in 0.1s"}) == ""
    recs = [{"task": "T1", "passed": True, "green": True, "workspace": "D:/w/T1"}, {"task": "T1", "passed": False, "green": False, "workspace": "D:/w/T1"}]
    assert admit(recs, "T1")["ok"] is False
    assert admit(list(reversed(recs)), "T1")["ok"] is True
    assert admit([], "T1")["ok"] is False
    elsewhere = [{"task": "T1", "passed": True, "green": True, "workspace": "D:/bench/T1"}]
    assert admit(elsewhere, "T1", workspace="D:/w/T1")["ok"] is False and admit(elsewhere, "T1")["ok"] is True


def test_sealed_the_records_keep_their_shape_and_the_reasons_name_what_they_refuse():
    """C-2.5, C-2.7, C-2.1 (sealed) — the merge record opens with its schema and carries its
    timestamp; the bd note names the stage; a refusal for want of records names the task and the
    workspace; the verify verdict has the dispatch verdict's shape and says why it is red; the
    rendered metrics open with their header and say so when empty (the golden of foundry C-9.6)."""
    from lib.refinery import MERGE_SCHEMA, admit, bd_return_command, merge_record, render_merge_metrics, verify_verdict
    rec = merge_record("T1", "pi-9b", "check", False, "spec red", ts="2026-09-27T00:00:00")
    assert list(rec) == ["schema", "ts", "task", "executor", "stage", "ok", "reason"] and rec["schema"] == MERGE_SCHEMA
    assert bd_return_command("athena", "T1", "check", "spec red")[-1] == "refinery refused at check: spec red"
    assert admit([], "T1", workspace="D:/w/T1")["reason"] == "no record for task T1 in D:/w/T1"
    v = verify_verdict([], [], spec_files=())
    assert set(v) == {"landed", "green", "passed", "changed_files", "deleted_files", "review_flags", "red", "reason"}
    assert v["landed"] is False and v["green"] is False and "nothing to merge" in v["reason"] and "silence is not proof" in v["reason"]
    assert render_merge_metrics({}) == "# merge - per executor, from the merge record" + chr(10) + "  (no merge recorded yet)"

