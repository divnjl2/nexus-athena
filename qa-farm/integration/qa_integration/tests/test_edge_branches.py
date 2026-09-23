"""Closes the branch gaps qa_integration found in ITSELF (orphan branches — the untested side
of guard `if`s). Dogfood: the frame's own coverage gate would flag these; real tests close
them, mirroring qa_unit/tests/test_edge_branches.py."""
import json

import pytest

from qa_integration.api import app
from qa_integration.ci.hitl_manifest import write_manifest
from qa_integration.config import Config, is_compose_or_fixture_change
from qa_integration.primitives.coverage_parse_integration import parse_coverage_text
from qa_integration.tools.isolation_manager import check_fingerprint
from qa_integration.tools.run_changed_integration_tests import select_integration_tests
from qa_integration.tools.slow_flaky_triage import classify, quarantine_if_slow


def test_match_any_depth_suffix_pattern():                # config.py:27-28 ("/**" branch)
    cfg = Config(compose_fixture_globs=("shared_fixtures/**",))
    assert is_compose_or_fixture_change("shared_fixtures/x.py", cfg) is True
    assert is_compose_or_fixture_change("shared_fixtures", cfg) is True
    assert is_compose_or_fixture_change("unrelated/x.py", cfg) is False


def test_coverage_parse_class_outside_any_boundary_is_ignored():  # coverage_parse_integration.py:23
    xml = ('<coverage><packages><package><classes>'
          '<class filename="unrelated/x.py"><lines><line number="1" hits="1"/></lines></class>'
          '</classes></package></packages></coverage>')
    r = parse_coverage_text(xml, {"boundary_a": ["service_a/"]})
    assert r["boundaries"]["boundary_a"]["line"] == 0.0
    assert r["boundaries"]["boundary_a"]["has_tests"] is False


def test_coverage_parse_skips_line_without_number():        # coverage_parse_integration.py:28
    xml = ('<coverage><packages><package><classes>'
          '<class filename="service_a/h.py"><lines>'
          '<line hits="1"/><line number="2" hits="1"/>'
          '</lines></class></classes></package></packages></coverage>')
    r = parse_coverage_text(xml, {"boundary_a": ["service_a/"]})
    assert r["boundaries"]["boundary_a"]["line"] == 1.0    # only the numbered line counted


def test_select_respects_explicit_all_tests_on_compose_change():  # run_changed_integration_tests.py:26
    sel = select_integration_tests(["docker-compose.yml"], {}, {}, all_tests=["ta", "tb"])
    assert sel.full_run is True and set(sel.tests) == {"ta", "tb"}


def test_check_fingerprint_clean_state_is_not_a_bleed():   # isolation_manager.py:35
    check = check_fingerprint("tests/test_a.py::t1", expected_fingerprint="clean",
                              actual_fingerprint="clean")
    assert check.ok is True and check.colliding_tests == ()


def test_quarantine_if_slow_within_budget_is_none():        # slow_flaky_triage.py:20
    assert quarantine_if_slow("tests/test_fast.py::t", 5.0, budget_s=30.0) is None


def test_classify_empty_results_raises():                   # slow_flaky_triage.py:32
    with pytest.raises(ValueError):
        classify("t", "c", [])


def test_api_version_endpoint():                            # api.py:47
    from fastapi.testclient import TestClient
    client = TestClient(app)
    body = client.get("/version").json()
    assert body["qa_integration"]


def test_write_manifest_produces_valid_json(tmp_path):      # hitl_manifest.py:24-26
    path = write_manifest(str(tmp_path / "hitl_manifest.json"))
    data = json.loads(open(path, encoding="utf-8").read())
    assert any(p["id"] == "approve-environment-fix" for p in data["hitl"])
