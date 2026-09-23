"""L1: structured integration-run report — JUnit XML + an Allure result dir + a metrics block
with every field required, including dependency health (R6.1/R6.2)."""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

REQUIRED_METRICS = (
    "pass_rate", "boundary_coverage", "dependency_health", "runtime_s", "flaky_rate",
)


def build_metrics(*, passed, total, boundary_coverage, dependency_health, runtime_s,
                  flaky, flaky_total) -> dict:
    return {
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "boundary_coverage": dict(boundary_coverage),     # {boundary: line_rate}
        "dependency_health": dict(dependency_health),      # {dependency: "healthy"|"unhealthy"}
        "runtime_s": round(runtime_s, 4),
        "flaky_rate": round(flaky / flaky_total, 4) if flaky_total else 0.0,
    }


def write_report(out_dir, *, cases, metrics):
    """`cases` = list of {name, passed, duration}. Writes junit.xml + allure/<i>-result.json +
    metrics.json. Returns (junit_path, allure_dir)."""
    os.makedirs(out_dir, exist_ok=True)
    ts = ET.Element("testsuite", name="qa_integration", tests=str(len(cases)),
                    failures=str(sum(1 for c in cases if not c["passed"])))
    for c in cases:
        tc = ET.SubElement(ts, "testcase", name=c["name"], time=str(c.get("duration", 0.0)))
        if not c["passed"]:
            ET.SubElement(tc, "failure", message="failed")
    junit_path = os.path.join(out_dir, "junit.xml")
    ET.ElementTree(ts).write(junit_path, encoding="utf-8", xml_declaration=True)

    allure_dir = os.path.join(out_dir, "allure")
    os.makedirs(allure_dir, exist_ok=True)
    for i, c in enumerate(cases):
        with open(os.path.join(allure_dir, f"{i}-result.json"), "w", encoding="utf-8") as fh:
            json.dump({"name": c["name"], "status": "passed" if c["passed"] else "failed"}, fh)

    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh)
    return junit_path, allure_dir
