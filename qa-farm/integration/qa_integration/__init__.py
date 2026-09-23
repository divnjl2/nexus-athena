"""Integration-Testing QA workflow-microservice (NEXUS QA farm, domain #2).

Layered per the L0/L1/L2 pie (see ../design.md):
  primitives/  L0  atomic, pure, JSON-in/out wrappers over tools — run against real deps
  tools/       L1  composition + policy (the gates: dependency health, coverage, isolation,
               slow/flaky triage, selection)
  agent/       L2  the Env-Fix Proposal agent (propose, never apply)
  ci/              blocking PR gate + budget guard + HITL manifest
Every public behaviour is proven by a scenario test under tests/ (see ../scenarios.md).

Differs from domain #1 (qa_unit) in one load-bearing way: every assertion here runs against
REAL dependencies (docker-compose / testcontainers), never mocks or in-process fakes — which
is why this domain needs a dependency-health gate and an isolation manager that domain #1
does not.
"""
__version__ = "0.1.0"
