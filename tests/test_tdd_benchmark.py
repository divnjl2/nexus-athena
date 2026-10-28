"""TDD adapter contracts. Synthetic metadata only; never launches Git, Docker or models."""
import copy
import json
import pathlib
import zipfile

import pytest

from evals.tddbench.adapter import classify, filter_tdd, harness_command, prepare, public_input, select, summarize


def rows(n=40):
    return [{"instance_id": f"repo{i%5}__project-{i}", "repo": f"repo{i%5}/project", "base_commit": "a"*40,
             "problem_statement": "the expected outcome", "patch": "secret fix", "test_patch": "secret test",
             "version": "1", "FAIL_TO_PASS": ["hidden"], "hints_text": "secret hint"} for i in range(n)]


@pytest.fixture
def frozen(tmp_path):
    data = rows()
    dataset, membership, archive = [tmp_path / n for n in ("verified.json", "ids.txt", "archive.zip")]
    dataset.write_text(json.dumps(data))
    membership.write_text("\n".join(r["instance_id"] for r in data))
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("upstream/run_evaluation.py", "pass\n")
    dest = tmp_path / "run"
    manifest = prepare(str(dataset), str(membership), str(archive), str(dest))
    (dest / "run_evaluation.py").write_bytes(b"pass\n")
    return dest, manifest


def test_only_tdd_members_are_admitted():
    """C-1.1 - only reproducible, blind, executed evidence is credited."""
    data = rows()
    wanted = data[3]["instance_id"]
    assert filter_tdd(data, wanted) == [data[3]]
    with pytest.raises(ValueError, match="missing"):
        filter_tdd(data, "unknown__repo-1")
    with pytest.raises(ValueError, match="duplicate"):
        filter_tdd(data, wanted + "\n" + wanted)


def test_generator_inputs_never_contain_solutions(frozen):
    """C-1.2 - only reproducible, blind, executed evidence is credited."""
    root, _ = frozen
    for p in (root / "generator").glob("*.json"):
        for row in json.loads(p.read_text()):
            assert set(row) == {"instance_id", "repo", "base_commit", "problem_statement"}
            assert "secret" not in json.dumps(row)
    row = public_input({**rows(1)[0], "unexpected_gold": "private"})
    assert "unexpected_gold" not in row


def test_selection_is_frozen_distinct_and_disjoint(frozen):
    """C-1.3 - only reproducible, blind, executed evidence is credited."""
    root, manifest = frozen
    assert len(set(manifest["calibration_ids"])) == 5
    assert len(set(manifest["evaluation_ids"])) == 30
    assert not set(manifest["calibration_ids"]) & set(manifest["evaluation_ids"])
    chosen = select(rows(), 5, seed=20261024)
    assert chosen == select(list(reversed(rows())), 5, seed=20261024)
    assert len({r["repo"] for r in chosen}) == 5
    with pytest.raises(ValueError, match="overwrite"):
        prepare(str(root.parent / "verified.json"), str(root.parent / "ids.txt"), str(root.parent / "archive.zip"), str(root))


def test_missing_inputs_never_fall_back(tmp_path):
    """C-1.4 - only reproducible, blind, executed evidence is credited."""
    with pytest.raises(FileNotFoundError):
        prepare(str(tmp_path / "missing.json"), "missing", "missing", str(tmp_path / "run"))
    bad = rows(1)
    bad[0].pop("test_patch")
    with pytest.raises(ValueError, match="missing required"):
        filter_tdd(bad, bad[0]["instance_id"])
    with pytest.raises(ValueError, match="not enough"):
        select(rows(2), 3, seed=1)
    from evals.tddbench.adapter import fetch_verified
    calls = []
    def offline(request, **kwargs):
        calls.append(request.full_url)
        raise OSError("network unavailable")
    with pytest.raises(OSError, match="network unavailable"):
        fetch_verified(str(tmp_path / "out.json"), opener=offline)
    assert len(calls) == 1 and not (tmp_path / "out.json").exists()


def test_source_artifacts_are_fingerprinted(frozen):
    """C-1.5 - only reproducible, blind, executed evidence is credited."""
    root, m = frozen
    assert set(m["hashes"]) == {"dataset", "membership", "harness_archive"}
    assert all(len(v) == 64 for v in m["hashes"].values())
    assert len(m["artifacts"]) == 4
    for path, expected in m["artifacts"].items():
        from evals.tddbench.adapter import sha
        assert sha((root / path).read_bytes()) == expected


def test_harness_requires_explicit_git_authorization(frozen):
    """C-2.1 - only reproducible, blind, executed evidence is credited."""
    root, _ = frozen
    with pytest.raises(PermissionError, match="Git"):
        harness_command(str(root), str(root), git_authorized=False, run_id="calibration")
    cmd = harness_command(str(root), str(root), git_authorized=True, run_id="calibration")
    assert "tddbench.harness.run_evaluation" in cmd
    assert cmd[cmd.index("--max_workers")+1] == "1"
    assert cmd[cmd.index("--predictions_path")+1] == "gold"
    (root / "sealed" / "calibration.json").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        harness_command(str(root), str(root), git_authorized=True, run_id="calibration")


def good_report():
    return {"test_before_patch": {"test_bug": "FAILED", "test_old": "PASSED"},
            "test_after_patch": {"test_bug": "PASSED", "test_old": "PASSED"},
            "resolved": True, "final_score": 1.0, "cov_score": 1.0}


