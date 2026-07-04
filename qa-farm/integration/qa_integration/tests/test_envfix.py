"""Proves the Env-Fix Proposal agent: find -> generate -> deliver, never apply
(plan T3.1/T3.2/T3.3 · scenario S8.1)."""
from qa_integration.agent.envfix_finder import EnvIssue, find_issue
from qa_integration.agent.envfix_generator import generate_fix
from qa_integration.agent.envfix_pr import EnvFixPR, open_env_fix_pr
from qa_integration.tools.dependency_health_gate import DependencyGateResult


class _FakeVCS:
    def __init__(self):
        self.opened = None
        self.applied = False

    def open_pr(self, branch, files):
        self.opened = (branch, tuple(files))
        return "http://pr/1"

    def apply(self, *a, **k):            # present, but the agent must NEVER call it
        self.applied = True


def test_finds_issue_target():
    gate = DependencyGateResult(False, ("postgres", "redis"), ("redis",),
                                "dependency unhealthy: redis")
    issues = find_issue(gate, locator=lambda dep: {
        "kind": "compose_service", "file": "docker-compose.yml", "line": 12,
        "detail": f"{dep} service block is misconfigured",
    })
    assert len(issues) == 1
    assert issues[0].dependency == "redis"
    assert issues[0].file == "docker-compose.yml" and issues[0].line == 12
    assert issues[0].target_kind == "compose_service"


def test_drafts_candidate_fix():
    issue = EnvIssue(dependency="redis", target_kind="compose_service",
                     file="docker-compose.yml", line=12, detail="redis service down")
    fix = generate_fix(issue)
    assert "redis" in fix and "docker-compose.yml" in fix and "12" in fix


def test_delivers_proposal_never_auto_applies():
    vcs = _FakeVCS()
    pr = open_env_fix_pr(vcs, branch="qa/envfix-1", files=["docker-compose.yml"])
    assert isinstance(pr, EnvFixPR) and pr.url == "http://pr/1"
    assert vcs.opened == ("qa/envfix-1", ("docker-compose.yml",))
    assert vcs.applied is False           # the agent performed no apply action
