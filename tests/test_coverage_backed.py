"""v3.2 coverage-backed provenance — the code->spec reverse leg (Seam 10 + trace_coverage)."""
from lib.ast import Plan, Phase, Task
from lib.coverage_backed import parse_coverage, trace_coverage, _is_test
from lib.seams import seam_coverage_backed

# pkg/a.py: covered (line 1 hit) with an uncovered branch on line 2.
# pkg/b.py: fully uncovered (line 1 hit=0).
COV = """<coverage>
 <packages><package><classes>
  <class filename="pkg/a.py" line-rate="0.5"><lines>
    <line number="1" hits="1"/>
    <line number="2" hits="1" branch="true" condition-coverage="50% (1/2)"/>
  </lines></class>
  <class filename="pkg/b.py" line-rate="0.0"><lines>
    <line number="1" hits="0"/>
  </lines></class>
 </classes></package></packages>
</coverage>"""


def _plan(*tasks):
    return Plan("t", "", (), (Phase("phase1", "p", "g", (), "", tuple(tasks)),))


def _task(tid, files, verifies):
    return Task(id=tid, title="x", success_check="run", verifies=verifies, files=files)


def test_is_test_classifier():
    assert _is_test("qa_unit/tests/test_x.py") and _is_test("pkg/foo_test.py")
    assert not _is_test("pkg/a.py")


def test_parse_covered_and_uncovered_branch():
    cov = parse_coverage(COV)
    assert cov.covered("pkg/a.py") is True
    assert cov.covered("pkg/b.py") is False               # no covered lines
    assert cov.files["pkg/a.py"].uncovered_branches == (2,)


def test_real_edge_is_proven():
    cov = parse_coverage(COV)
    plan = _plan(_task("T1", ("pkg/a.py", "tests/test_a.py"), ("S1",)))
    rep = trace_coverage(plan, cov)
    assert rep["proven"] == 1 and rep["unproven"] == 0


def test_fake_edge_is_unproven():
    cov = parse_coverage(COV)
    plan = _plan(_task("T2", ("pkg/b.py", "tests/test_b.py"), ("S2",)))   # b.py never covered
    rep = trace_coverage(plan, cov)
    assert rep["unproven"] == 1 and rep["proven"] == 0
    assert rep["replan_trigger"] == "satisfies_unproven"


def test_meta_task_without_source_or_verifies_is_ignored():
    cov = parse_coverage(COV)
    plan = _plan(
        _task("T3", ("tests/test_only.py",), ("S3",)),   # only a test file -> no edge to prove
        _task("T4", ("pkg/a.py",), ()),                  # no verifies -> no edge
    )
    rep = trace_coverage(plan, cov)
    assert rep["proven"] == 0 and rep["unproven"] == 0


def test_orphan_branch_is_a_spec_gap():
    cov = parse_coverage(COV)
    rep = trace_coverage(_plan(_task("T1", ("pkg/a.py",), ("S1",))), cov)
    assert "pkg/a.py:2" in rep["spec_gaps"]


def test_seam_fails_on_fake_edge():
    cov = parse_coverage(COV)
    plan = _plan(_task("T2", ("pkg/b.py",), ("S2",)))
    r = seam_coverage_backed(plan, cov)
    assert r.passed is False and "T2" in r.issues[0]


def test_seam_passes_when_edges_are_real():
    cov = parse_coverage(COV)
    plan = _plan(_task("T1", ("pkg/a.py",), ("S1",)))
    r = seam_coverage_backed(plan, cov)
    assert r.passed is True and r.issues == ()


# --- v3.3: the reverse leg made honest -----------------------------------------

COV_ROOTED = r"""<coverage>
 <sources><source>C:\repo\lib</source></sources>
 <packages><package><classes>
  <class filename="contract.py" line-rate="0.9"><lines>
    <line number="1" hits="1"/>
    <line number="2" hits="1" branch="true" condition-coverage="50% (1/2)"/>
  </lines></class>
 </classes></package></packages>
</coverage>"""


def test_coverage_paths_resolve_across_source_roots():
    """C-8.1 — cobertura strips the <source> root off every filename, so a plan that says
    `lib/contract.py` must still find `contract.py` — otherwise every edge reads as fake."""
    cov = parse_coverage(COV_ROOTED)
    assert cov.covered("lib/contract.py"), "the plan's path must resolve to the coverage entry"
    assert cov.covered("contract.py")
    assert cov.resolve("lib/contract.py").path == "lib/contract.py"
    assert cov.resolve("nowhere/other.py") is None


def test_an_ambiguous_basename_resolves_to_nothing():
    """C-8.3 — two files named the same must not be silently conflated; an unproven edge a
    human looks at beats a proven edge that is a guess."""
    ambiguous = parse_coverage("""<coverage>
 <packages><package><classes>
  <class filename="a/x.py" line-rate="1"><lines><line number="1" hits="1"/></lines></class>
  <class filename="b/x.py" line-rate="1"><lines><line number="1" hits="1"/></lines></class>
 </classes></package></packages>
</coverage>""")
    assert ambiguous.resolve("x.py") is None
    assert not ambiguous.covered("x.py")
    assert ambiguous.resolve("a/x.py") is not None      # an unambiguous path still resolves


def test_reverse_leg_separates_in_scope_gaps_from_unclaimed_code():
    """C-8.2 — code this contract never claimed is not a spec_gap; burying the real signal
    under another feature's branches is how a report becomes noise nobody reads."""
    plan = _plan(_task("T1", ("pkg/a.py",), ("S1",)))
    rep = trace_coverage(plan, parse_coverage(COV))
    assert rep["spec_gaps"] == ["pkg/a.py:2"]          # inside a claimed file
    assert rep["out_of_scope_gap_count"] == 0          # b.py has no uncovered BRANCH
    assert rep["unclaimed_files"] == ["pkg/b.py"]      # ...but it is still unclaimed
    assert rep["proven"] == 1 and rep["unproven"] == 0
