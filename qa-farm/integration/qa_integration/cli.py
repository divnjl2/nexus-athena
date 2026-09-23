"""CLI — the service handles ("ручки") for the Integration-QA microservice. Every subcommand
prints one JSON object and returns an exit code, so it works as a shell step, a CI gate, or a
Hermes `dispatcher: script` verb.

  python -m qa_integration gate --coverage cov.xml [--boundary-map map.json] [--base-line base.json]
      run the integration coverage gate on a real coverage.xml -> JSON verdict, exit 0 (pass) / 1 (block)
  python -m qa_integration select --changed a.py b.py [--boundary-map map.json] [--test-map map.json]
      print the affected integration test set for a change (no relevant change / compose fallback handled)
  python -m qa_integration manifest      print the HITL manifest (what a human must decide)
  python -m qa_integration version
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET

from qa_integration import __version__
from qa_integration.ci.hitl_manifest import manifest as hitl_manifest
from qa_integration.ci.pr_gate import aggregate
from qa_integration.primitives.coverage_parse_integration import parse_coverage_text
from qa_integration.tools.integration_coverage_gate import integration_coverage_gate
from qa_integration.tools.run_changed_integration_tests import select_integration_tests


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cmd_gate(a) -> int:
    boundary_map = _load_json(a.boundary_map) if a.boundary_map else {}
    base_line = _load_json(a.base_line) if a.base_line else None
    try:
        with open(a.coverage, encoding="utf-8") as fh:
            cov = parse_coverage_text(fh.read(), boundary_map, base_line=base_line)
    except FileNotFoundError:
        _emit({"error": f"coverage file not found: {a.coverage}", "exit_code": 2})
        return 2
    except ET.ParseError as e:
        _emit({"error": f"malformed coverage xml: {e}", "exit_code": 2})
        return 2
    g = integration_coverage_gate(cov["boundaries"])
    status = aggregate([("coverage", g.passed)])
    _emit({
        "gate": "integration_coverage", "passed": g.passed, "failing_boundary": g.failing_boundary,
        "detail": g.detail, "boundaries": cov["boundaries"], "exit_code": status.exit_code,
    })
    return status.exit_code


def cmd_select(a) -> int:
    boundary_map = _load_json(a.boundary_map) if a.boundary_map else {}
    test_map = _load_json(a.test_map) if a.test_map else {}
    sel = select_integration_tests(a.changed, boundary_map, test_map)
    _emit({"reason": sel.reason, "full_run": sel.full_run,
          "boundaries": list(sel.boundaries), "tests": list(sel.tests)})
    return 0


def cmd_manifest(a) -> int:
    _emit(hitl_manifest())
    return 0


def cmd_version(a) -> int:
    _emit({"qa_integration": __version__})
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="qa_integration",
                                description="Integration-Testing QA workflow-microservice")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gate", help="run the integration coverage gate on a coverage.xml")
    g.add_argument("--coverage", required=True)
    g.add_argument("--boundary-map", default="", dest="boundary_map")
    g.add_argument("--base-line", default="", dest="base_line")
    g.set_defaults(fn=cmd_gate)

    s = sub.add_parser("select", help="print affected integration tests for a change")
    s.add_argument("--changed", nargs="+", required=True)
    s.add_argument("--boundary-map", default="", dest="boundary_map")
    s.add_argument("--test-map", default="", dest="test_map")
    s.set_defaults(fn=cmd_select)

    sub.add_parser("manifest", help="print the HITL manifest").set_defaults(fn=cmd_manifest)
    sub.add_parser("version", help="print version").set_defaults(fn=cmd_version)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