def test_errors_skips_and_missing_reports_are_incomplete():
    """C-2.2 - only reproducible, blind, executed evidence is credited."""
    assert classify(None)["state"] == "INCOMPLETE"
    assert classify({})["state"] == "INCOMPLETE"
    for status in ("ERROR", "SKIP", "SKIPPED", "UNKNOWN"):
        row = good_report()
        row["test_before_patch"]["test_bug"] = status
        assert classify(row)["state"] == "INCOMPLETE"


def test_fail_before_requires_same_test_to_pass_after():
    """C-2.3 - only reproducible, blind, executed evidence is credited."""
    assert classify(good_report())["state"] == "PASS"
    row = good_report()
    row["test_after_patch"].pop("test_bug")
    assert classify(row)["state"] == "INCOMPLETE"
    row = good_report()
    row["test_before_patch"]["test_bug"] = "PASSED"
    assert classify(row)["state"] == "FAIL"
    row = good_report()
    row["test_after_patch"]["test_bug"] = "FAILED"
    assert classify(row)["state"] == "FAIL"
    row = good_report()
    row["resolved"] = False
    assert classify(row)["state"] == "INCOMPLETE"


def test_summary_keeps_all_denominators(frozen):
    """C-2.4 - only reproducible, blind, executed evidence is credited."""
    root, m = frozen
    absent = summarize(str(root), "not-run")
    assert absent["selected"] == 5 and absent["evaluated"] == 0 and absent["incomplete"] == 5
    assert absent["state"] == "INCOMPLETE"
    p = root / "logs/run_evaluation/calibration/gold_initial" / m["calibration_ids"][0]
    p.mkdir(parents=True)
    (p / "report.json").write_text(json.dumps({m["calibration_ids"][0]: good_report()}))
    rep = summarize(str(root), "calibration")
    assert rep["pass"] == 1 and rep["incomplete"] == 4 and rep["selected"] == 5
    assert rep["evaluated"] == rep["pass"] + rep["fail"]


def test_gold_runs_are_always_calibration(frozen):
    """C-2.5 - only reproducible, blind, executed evidence is credited."""
    root, m = frozen
    assert m["calibration_is_model_performance"] is False
    assert summarize(str(root), "none")["is_model_performance"] is False
    with pytest.raises(ValueError, match="calibration"):
        harness_command(str(root), str(root), git_authorized=True, run_id="bad", mode="evaluation", predictions="gold")


def test_evaluation_predictions_are_validated_and_mounted(frozen):
    """C-3.1 - valid predictions use the mounted path and invalid submissions are rejected."""
    root, m = frozen
    selected = m['evaluation_ids']
    prediction = root / 'predictions.json'
    item = {'instance_id': selected[0], 'model_patch': 'a generated test patch'}
    prediction.write_text(json.dumps([item]))
    cmd = harness_command(str(root), str(root), git_authorized=True, run_id='model-direct',
                          mode='evaluation', predictions='predictions.json')
    assert cmd[cmd.index('--predictions_path') + 1] == '/bench/predictions.json'
    assert cmd[cmd.index('--dataset_name') + 1] == '/bench/sealed/evaluation.json'
    assert cmd[cmd.index('--instance_ids') + 1:] == selected
    for invalid in ([item, item], [{'instance_id': m['calibration_ids'][0], 'model_patch': 'x'}],
                    [{'instance_id': selected[0], 'model_patch': None}], [], {'bad': 'format'}):
        prediction.write_text(json.dumps(invalid))
        with pytest.raises(ValueError):
            harness_command(str(root), str(root), git_authorized=True, run_id='model',
                            mode='evaluation', predictions='predictions.json')
    outside = root.parent / 'outside.json'
    outside.write_text(json.dumps([item]))
    with pytest.raises(ValueError, match='inside'):
        harness_command(str(root), str(root), git_authorized=True, run_id='model',
                        mode='evaluation', predictions=str(outside))


def test_evaluation_cli_preserves_selection_and_denominators(frozen, capsys):
    """C-3.2 - it selects thirty evaluation instances and retains twenty-nine missing reports."""
    from evals.tddbench.__main__ import main
    root, m = frozen
    (root / 'predictions.jsonl').write_text(json.dumps({'instance_id': m['evaluation_ids'][0],
                                                       'model_patch': ''}) + '\n')
    assert main(['run', str(root), '--harness', str(root), '--run-id', 'direct',
                 '--git-authorized', '--mode', 'evaluation', '--predictions', 'predictions.jsonl']) == 0
    dry = json.loads(capsys.readouterr().out)
    assert dry['executed'] is False
    assert dry['command'][dry['command'].index('--instance_ids') + 1:] == m['evaluation_ids']
    p = root / 'logs/run_evaluation/direct/predictions' / m['evaluation_ids'][0]
    p.mkdir(parents=True)
    (p / 'report.json').write_text(json.dumps({m['evaluation_ids'][0]: good_report()}))
    assert main(['report', str(root), '--run-id', 'direct', '--mode', 'evaluation']) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['selected'] == 30 and result['pass'] == 1 and result['incomplete'] == 29
    assert result['mode'] == 'evaluation'
    with pytest.raises(ValueError):
        summarize(str(root), '../outside', mode='evaluation')
