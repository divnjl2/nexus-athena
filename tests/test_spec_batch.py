"""v3.10 the fast lane — many specs, one process, every verdict still its own.

Each test is the executable spec of one C-6.* clause in features/core-layer/contract.md.
The process boundary (`spawn`) is injected: the fake records argv and writes the junit
report a batch asks for, so nothing here shells out.
"""
from __future__ import annotations

import pathlib

from lib.ast import Scenario
from lib.contract import parse
from lib.spec_runner import batch_key, plan_batches, run_specs


def _s(sid, clause="C-1.1", node=None):
    node = node or f"tests/test_x.py::{sid}"
    return Scenario(id=sid, requirement_key=clause, gwt_text="g",
                    run_cmd=f"python -m pytest {node} -q")


def _case(node, outcome="passed", t="0.010", msg="boom"):
    path, _, name = node.partition("::")
    return (path[:-3].replace("/", "."), name, outcome, t, msg)


def _junit(cases):
    body = ""
    for cls, name, outcome, t, msg in cases:
        if outcome == "passed":
            inner = ""
        elif outcome == "failed":
            inner = f'<failure message="{msg}">{msg}\nassert 1 == 2</failure>'
        else:
            inner = f'<skipped message="{msg}"/>'
        body += f'<testcase classname="{cls}" name="{name}" time="{t}">{inner}</testcase>'
    return ('<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" '
            f'tests="{len(cases)}">{body}</testsuite></testsuites>')


class Spawner:
    """A fake process runner: records argv; writes the junit file a batch asks for."""

    def __init__(self, report=None, single_code=0, aborted=False):
        self.calls = []
        self.report = report or {}
        self.single_code = single_code
        self.aborted = aborted

    def __call__(self, argv, *, cwd, timeout):
        self.calls.append(list(argv))
        junit = next((a for a in argv if a.startswith("--junitxml=")), None)
        if junit is None:
            node = next(a for a in argv if "::" in a)
            code = self.single_code(node) if callable(self.single_code) else self.single_code
            return code, f"ran {node}"
        out = pathlib.Path(junit[len("--junitxml="):])
        if self.aborted:
            out.write_text(_junit([]), encoding="utf-8")
            return 4, "ERROR: not found"
        cases = [self.report[n] for n in argv if n in self.report]
        out.write_text(_junit(cases), encoding="utf-8")
        return (1 if any(c[2] == "failed" for c in cases) else 0), ""


def test_specs_sharing_an_invocation_run_in_one_process():
    """C-6.1 — one spawn for three specs; the nodes ride together, the prefix once."""
    specs = (_s("S1"), _s("S2"), _s("S3"))
    sp = Spawner({f"tests/test_x.py::{i}": _case(f"tests/test_x.py::{i}") for i in ("S1", "S2", "S3")})
    res = run_specs(specs, spawn=sp, jobs=4)
    assert len(sp.calls) == 1
    argv = sp.calls[0]
    assert argv[:3] == ["python", "-m", "pytest"]
    assert all(f"tests/test_x.py::{i}" in argv for i in ("S1", "S2", "S3"))
    assert [r.passed for r in res] == [True, True, True]


def test_each_batched_spec_gets_its_own_verdict_and_duration():
    """C-6.2 — verdict and duration per spec come out of the report, in document order."""
    specs = (_s("S1"), _s("S2"), _s("S3"))
    sp = Spawner({"tests/test_x.py::S1": _case("tests/test_x.py::S1", t="0.250"),
                  "tests/test_x.py::S2": _case("tests/test_x.py::S2", "failed", t="0.100"),
                  "tests/test_x.py::S3": _case("tests/test_x.py::S3", t="0.005")})
    res = run_specs(specs, spawn=sp, jobs=1)
    assert [(r.scenario_id, r.passed, r.duration_ms) for r in res] == \
        [("S1", True, 250), ("S2", False, 100), ("S3", True, 5)]
    assert res[1].exit_code != 0 and res[0].exit_code == 0


