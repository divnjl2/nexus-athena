"""
Fail-closed seam battery (codifies the live shakedown).

Every broken front must be CAUGHT at its seam — exit 1 with a SPECIFIC, debuggable issue
(breaks at the seam, not three stages later). Positives pass clean (exit 0) — no false
positives. This is the regression guard for the framework's whole premise: the glue's
boundary contracts hold.
"""
import json
import pathlib

import pytest

import athena

FIX = pathlib.Path(__file__).parent / "fixtures"

# (front, speckit, seam, needle-in-issue)
ADVERSARIAL = [
    ("cycle.md", "off", "ast_wellformed", "cycle"),            # compiler misses; seam catches
    ("bad_dep.md", "off", "ast_wellformed", "missing"),         # dep -> non-existent phase
    ("no_check.md", "off", "ast_wellformed", "success_check"),  # task missing the gate
    ("valid.md", "on", "speckit_schema", "Tasks"),             # plan.md fed as tasks.md -> drift
]

POSITIVE = [
    ("valid.md", "off", "ast_wellformed"),
    ("speckit_tasks.md", "on", "speckit_schema"),
    ("speckit_tasks.md", "on", "ast_wellformed"),
]


@pytest.mark.parametrize("front,sk,seam,needle", ADVERSARIAL)
def test_adversarial_caught_at_seam(front, sk, seam, needle, capsys):
    rc = athena.main(["--speckit", sk, "seam", seam, str(FIX / front)])
    assert rc == 1                                              # fail-closed
    out = json.loads(capsys.readouterr().out.strip())
    issue = (out.get("issues") or [out.get("error", "")])[0]
    assert needle in issue                                     # specific + debuggable


@pytest.mark.parametrize("front,sk,seam", POSITIVE)
def test_positive_passes_clean(front, sk, seam, capsys):
    rc = athena.main(["--speckit", sk, "seam", seam, str(FIX / front)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out.strip())["passed"] is True
