# /athena.scenarios — EARS acceptance criteria -> executable GWT scenarios (v3.1)

Derives executable Given-When-Then scenarios from the spec's EARS acceptance criteria.
Output is versioned as `scenario_version` pinned to `spec_version`.

## When to use

After `/athena.spec` produces `spec.md`. Before `/crisp.design` and task compilation.
Scenarios feed into `Task.verifies` so every task's `success_check` is a requirement proof.

## What it produces

- One `Scenario` per acceptance criterion in spec.md
- Grouped by requirement key (R1, R2, ...)
- Stored under `thoughts/scenarios/<spec_version>/scenarios.md`
- `scenario_version` written to `.athena/seams.jsonl` (pinned to `spec_version`)

## Invocation

Read spec.md, then for each EARS criterion:
1. Extract WHEN/SHALL pattern -> Given-When-Then
2. Assign stable ID: `S<requirement_number>.<index>` (e.g. S1.2)
3. Write `run_cmd` as a native test runner command (pytest, curl, etc.)

NO Gherkin/Cucumber. See `skills/scenario-format/SKILL.md`.

## Pin the output

```python
from lib.versioning import pin_output, scenario_dir
outdir = scenario_dir(spec_version)
outdir.mkdir(parents=True, exist_ok=True)
# write scenarios.md to outdir/scenarios.md
scenario_version = pin_output("scenarios", run_id, outdir / "scenarios.md",
                              input_version=spec_version, ts=<iso_ts>)
```

## Connecting to tasks

When writing tasks.md (via `/plan` + `/tasks`), bind each scenario:
```markdown
- [ ] T1.1 add /health route
  - success_check: `pytest tests/test_health.py::test_health_endpoint -q`
  - verifies: S1.2
```

## Compile-time enforcement

`plan2beads.compile()` raises `CompileError` if `Task.verifies` references an unknown
scenario ID. Coverage gaps (requirements with no scenario) are flagged by
`planner_trace_proof`.
