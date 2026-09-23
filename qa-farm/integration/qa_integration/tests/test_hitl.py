"""Proves the HITL safety boundary (plan T6.3/T7.2 · scenarios S8.2/S8.3)."""
import pytest

from qa_integration.agent.envfix_pr import ApplyNotPermitted, EnvFixPR, apply_env_fix
from qa_integration.ci.hitl_manifest import manifest


def test_hitl_manifest_enumerates_points():
    ids = {p["id"] for p in manifest()["hitl"]}
    assert "approve-environment-fix" in ids
    assert "classify-ambiguous-flaky" in ids


def test_env_fix_requires_approval():
    pr = EnvFixPR(branch="qa/envfix-1", files=("docker-compose.yml",), url="http://pr/1")
    with pytest.raises(ApplyNotPermitted):
        apply_env_fix(pr, approval=None)
    ok = apply_env_fix(pr, approval={"approved_by": "dmitry"})
    assert ok["approved_by"] == "dmitry"
