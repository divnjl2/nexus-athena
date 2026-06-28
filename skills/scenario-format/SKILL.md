# Scenario Format — EARS->GWT Harness (v3.1)

## Rule: scenarios derive from acceptance criteria, never authored separately

Given a Spec-Kit spec.md with EARS-style acceptance criteria
(`WHEN <event> THE SYSTEM SHALL <response>`), derive scenarios directly.
Do NOT write scenarios in parallel to the spec — they rot out of sync.

## No Gherkin/Cucumber

Do NOT add a Gherkin parser. Gherkin parsers are a brittle shim that becomes
its own source of breakage at scale. Instead:
- GWT text = human-readable (versioned artifact)
- run_cmd = direct pytest / shell command in the project's native test runner

## Scenario structure (lib/ast.py Scenario dataclass)

```python
Scenario(
    id="S1.2",              # stable ID: S<requirement_number>.<index>
    requirement_key="R1",   # matches a requirement ID in spec.md
    gwt_text=(
        "Given the system is running\n"
        "When GET /health is called\n"
        "Then response status is 200 and body contains ok"
    ),
    run_cmd="pytest tests/test_health.py::test_health_endpoint -q",
)
```

## Versioning rule (invariant 13)

scenario_version = sha-prefix of the GWT artifact file (LLM-hop output).
Cached per spec_version — do NOT regenerate unless spec_version changed.
Store under `thoughts/scenarios/<spec_version>/`.

## Task binding (Task.verifies)

Every Task that implements a scenario MUST declare it:
```python
Task(
    id="T1.1",
    title="add /health route",
    success_check="pytest tests/test_health.py::test_health_endpoint -q",
    verifies=("S1.2",),   # ties to scenario; success_check = scenario run_cmd
)
```

A task with `verifies=()` is valid (infrastructure/meta tasks).
A task that claims to verify a scenario ID not in `plan.scenarios` -> CompileError.

## Coverage check

`planner_trace_proof` flags requirements with zero verifying scenarios as UNCOVERED.
Every functional requirement SHOULD have >= 1 scenario before the plan is compiled.
