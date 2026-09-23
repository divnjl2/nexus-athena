# Architecture — interactive maps

> GitHub renders these Mermaid diagrams inline. Nodes marked with a link are **clickable** —
> they jump straight to the source file.

## 1. The L0 / L1 / L2 pie

Bottom-up: pure primitives (that exercise real dependencies) → policy gates → the one
stateful agent. Click a node to open its code.

```mermaid
flowchart TB
    classDef l0 fill:#0d3b66,stroke:#58a6ff,color:#eaf2ff;
    classDef l1 fill:#14432a,stroke:#3fb950,color:#eafff0;
    classDef l2 fill:#3d2a5e,stroke:#bc8cff,color:#f3ecff;
    classDef ci fill:#5a3a12,stroke:#e3b341,color:#fff7e6;

    subgraph AGENT["🤖 L2 — Env-Fix Proposal Agent · propose, never apply"]
        direction LR
        EF["envfix_finder"]:::l2 --> EG["envfix_generator"]:::l2 --> EP["envfix_pr"]:::l2
    end
    subgraph TOOLS["⚙️ L1 — Workflow tools · gates + policy"]
        direction LR
        RCT["run_changed_integration_tests"]:::l1
        DHG["dependency_health_gate"]:::l1
        ICG["integration_coverage_gate"]:::l1
        IM["isolation_manager"]:::l1
        SFT["slow_flaky_triage"]:::l1
        RP["report"]:::l1
    end
    subgraph PRIM["🧱 L0 — Primitives · pure, JSON-in/out, exercise real deps"]
        direction LR
        PRI["pytest_run_integration"]:::l0
        CB["changed_boundaries"]:::l0
        CPI["coverage_parse_integration"]:::l0
        DHP["dependency_health_probe"]:::l0
    end
    subgraph FACE["🚦 CI + handles"]
        direction LR
        PG["pr_gate"]:::ci
        BG["budget"]:::ci
        HM["hitl_manifest"]:::ci
        CFG["config.py"]:::ci
        CLI["cli.py · api.py"]:::ci
    end

    AGENT --> TOOLS
    TOOLS --> PRIM
    FACE --> TOOLS

    click EF "../qa_integration/agent/envfix_finder.py" "envfix_finder.py"
    click EG "../qa_integration/agent/envfix_generator.py" "envfix_generator.py"
    click EP "../qa_integration/agent/envfix_pr.py" "envfix_pr.py"
    click RCT "../qa_integration/tools/run_changed_integration_tests.py" "run_changed_integration_tests.py"
    click DHG "../qa_integration/tools/dependency_health_gate.py" "dependency_health_gate.py"
    click ICG "../qa_integration/tools/integration_coverage_gate.py" "integration_coverage_gate.py"
    click IM "../qa_integration/tools/isolation_manager.py" "isolation_manager.py"
    click SFT "../qa_integration/tools/slow_flaky_triage.py" "slow_flaky_triage.py"
    click RP "../qa_integration/tools/report.py" "report.py"
    click PRI "../qa_integration/primitives/pytest_run_integration.py" "pytest_run_integration.py"
    click CB "../qa_integration/primitives/changed_boundaries.py" "changed_boundaries.py"
    click CPI "../qa_integration/primitives/coverage_parse_integration.py" "coverage_parse_integration.py"
    click DHP "../qa_integration/primitives/dependency_health_probe.py" "dependency_health_probe.py"
    click PG "../qa_integration/ci/pr_gate.py" "pr_gate.py"
    click BG "../qa_integration/ci/budget.py" "budget.py"
    click HM "../qa_integration/ci/hitl_manifest.py" "hitl_manifest.py"
    click CFG "../qa_integration/config.py" "config.py"
    click CLI "../qa_integration/cli.py" "cli.py"
```

## 2. What happens on a pull request

Change → select → dependency health → run (isolated) → coverage → gate → report.

```mermaid
flowchart LR
    A(["PR opened"]) --> B["select<br/>only tests for the changed boundary"]
    B --> C{"dependency_health_gate<br/>probe every declared dependency"}
    C -->|"a dependency is down"| X(["❌ FAIL loud · names the dependency<br/>exit 1 · no result is trusted"])
    C -->|"all healthy"| D["run_changed_integration_tests<br/>pytest_run_integration under isolation_manager"]
    D --> E{"integration_coverage_gate<br/>per-boundary line coverage"}
    E -->|PASS| F(["✅ merge allowed · exit 0"])
    E -->|FAIL| G(["❌ merge blocked · exit 1 · names the boundary"])
    D --> H["slow_flaky_triage<br/>quarantine slow · classify flaky"]
    H --> I["report<br/>JUnit + Allure + dependency health + coverage + flaky rate"]
    X --> J["🤖 envfix agent drafts a fix"] --> K{{"👤 human approves"}} --> L(["fix lands via PR"])

    style F fill:#14432a,stroke:#3fb950,color:#eafff0
    style G fill:#4a1f1f,stroke:#f85149,color:#ffecec
    style X fill:#4a1f1f,stroke:#f85149,color:#ffecec
    style K fill:#5a3a12,stroke:#e3b341,color:#fff7e6
```

