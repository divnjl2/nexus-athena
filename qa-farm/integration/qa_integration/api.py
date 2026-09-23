"""HTTP API — the same handles as the CLI, over FastAPI, for network-driven use (dashboards,
webhooks, the farm orchestrator). Run: `uvicorn qa_integration.api:app`.

  GET  /health                       liveness
  GET  /version
  GET  /manifest                     HITL decision points (R8.3)
  POST /gate   {coverage_xml, boundary_map?, base_line?}   -> integration coverage verdict
  POST /select {changed[], boundary_map?, test_map?}       -> affected integration test set
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from qa_integration import __version__
from qa_integration.ci.hitl_manifest import manifest as hitl_manifest
from qa_integration.ci.pr_gate import aggregate
from qa_integration.primitives.coverage_parse_integration import parse_coverage_text
from qa_integration.tools.integration_coverage_gate import integration_coverage_gate
from qa_integration.tools.run_changed_integration_tests import select_integration_tests

app = FastAPI(title="qa_integration", version=__version__,
              description="Integration-Testing QA workflow-microservice (NEXUS QA farm, domain #2)")


class GateReq(BaseModel):
    coverage_xml: str
    boundary_map: dict[str, list[str]] = {}
    base_line: dict[str, float] | None = None


class SelectReq(BaseModel):
    changed: list[str]
    boundary_map: dict[str, list[str]] = {}
    test_map: dict[str, list[str]] = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"qa_integration": __version__}


@app.get("/manifest")
def manifest():
    return hitl_manifest()


@app.post("/gate")
def gate(req: GateReq):
    try:
        cov = parse_coverage_text(req.coverage_xml, req.boundary_map, base_line=req.base_line)
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail=f"malformed coverage xml: {e}")
    g = integration_coverage_gate(cov["boundaries"])
    status = aggregate([("coverage", g.passed)])
    return {
        "gate": "integration_coverage", "passed": g.passed, "failing_boundary": g.failing_boundary,
        "detail": g.detail, "boundaries": cov["boundaries"], "exit_code": status.exit_code,
    }


@app.post("/select")
def select(req: SelectReq):
    sel = select_integration_tests(req.changed, req.boundary_map, req.test_map)
    return {"reason": sel.reason, "full_run": sel.full_run,
           "boundaries": list(sel.boundaries), "tests": list(sel.tests)}