def test_a_spec_missing_from_the_report_is_red():
    """C-6.3 — a node the runner never mentioned did not pass; it is red with a stated reason."""
    specs = (_s("S1"), _s("S2"))
    sp = Spawner({"tests/test_x.py::S1": _case("tests/test_x.py::S1")})     # S2 never reported
    res = run_specs(specs, spawn=sp, jobs=1)
    assert res[0].passed and not res[1].passed
    assert "not in the runner's report" in res[1].output_tail and res[1].exit_code == 4


def test_an_isolated_clause_runs_in_its_own_process():
    """C-6.4 — a spec that needs a process of its own gets one; the rest still share."""
    contract = parse("# Contract: I\n\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\n"
                     "- **C-1.2** — WHEN c THE SYSTEM SHALL d.\n  - tags: isolated\n")
    specs = (_s("S1", "C-1.1"), _s("S2", "C-1.2"), _s("S3", "C-1.1"))
    sp = Spawner({"tests/test_x.py::S1": _case("tests/test_x.py::S1"),
                  "tests/test_x.py::S3": _case("tests/test_x.py::S3")})
    res = run_specs(specs, spawn=sp, jobs=2, contract=contract)
    batch = [c for c in sp.calls if any(a.startswith("--junitxml=") for a in c)]
    single = [c for c in sp.calls if not any(a.startswith("--junitxml=") for a in c)]
    assert len(batch) == 1 and len(single) == 1
    assert "tests/test_x.py::S2" in single[0] and "tests/test_x.py::S2" not in batch[0]
    assert all(r.passed for r in res)


def test_early_exit_and_report_options_are_never_batched():
    """C-6.5 — -x changes what a run means for the other specs; --junitxml claims the report
    slot. Both keep an invocation out of every batch."""
    assert batch_key("python -m pytest tests/test_x.py::t -q") == \
        (("python", "-m", "pytest", "-q"), ("tests/test_x.py::t",))
    for bad in ("python -m pytest tests/test_x.py::t -x",
                "pytest tests/test_x.py::t --maxfail=1",
                "pytest tests/test_x.py::t --junitxml=out.xml",
                "pytest -xq tests/test_x.py::t",
                "python -m pytest tests/test_x.py::t --lf"):
        assert batch_key(bad) is None, bad
    assert batch_key("python scripts/check.py tests/test_x.py::t") is None, "not pytest"
    assert batch_key("pytest -q") is None, "no node"
    units = plan_batches((_s("S1"),
                          Scenario(id="S2", requirement_key="C-1.1", gwt_text="g",
                                   run_cmd="python -m pytest tests/test_x.py::S2 -x"),
                          _s("S3")))
    assert [(k, tuple(s.id for s in m)) for k, m in units] == \
        [("batch", ("S1", "S3")), ("one", ("S2",))]


def test_an_aborted_batch_is_rerun_one_process_per_spec():
    """C-6.6 — one unknown node aborts pytest with zero tests; the batch falls back to one
    process each, so only the bad spec is red."""
    specs = (_s("S1"), _s("S2"), _s("S3"))
    sp = Spawner(aborted=True, single_code=lambda node: 4 if node.endswith("S2") else 0)
    res = run_specs(specs, spawn=sp, jobs=1)
    assert len(sp.calls) == 4, "one batch attempt, then three singles"
    assert [r.passed for r in res] == [True, False, True]


def test_a_batched_failure_keeps_its_message():
    """C-6.7 — the ledger must stay diagnosable when the spec did not run alone."""
    specs = (_s("S1"), _s("S2"))
    sp = Spawner({"tests/test_x.py::S1": _case("tests/test_x.py::S1"),
                  "tests/test_x.py::S2": _case("tests/test_x.py::S2", "failed",
                                               msg="AssertionError: one is not two")})
    res = run_specs(specs, spawn=sp, jobs=1)
    assert "one is not two" in res[1].output_tail and res[0].output_tail == ""


def test_an_injected_executor_runs_each_spec_alone():
    """C-6.8 — the injected executor is the seam the runner's own specs rely on; it sees one
    command at a time and nothing is spawned around it."""
    seen = []

    def ex(cmd, *, cwd, timeout):
        seen.append(cmd)
        return 0, ""

    sp = Spawner()
    res = run_specs((_s("S1"), _s("S2"), _s("S3")), executor=ex, spawn=sp, jobs=3)
    assert len(seen) == 3 and sp.calls == [] and all(r.passed for r in res)
