"""L2 boundary: deliver a candidate environment fix as a pull request/patch and STOP. This
module holds NO apply credential to any shared or production environment — applying a fix
requires a recorded human approval (R8.1/R8.2). The injected `vcs` client is asked to open a
PR, never to apply/merge."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvFixPR:
    branch: str
    files: tuple[str, ...]
    url: str


class ApplyNotPermitted(Exception):
    """The agent never applies a fix to a shared/production environment; only a
    human-approved apply can."""


def open_env_fix_pr(vcs, *, branch, files) -> EnvFixPR:
    """`vcs` must expose `open_pr(branch, files) -> url`. It is never asked to apply or merge."""
    url = vcs.open_pr(branch, list(files))
    return EnvFixPR(branch=branch, files=tuple(files), url=url)


def apply_env_fix(pr: EnvFixPR, *, approval=None) -> dict:
    """R8.2: refuse to apply an environment fix without a recorded human approval."""
    if not approval or not approval.get("approved_by"):
        raise ApplyNotPermitted("environment fix requires human approval before apply")
    return {"applied": pr.branch, "approved_by": approval["approved_by"]}
