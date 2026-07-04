"""v4 executor port — the `implements` edge (commit->task), executor-agnostic (Seam 11)."""
from lib.ast import Plan, Phase, Task
from lib.executor import ExecutorResult, Executor, validate_results, implements_commands
from lib.seams import seam_implements_backed


def _plan(*ids):
    return Plan("Demo Feature", "", (),
                (Phase("phase1", "p", "g", (), "",
                       tuple(Task(id=i, title="x", success_check="run") for i in ids)),))


def test_any_object_with_the_contract_is_an_executor():
    class Fake:                         # NOT importing anything Athena-specific — pure duck type
        name = "fake"

        def implement(self, task):
            return ExecutorResult(task, "abc1234", True, "fake")

    assert isinstance(Fake(), Executor)          # Hermes/OpenHands/ClaudeCode plug in the same way


def test_validate_flags_empty_and_fake_sha():
    issues = validate_results([
        ExecutorResult("T1.1", "", True),            # empty
        ExecutorResult("T1.2", "xyz", True),         # not hex
        ExecutorResult("T1.3", "a1b2c3d", True),     # real
    ])
    assert any("T1.1" in i for i in issues)
    assert any("T1.2" in i for i in issues)
    assert not any("T1.3" in i for i in issues)


def test_implements_commands_pins_edge_and_closes_passing_task():
    cmds = implements_commands(
        [ExecutorResult("T1.1", "a1b2c3d4e5f6", True, "claude_code")], slug="demo-feature")
    joined = [" ".join(c) for c in cmds]
    assert any("kind:commit" in j for j in joined)
    assert any("--type implements" in j and "athena:demo-feature:T1.1" in j for j in joined)
    assert any("executor:claude_code" in j for j in joined)
    assert any(j.startswith("bd close") for j in joined)


def test_failing_check_gets_edge_but_no_close():
    cmds = implements_commands([ExecutorResult("T1.1", "a1b2c3d4", False)], slug="demo-feature")
    joined = [" ".join(c) for c in cmds]
    assert any("--type implements" in j for j in joined)
    assert not any(j.startswith("bd close") for j in joined)


def test_seam_fails_on_fake_sha():
    r = seam_implements_backed(_plan("T1.1"), [ExecutorResult("T1.1", "", True)])
    assert r.passed is False


def test_seam_fails_on_phantom_task():
    r = seam_implements_backed(_plan("T1.1"), [ExecutorResult("T9.9", "a1b2c3d", True)])
    assert r.passed is False and "not in the plan" in r.issues[0]


def test_seam_passes_on_real_sha_to_real_task():
    r = seam_implements_backed(_plan("T1.1"), [ExecutorResult("T1.1", "a1b2c3d4e5", True, "hermes")])
    assert r.passed is True and r.issues == ()
