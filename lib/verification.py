"""Typed execution evidence shared by mutation and spec-trust audits.

Only an assertion failure is an automatic witness. A timeout, skipped test, collection
error or arbitrary exit code is not evidence that a requirement violation was detected.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from lib.spec_runner import _tokenize


@dataclass(frozen=True)
class Outcome:
    status: str
    exit_code: int
    tail: str = ""
    tests: int = 0


def outcome(value: Outcome | int) -> Outcome:
    """Integer 0/1 remains a compatibility seam for injected legacy unit-test runners."""
    if isinstance(value, Outcome):
        return value
    return Outcome({0: "PASS", 1: "ASSERTION_FAIL"}.get(value, "TOOL_ERROR"), value)


def junit_outcome(code: int, xml: str, tail: str = "") -> Outcome:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return Outcome("TOOL_ERROR", code, "missing or invalid JUnit evidence: " + tail)
    cases = list(root.iter("testcase"))
    if not cases or any(c.find("skipped") is not None or c.find("error") is not None for c in cases):
        return Outcome("TOOL_ERROR", code, "empty, skipped or errored test run: " + tail, len(cases))
    failures = [f for c in cases for f in c.findall("failure")]
    # Runtime/import exceptions are not silently turned into semantic kills. pytest's
    # assertion rewriting uses an empty `type` and includes AssertionError in its message.
    if failures:
        assertion = all(f.get("type", "").endswith(("AssertionError", "Failed"))
                        or not f.get("type") and f.get("message", "").startswith(
                            ("AssertionError", "assert ", "Failed: ")) for f in failures)
        return Outcome("ASSERTION_FAIL" if code == 1 and assertion else "TOOL_ERROR", code, tail, len(cases))
    return Outcome("PASS" if code == 0 else "TOOL_ERROR", code, tail, len(cases))


def execution_environment() -> dict:
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONOPTIMIZE", "PYTHONINSPECT",
                 "PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST", "COVERAGE_PROCESS_START",
                 "CODEX_TOOL_CALL_ID"):
        env.pop(name, None)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    return env


def run_command(cmd: str, *, cwd: str, timeout: int = 120, prefix=()) -> Outcome:
    argv, reason = _tokenize(cmd)
    if not argv:
        return Outcome("TOOL_ERROR", 126, reason)
    # All Python invocations use the verifier's interpreter, not a candidate-local shim.
    is_python = pathlib.Path(argv[0]).name.lower() in ("python", "python3", "python.exe")
    if is_python:
        argv[0] = sys.executable
    if pathlib.Path(argv[0]).name.lower() in ("pytest", "pytest.exe"):
        argv = [sys.executable, "-m", "pytest", *argv[1:]]
    is_pytest = (pathlib.Path(argv[0]).name.lower() in ("pytest", "pytest.exe")
                 or len(argv) > 2 and argv[1:3] == ["-m", "pytest"])
    with tempfile.TemporaryDirectory(prefix="athena-verifier-") as tmp:
        report = pathlib.Path(tmp) / "results.xml"
        if is_pytest:
            if any(a.startswith(("--junit", "--collect-only", "--co")) for a in argv):
                return Outcome("TOOL_ERROR", 126, "verifier owns JUnit collection")
            argv += [f"--junitxml={report}"]
        try:
            env = execution_environment()
            p = subprocess.run([*prefix, *argv], cwd=cwd, capture_output=True, text=True,
                               errors="replace", timeout=timeout, env=env, shell=False)
            tail = ((p.stdout or "") + (p.stderr or ""))[-1000:]
        except subprocess.TimeoutExpired:
            return Outcome("TOOL_ERROR", 124, f"TIMEOUT after {timeout}s")
        except OSError as exc:
            return Outcome("TOOL_ERROR", 127, str(exc))
        if is_pytest:
            return junit_outcome(p.returncode, report.read_text(encoding="utf-8") if report.exists() else "", tail)
        # Generic commands can witness successful activation; a nonzero code does not
        # carry enough information to witness a requirement failure.
        return Outcome("PASS" if p.returncode == 0 else "TOOL_ERROR", p.returncode, tail)
