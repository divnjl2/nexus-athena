"""
Athena scaffold — how a project STARTS using the frame (v3.5).

Adoption was the quiet failure mode: everything downstream of `contract.md` is automated,
and `contract.md` itself was "write these three files by hand, in a format described in a
skill". A frame nobody can start is a frame nobody uses.

`init` emits the three files already wired to each other — one clause, one spec that proves
it, one task that carries it — so the very first `athena check` on a new project passes and
the loop is visible before anything real is written. Everything here is PURE text: the CLI
owns the writing, so the templates are golden-testable.
"""
from __future__ import annotations

QUOTE3 = chr(34) * 3

CONTRACT_TEMPLATE = """# Contract: {title}

> Numbered requirement clauses. Ids are allocated ONCE and never reused: a requirement that
> changes is superseded by a successor, never edited in place, so a reference written months
> ago keeps resolving. Rules: skills/contract-format/SKILL.md
>
> One clause = one checkable obligation. `athena contract lint --strict` enforces the rest.

## C-1 — {group}

- **C-1.1** — WHEN {trigger} THE SYSTEM SHALL {obligation}.
"""

SCENARIOS_TEMPLATE = """# Scenarios: {title}

> One executable spec per clause. `run_cmd` is a real command in this project's own test
> runner; exit 0 means the requirement holds. `pins:` is written by
> `athena contract pin --write` and is what makes drift detectable.

---

## C-1 — {group}

### S1.1 — {spec_title}
- **verifies:** C-1.1
- **run_cmd:** `{run_cmd}`
- **Given** {given}
- **When** {when}
- **Then** {then}
"""

PLAN_TEMPLATE = """# Plan: {title}

## Overview
{overview}

## Out of Scope
- (list what this plan deliberately does not do)

## Phase 1: {group}
**Goal:** {goal}
**Depends on:** none
### Tasks
- [ ] T1.1 {task}
  - success_check: `{run_cmd}`
  - files: `{files}`
  - verifies: S1.1
### Manual Verification
- `athena check contract.md --front plan.md --run --text` reports PASS.
"""

NEXT_STEPS = """created {n} files in {path}

next:
  1. write the real clauses            {path}/contract.md
  2. bind each one to a spec           {path}/scenarios.md
  3. pin them                          athena contract pin --contract {path}/contract.md {path}/scenarios.md --write
  4. run the loop                      athena check {path}/contract.md --front {path}/plan.md --run --text
  5. line ownership (optional, slow)   athena contract map {path}/contract.md --source <pkg>

migrating an existing spec.md instead:
  athena contract import spec.md -o {path}/contract.md      # keeps the EARS ids verbatim
"""


EXAMPLE_TEST = QUOTE3 + """Example spec for the scaffolded clause - replace it with a real one.""" + QUOTE3 + """


def version() -> str:
    return "0.1.0"


def test_the_system_reports_its_version():
    assert version() == "0.1.0"
"""


def render_files(*, title: str, group: str = "First requirements", run_cmd: str = "",
                 files: str = "", dir_hint: str = "features/my-feature") -> dict:
    """PURE: {filename: text} for a fresh feature, already wired clause -> spec -> task.

    The example is deliberately complete rather than a stub with TODOs: a scaffold whose
    first `check` fails teaches the user that the tool is broken, not that their contract is
    empty. (`TODO` in a live clause is also exactly what C-10.12 refuses.)
    """
    # The scaffold ships a WORKING example test as a fourth file, because its promise is
    # that the first `athena check` passes. The first cut pointed the spec at
    # tests/test_example.py, a path init never created: an audit ran the quick start on a
    # clean directory and the very first check failed on a missing file.
    hint = dir_hint.replace("\\", "/").rstrip("/")
    run_cmd = run_cmd or f"pytest {hint}/test_example.py::test_the_system_reports_its_version -q"
    files = files or f"{hint}/test_example.py"
    return {
        "test_example.py": EXAMPLE_TEST,
        "contract.md": CONTRACT_TEMPLATE.format(
            title=title, group=group,
            trigger="the system starts",
            obligation="report its version"),
        "scenarios.md": SCENARIOS_TEMPLATE.format(
            title=title, group=group,
            spec_title="the system reports its version on start",
            run_cmd=run_cmd,
            given="a freshly started system",
            when="its version is requested",
            then="the reported version matches the packaged one"),
        "plan.md": PLAN_TEMPLATE.format(
            title=title, group=group,
            overview=f"Deliver {title}: every clause in contract.md proved by an executable "
                     f"spec, and every spec bound to the code it exercises.",
            goal="the first requirement is stated, bound and proved",
            task="implement the first requirement and bind its spec",
            run_cmd=run_cmd, files=files),
    }


def next_steps(path: str, count: int) -> str:
    """PURE: what to do with the files that were just written."""
    return NEXT_STEPS.format(path=path.replace("\\", "/"), n=count)
