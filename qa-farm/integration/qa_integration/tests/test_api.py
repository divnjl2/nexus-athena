"""Proves the HTTP API handles (FastAPI) mirror the CLI/library behaviour."""
from fastapi.testclient import TestClient

from qa_integration.api import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_gate_blocks_low_boundary_coverage():
    xml = ('<coverage><packages><package><classes>'
          '<class filename="service_a/h.py"><lines>'
          '<line number="1" hits="0"/><line number="2" hits="0"/>'
          '</lines></class></classes></package></packages></coverage>')
    body = client.post("/gate", json={
        "coverage_xml": xml, "boundary_map": {"boundary_a": ["service_a/"]}}).json()
    assert body["passed"] is False and body["failing_boundary"] == "boundary_a"
    assert body["exit_code"] != 0


def test_gate_passes_good_boundary_coverage():
    xml = ('<coverage><packages><package><classes>'
          '<class filename="service_a/h.py"><lines>'
          '<line number="1" hits="1"/><line number="2" hits="1"/>'
          '</lines></class></classes></package></packages></coverage>')
    body = client.post("/gate", json={
        "coverage_xml": xml, "boundary_map": {"boundary_a": ["service_a/"]}}).json()
    assert body["passed"] is True and body["exit_code"] == 0


def test_select_no_relevant_change():
    body = client.post("/select", json={"changed": ["README.md"]}).json()
    assert body["reason"] == "no_relevant_change" and body["tests"] == []


def test_manifest_lists_hitl_points():
    ids = {p["id"] for p in client.get("/manifest").json()["hitl"]}
    assert "approve-environment-fix" in ids


def test_gate_malformed_xml_returns_400():
    r = client.post("/gate", json={"coverage_xml": "<coverage line-rate="})
    assert r.status_code == 400
    assert "malformed" in r.json()["detail"]
