"""L2: draft a candidate fix (compose patch / env var / config diff) for an EnvIssue. The LLM
call is injected; the default is a deterministic, always-non-empty patch skeleton, so the
generator is testable and always hands back a reviewable candidate."""
from __future__ import annotations

from qa_integration.agent.envfix_finder import EnvIssue


def generate_fix(issue: EnvIssue, *, llm=None) -> str:
    body = llm(issue) if llm is not None else _skeleton(issue)
    if not body.strip():
        raise ValueError("generated fix must not be empty")
    return body


def _skeleton(issue: EnvIssue) -> str:
    return (
        f"# candidate fix for dependency '{issue.dependency}' ({issue.target_kind})\n"
        f"# target: {issue.file}:{issue.line}\n"
        f"# cause: {issue.detail}\n"
        f"# REVIEW: a human must verify and approve this before it is applied (R8.1/R8.2).\n"
    )
