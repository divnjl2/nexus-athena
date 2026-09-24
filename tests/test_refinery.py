"""v3.13 refinery — a skip is not proof; a green workspace reaches the target only through
admit, rebase, check, fast-forward.

Each test is the executable spec of one C-1.* or C-2.* clause in
features/refinery-layer/contract.md. The git specs run against a real temporary repository:
the refinery takes `run(argv, cwd) -> (code, output)` and never imports subprocess itself.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

from lib.scenario_parser import parse as parse_scenarios

SCENARIO = parse_scenarios("""# Scenarios: Demo

### S1.1 — y
- **verifies:** C-1.1
- **run_cmd:** `python -m pytest tests/test_x.py::test_y -q`
- **Given** a
- **When** b
- **Then** c
""")[0]

TS = "2026-09-24T12:00:00+00:00"


# --- C-1: a skip is not proof ----------------------------------------------------------

def test_a_check_that_skipped_is_red_even_at_exit_zero():
    """C-1.1 — exit 0 with a skipped or absent test is red in the verdict; a non-pytest check
    keeps its exit code."""
    from lib.dispatch import pytest_outcome, verdict
    before, after = {"lib/x.py": (1, 1)}, {"lib/x.py": (2, 1)}
    cmd = "python -m pytest tests/test_x.py::test_y -q"

    skipped = verdict(before, after, [{"cmd": cmd, "exit": 0, "tail": "1 skipped in 0.01s"}])
    assert skipped["green"] is False and skipped["passed"] is False
    assert "skip" in skipped["reason"].lower()
    assert [r["cmd"] for r in skipped["red"]] == [cmd]

    empty = verdict(before, after, [{"cmd": cmd, "exit": 0, "tail": "no tests ran in 0.01s"}])
    assert empty["green"] is False

    mixed = verdict(before, after, [{"cmd": cmd, "exit": 0, "tail": "2 passed, 1 skipped in 0.30s"}])
    assert mixed["green"] is False

    green = verdict(before, after, [{"cmd": cmd, "exit": 0, "tail": "1 passed in 0.01s"}])
    assert green["green"] is True and green["passed"] is True

    shell = verdict(before, after, [{"cmd": "echo ok", "exit": 0, "tail": "ok"}])
    assert shell["green"] is True

    o = pytest_outcome("2 passed, 1 skipped in 0.30s")
    assert (o["passed"], o["skipped"]) == (2, 1)
    o = pytest_outcome("1 failed, 3 passed, 2 errors in 1.00s")
    assert (o["passed"], o["failed"], o["errors"]) == (3, 1, 2)
    assert pytest_outcome("ok")["passed"] == 0


def test_a_skipped_node_in_the_runners_report_is_not_passed():
    """C-1.2 — a junit testcase carrying <skipped> attributes to a SpecResult that is not
    passed and whose tail names the skip."""
    from lib.spec_runner import attribute, parse_junit
    xml = ('<testsuites><testsuite name="pytest">'
           '<testcase classname="tests.test_x" name="test_y" time="0.010">'
           '<skipped type="pytest.skip" message="not on this box"/></testcase>'
           '</testsuite></testsuites>')
    cases = parse_junit(xml)
    assert cases, "the junit parser must still read the report"
    res = attribute(SCENARIO, cases)
    assert res.passed is False
    assert res.exit_code != 0
    assert "skip" in res.output_tail.lower()

    ok_xml = xml.replace('<skipped type="pytest.skip" message="not on this box"/>', "")
    assert attribute(SCENARIO, parse_junit(ok_xml)).passed is True


def test_a_spec_command_exiting_zero_with_a_skip_is_not_passed():
    """C-1.3 — through the per-command executor seam, exit 0 with a skipped or absent test is
    not passed; exit 0 with a passed test is."""
    from lib.spec_runner import run_specs

    def skipping(cmd, *, cwd, timeout):
        return 0, "1 skipped in 0.01s"

    def empty(cmd, *, cwd, timeout):
        return 0, "no tests ran in 0.01s"

    def passing(cmd, *, cwd, timeout):
        return 0, "1 passed in 0.01s"

    assert run_specs((SCENARIO,), executor=skipping)[0].passed is False
    assert run_specs((SCENARIO,), executor=empty)[0].passed is False
    assert run_specs((SCENARIO,), executor=passing)[0].passed is True


# --- C-2: the merge queue --------------------------------------------------------------

def _git(argv, cwd):
    """The injected runner: real git, identity and line endings pinned for the test."""
    if argv and argv[0] == "git":
        argv = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false",
                "-c", "commit.gpgsign=false", *argv[1:]]
    p = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _repo(base: pathlib.Path):
    """A repository on `master` with a.txt and b.txt, and a worktree on branch `lane`."""
    base.mkdir(parents=True, exist_ok=True)
    repo = base / "repo"
    repo.mkdir()
    assert _git(["git", "init", "-q", "-b", "master"], repo)[0] == 0
    (repo / "a.txt").write_text("base\n", encoding="utf-8")
    (repo / "b.txt").write_text("base\n", encoding="utf-8")
    _git(["git", "add", "."], repo)
    assert _git(["git", "commit", "-q", "-m", "base"], repo)[0] == 0
    wt = base / "wt"
    assert _git(["git", "worktree", "add", "-q", "-b", "lane", str(wt)], repo)[0] == 0
    return repo, wt


def _commit(cwd: pathlib.Path, name: str, text: str, msg: str):
    (cwd / name).write_text(text, encoding="utf-8")
    _git(["git", "add", name], cwd)
    assert _git(["git", "commit", "-q", "-m", msg], cwd)[0] == 0


def _rev(cwd, ref="HEAD") -> str:
    return _git(["git", "rev-parse", ref], cwd)[1].strip()


def test_an_offer_is_admitted_only_on_a_green_last_record():
    """C-2.1 — the last record of the task decides; its words come back in the reason."""
    from lib.refinery import admit
    red = {"task": "T1.1", "executor": "local-27b", "landed": True, "green": False,
           "passed": False, "iteration": 1}
    green = {"task": "T1.1", "executor": "local-27b", "landed": True, "green": True,
             "passed": True, "iteration": 2}
    other = {"task": "T1.2", "executor": "local-27b", "landed": True, "green": True,
             "passed": True, "iteration": 1}

    yes = admit([red, green, other], "T1.1")
    assert yes["ok"] is True and "green" in yes["reason"]

    no = admit([green, red], "T1.1")
    assert no["ok"] is False and "not green" in no["reason"]

    none = admit([other], "T1.1")
    assert none["ok"] is False and "no record" in none["reason"]

    assert admit([], "T1.1")["ok"] is False
    # the workspace narrows the record: another executor's later red run elsewhere is not
    # this worktree's verdict, and a record without a workspace still counts
    here = dict(green, workspace="D:/w/ref-9")
    elsewhere = dict(red, executor="pi-27b", workspace="D:/w/ref-27")
    assert admit([here, elsewhere], "T1.1", workspace="D:/w/ref-9")["ok"] is True
    assert admit([here, elsewhere], "T1.1")["ok"] is False
    assert admit([here, elsewhere], "T1.1", workspace="D:/w/ref-27")["ok"] is False
    assert admit([green, elsewhere], "T1.1", workspace="D:\\w\\ref-9")["ok"] is True


def test_a_conflicting_rebase_is_aborted_and_the_files_named(tmp_path):
    """C-2.2 — on a real repository a conflicting rebase is aborted, refused and names the
    file; a clean one lands on top of the target."""
    from lib.refinery import conflicts_from, rebase

    repo, wt = _repo(tmp_path / "one")
    _commit(wt, "a.txt", "lane\n", "lane edits a")
    _commit(repo, "a.txt", "master\n", "master edits a")
    r = rebase(_git, str(wt), "master")
    assert r["ok"] is False
    assert r["conflicts"] == ["a.txt"]
    assert "a.txt" in r["reason"]
    # nothing left in progress: a second abort has nothing to abort
    assert _git(["git", "rebase", "--abort"], wt)[0] != 0
    assert (wt / "a.txt").read_text(encoding="utf-8") == "lane\n"

    repo2, wt2 = _repo(tmp_path / "two")
    _commit(wt2, "a.txt", "lane\n", "lane edits a")
    _commit(repo2, "b.txt", "master\n", "master edits b")
    r2 = rebase(_git, str(wt2), "master")
    assert r2["ok"] is True and r2["conflicts"] == []
    assert _git(["git", "merge-base", "--is-ancestor", "master", "HEAD"], wt2)[0] == 0
    assert (wt2 / "b.txt").read_text(encoding="utf-8") == "master\n"

    assert conflicts_from("CONFLICT (content): Merge conflict in a.txt\n"
                          "CONFLICT (modify/delete): dir/b.py deleted in HEAD\n") == ["a.txt", "dir/b.py"]


def test_a_failing_contract_refuses_the_offer_with_its_first_cause():
    """C-2.3 — over gate-shaped verdicts, empty when every contract holds, else the first
    failing contract and its first cause."""
    from lib.refinery import first_failure
    ok = [{"contract": "features/a/contract.md", "report": {"passed": True}}]
    assert first_failure(ok) == ""

    bad = ok + [{"contract": "features/b/contract.md",
                 "report": {"passed": False, "first_cause": "ledger has red specs"}}]
    s = first_failure(bad)
    assert "features/b/contract.md" in s and "ledger has red specs" in s

    err = [{"contract": "features/c/contract.md", "error": "ParseError: bad clause",
            "report": {"passed": False, "first_cause": "check could not run"}}]
    s = first_failure(err)
    assert "features/c/contract.md" in s and "check could not run" in s

    assert first_failure([]) == ""


def test_the_target_is_fast_forwarded_to_the_workspace_head_or_refused(tmp_path):
    """C-2.4 — on a real repository the target ref moves to the workspace head when it is an
    ancestor, and the offer is refused, naming the fast-forward, when it is not."""
    from lib.refinery import fast_forward

    repo, wt = _repo(tmp_path / "one")
    _commit(wt, "a.txt", "lane\n", "lane edits a")
    old = _rev(repo, "master")
    r = fast_forward(_git, str(wt), "master")
    assert r["ok"] is True
    assert r["head"] == _rev(wt) == _rev(repo, "master")
    assert r["old"] == old

    repo2, wt2 = _repo(tmp_path / "two")
    _commit(wt2, "a.txt", "lane\n", "lane edits a")
    _commit(repo2, "b.txt", "master\n", "master edits b")
    before = _rev(repo2, "master")
    r2 = fast_forward(_git, str(wt2), "master")
    assert r2["ok"] is False
    assert "fast-forward" in r2["reason"]
    assert _rev(repo2, "master") == before


def test_an_offer_ends_in_a_merge_record_and_a_refusal_returns_the_task_to_bd():
    """C-2.5 — the record carries task, executor, stage, ok, reason and ts; the bd command
    reopens the task with the stage and reason in its notes."""
    from lib.refinery import bd_return_command, merge_record, parse_merges
    rec = merge_record("T2.1", "local-27b", "check", False,
                       "features/x/contract.md: ledger has red specs", ts=TS)
    assert rec["task"] == "T2.1" and rec["executor"] == "local-27b"
    assert rec["stage"] == "check" and rec["ok"] is False and rec["ts"] == TS
    assert "ledger has red specs" in rec["reason"]

    done = merge_record("T2.1", "local-27b", "fast-forward", True, "master -> abc123", ts=TS)
    assert done["ok"] is True and done["stage"] == "fast-forward"

    cmd = bd_return_command("athena", "T2.1", "check", "features/x/contract.md: ledger has red specs")
    assert cmd[:3] == ["bd", "update", "athena:athena:T2.1"]
    assert cmd[cmd.index("--status") + 1] == "open"
    note = cmd[cmd.index("--append-notes") + 1]
    assert "check" in note and "ledger has red specs" in note

    text = "\n".join(json.dumps(m) for m in (rec, done)) + "\nnot json\n\n"
    assert [m["stage"] for m in parse_merges(text)] == ["check", "fast-forward"]


def test_metrics_report_merged_green_dispatches_per_executor_and_refusal_stages():
    """C-2.6 — per executor — distinct tasks that went green, how many of them merged, and the
    refusals by stage; the render names them."""
    from lib.refinery import merge_metrics, merge_record, render_merge_metrics
    disp = [
        {"task": "T1.1", "executor": "local-27b", "green": True},
        {"task": "T1.1", "executor": "local-27b", "green": True},     # a second green run of the same task
        {"task": "T1.2", "executor": "local-27b", "green": True},
        {"task": "T1.3", "executor": "local-27b", "green": False},
        {"task": "T2.1", "executor": "claude", "green": True},
    ]
    merges = [
        merge_record("T1.1", "local-27b", "fast-forward", True, "master -> 1", ts=TS),
        merge_record("T1.2", "local-27b", "check", False, "features/x/contract.md: red", ts=TS),
        merge_record("T2.1", "claude", "rebase", False, "conflicts: a.txt", ts=TS),
    ]
    rep = merge_metrics(disp, merges)
    assert rep["local-27b"] == {"green": 2, "merged": 1, "refused": {"check": 1}}
    assert rep["claude"] == {"green": 1, "merged": 0, "refused": {"rebase": 1}}

    text = render_merge_metrics(rep)
    assert "local-27b" in text and "merged" in text and "check" in text
    assert "(no merge recorded yet)" in render_merge_metrics({})
