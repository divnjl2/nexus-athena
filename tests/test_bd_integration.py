"""
Real-bd integration: compile -> execute (label->ID resolution) -> read-back seam ->
idempotency, against a real `bd` in a temp repo. Skipped if `bd` is not on PATH.

This catches the label-vs-ID contract drift that the fake-`run` unit tests cannot — it
is the test that surfaced the real bug: the compiler emits label-based --parent/--dep
references, but bd resolves those by issue ID, so bd_client.execute must substitute.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

from lib.plan_parser import parse
from lib.plan2beads import compile, _slugify
from lib.bd_client import execute, fetch_existing_keys
from lib import seams

BD = shutil.which("bd")
pytestmark = pytest.mark.skipif(BD is None, reason="bd not installed")
FIX = pathlib.Path(__file__).parent / "fixtures"


def _runner(cwd: pathlib.Path):
    def run(argv):
        argv = [BD if a == "bd" else str(a) for a in argv]
        return subprocess.run(argv, capture_output=True, text=True, cwd=str(cwd)).stdout
    return run


def test_real_bd_graph_materializes_and_is_idempotent(tmp_path):
    subprocess.run([BD, "init"], cwd=str(tmp_path), capture_output=True, text=True)
    run = _runner(tmp_path)

    plan = parse((FIX / "valid.md").read_text(encoding="utf-8"))
    slug = _slugify(plan.title)

    execute(compile(plan), run=run)   # label->ID resolution happens here

    issues = json.loads(run(["bd", "list", "--label", "athena", "--json"]) or "[]")
    assert len(issues) == 4           # 2 epics + 2 issues

    sr = seams.seam_graph_materialized(plan, issues, slug)
    assert sr.passed, sr.issues       # read-back: graph matches AST intent

    existing = fetch_existing_keys(slug, run=run)
    assert len(existing) == 4
    res2 = compile(plan, existing_keys=existing)
    assert not any(str(c).split()[:2] == ["bd", "create"] for c in res2.commands)  # idempotent no-op