## 3. The dependency-health gate (why a green run is a green run)

This is the headline difference from domain #1: `qa_unit` never touches live infra, so it
has nothing to probe. `qa_integration` runs against real dependencies, so a "PASS" is only
trustworthy if every declared dependency actually answered healthy — never inferred, never
skipped.

```mermaid
flowchart TB
    START["run starts"] --> PROBE["probe_all<br/>probes every declared dependency independently"]
    PROBE --> Q{"any dependency unhealthy<br/>or timed out?"}
    Q -->|"no"| OK(["✅ PASS · all dependencies healthy<br/>integration tests may proceed"])
    Q -->|"yes"| FAIL(["❌ FAIL · names the unhealthy dependency<br/>never a silent skip"])
    FAIL --> NOTE["a timeout counts as failure too<br/>never treated as 'no answer, assume fine'"]
    FAIL --> AGENT["🤖 envfix_finder may pick this up"]

    style OK fill:#14432a,stroke:#3fb950,color:#eafff0
    style FAIL fill:#4a1f1f,stroke:#f85149,color:#ffecec

    click PROBE "../qa_integration/primitives/dependency_health_probe.py" "dependency_health_probe.py"
    click Q "../qa_integration/tools/dependency_health_gate.py" "dependency_health_gate.py"
```

## 4. The HITL / env-fix safety boundary (why you can delegate)

The agent proposes; it **holds no apply credential** to any shared or production
environment. Every drafted fix crosses a human approval gate before it can be applied.

```mermaid
flowchart LR
    GAP["dependency-health failure"] --> FIND["envfix_finder<br/>locates the fix target · file + line"]
    FIND --> GEN["🤖 envfix_generator<br/>drafts a candidate fix"]
    GEN --> PR["envfix_pr.open_env_fix_pr<br/>opens a PR · never applies"]
    PR --> WALL{{"🧱 HITL wall<br/>apply_env_fix needs a recorded approval"}}
    WALL -->|"approval record"| LAND(["✅ fix applied · human-approved action"])
    WALL -.->|"no approval"| REFUSE(["⛔ ApplyNotPermitted"])

    style WALL fill:#5a3a12,stroke:#e3b341,color:#fff7e6
    style REFUSE fill:#4a1f1f,stroke:#f85149,color:#ffecec

    click FIND "../qa_integration/agent/envfix_finder.py" "envfix_finder.py"
    click GEN "../qa_integration/agent/envfix_generator.py" "envfix_generator.py"
    click PR "../qa_integration/agent/envfix_pr.py" "envfix_pr.py"
```

## 5. Provenance — how this repo ties to Athena (the closed loop)

Built by the [Athena](https://github.com/divnjl2/nexus-athena) planner, the same loop as
domain #1. Every edge is proven: `verifies` (v3.1) · `satisfies` coverage-proven (v3.2) ·
`implements` real SHA (v4).

```mermaid
flowchart LR
    SPEC["📜 spec<br/>requirement"]
    SCEN["🎬 scenario<br/>Given/When/Then"]
    TASK["🔧 task"]
    COMMIT["📦 commit"]

    SPEC -.->|derives| SCEN
    SCEN -->|"verifies · v3.1"| SPEC
    TASK -->|"satisfies + coverage-proven · v3.2"| SCEN
    COMMIT -->|"implements · real SHA · v4"| TASK

    click SPEC "../spec.md" "spec.md"
    click SCEN "../scenarios.md" "scenarios.md"
    click TASK "../plan.md" "plan.md"
```

## 6. Executor port (v4) — the frame doesn't care who writes the code

Hermes / OpenHands / Claude Code / Ralph are interchangeable adapters behind one contract —
identical to domain #1, since the executor port lives in Athena, not in the QA domain.

```mermaid
flowchart LR
    subgraph EXE["executors — swap freely"]
        direction TB
        H["Hermes"]
        O["OpenHands"]
        CC["Claude Code"]
        RA["Ralph"]
    end
    EXE ==>|"ExecutorResult: task_id, commit_sha, checks"| PORT["Executor port"]
    PORT --> SEAM["Seam 11<br/>real-SHA guard"]
    SEAM --> EDGE(["commit —implements→ task"])

    style PORT fill:#3d2a5e,stroke:#bc8cff,color:#f3ecff
    style EDGE fill:#14432a,stroke:#3fb950,color:#eafff0
```
