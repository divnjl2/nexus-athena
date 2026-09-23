"""Proves the coverage_parse_integration L0 primitive (plan T1.3)."""
from qa_integration.primitives.coverage_parse_integration import parse_coverage_text

COBERTURA = """<coverage line-rate="0.6" branch-rate="0.5">
 <packages><package><classes>
  <class filename="service_a/handler.py">
   <lines>
    <line number="10" hits="1"/>
    <line number="12" hits="0"/>
    <line number="14" hits="1" branch="true" condition-coverage="50% (1/2)"/>
    <line number="16" hits="1" branch="true" condition-coverage="100% (2/2)"/>
   </lines>
  </class>
 </classes></package></packages>
</coverage>"""

BOUNDARY_MAP = {"boundary_a": ["service_a/"], "boundary_b": ["service_b/"]}


def test_parses_per_boundary_line_rate():
    r = parse_coverage_text(COBERTURA, BOUNDARY_MAP)
    assert r["boundaries"]["boundary_a"]["line"] == 0.75      # 3 of 4 lines hit
    assert r["boundaries"]["boundary_a"]["has_tests"] is True


def test_new_boundary_with_no_classes_is_zero_not_no_data():
    r = parse_coverage_text(COBERTURA, BOUNDARY_MAP)
    assert r["boundaries"]["boundary_b"]["line"] == 0.0
    assert r["boundaries"]["boundary_b"]["has_tests"] is False


def test_delta_vs_base_per_boundary():
    r = parse_coverage_text(COBERTURA, BOUNDARY_MAP, base_line={"boundary_a": 0.9})
    assert r["boundaries"]["boundary_a"]["delta"] == round(0.75 - 0.9, 4)
    assert r["boundaries"]["boundary_b"]["delta"] is None
