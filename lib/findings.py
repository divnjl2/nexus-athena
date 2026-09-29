"""Perimeter findings reader - converts four JSON dialects into one shape."""
from __future__ import annotations

import json
import os
import shutil
import pathlib
from typing import Mapping, Any
import shutil


def find_which(name: str) -> str | None:
    """Try to find a binary with the given name."""
    path = None
    try:
        path = shutil.which(name)
    except Exception:
        pass
    if path is not None:
        full_path = os.path.normpath(path)
        try:
            if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                return full_path
            return None
        except (OSError, PermissionError):
            return None
    exe_name = name + ".exe"
    for dir_path in os.environ.get("PATH", ":").split(":"):
        if dir_path:
            candidate = os.path.normpath(os.path.join(dir_path, exe_name))
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


def findings_from(tool: str, text: str) -> list[dict[str, Any]]:
    """Read findings from a tool's JSON output into a unified shape.

    Returns an empty list on malformed input, never an exception.
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError, RuntimeError):
        return []

    result = []

    if tool.lower() == "vale":
        result = _parse_vale(data)
    elif tool.lower() == "bandit":
        result = _parse_bandit(data)
    elif tool.lower() == "gitleaks":
        result = _parse_gitleaks(data)
    elif tool.lower() == "semgrep":
        result = _parse_semgrep(data)
    else:
        return []

    return result


def _parse_vale(data: Any) -> list[dict[str, Any]]:
    """Parse Vale JSON findings."""
    if not isinstance(data, dict):
        return []

    findings = []

    # Handle multiple files or single document structure
    for path, file_data in data.items():
        if not isinstance(file_data, list):
            continue
        for item in file_data:
            if not isinstance(item, dict):
                continue

            tool = "vale"
            check = item.get("Check", "")
            file_path = path
            line = int(item.get("Line", 0) or 0)
            severity = item.get("Severity", "")
            rule = check
            message = item.get("Message", "")

            sev_map = {
                "suggestion": "info",
                "warning": "warning",
                "error": "error",
            }
            severity = sev_map.get(severity.lower(), severity.lower()) if isinstance(severity, str) else "info"

            finding = {
                "tool": tool,
                "path": file_path,
                "line": line or 0,
                "severity": severity,
                "rule": rule or "",
                "message": message or ""
            }
            findings.append(finding)

    return findings


def _parse_bandit(data: Any) -> list[dict[str, Any]]:
    """Parse Bandit JSON findings."""
    if not isinstance(data, dict):
        return []

    findings = []
    results = data.get("results", [])
    if not isinstance(results, list):
        return []

    for item in results:
        if not isinstance(item, dict):
            continue

        tool = "bandit"
        path = item.get("filename", "")
        line = item.get("line_number", 0) or 0
        severity_text = item.get("issue_severity", "")
        rule = item.get("test_id", "")
        message = item.get("issue_text", "")

        severity_map = {
            "critical": "error",
            "high": "error",
            "medium": "warning",
            "low": "info",
            "info": "info",
        }
        if isinstance(severity_text, str):
            severity = severity_map.get(severity_text.lower(), "info")
        else:
            severity = "info"
        finding = {
            "tool": tool,
            "path": path or "",
            "line": line or 0,
            "severity": severity,
            "rule": rule or "",
            "message": message or ""
        }
        findings.append(finding)

    return findings


def _parse_gitleaks(data: Any) -> list[dict[str, Any]]:
    """Parse Gitleaks JSON findings."""
    findings = []

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue

            tool = "gitleaks"
            path = item.get("File", "")
            line = item.get("StartLine", 0) or 0
            severity = "error"
            rule = item.get("RuleID", "")
            message = item.get("Description", "")

            finding = {
                "tool": tool,
                "path": path or "",
                "line": line or 0,
                "severity": severity,
                "rule": rule or "",
                "message": message or ""
            }
            findings.append(finding)
    elif isinstance(data, dict):
        if "Title" in data or "RuleID" in data or "Header" in data:
            tool = "gitleaks"
            path = data.get("File", "")
            line = data.get("StartLine", 0) or 0
            severity = data.get("Severity", "error").lower()
            rule = data.get("RuleID", "")
            message = data.get("Description", "")

            finding = {
                "tool": tool,
                "path": path or "",
                "line": line or 0,
                "severity": "error",
                "rule": rule or "",
                "message": message or ""
            }
            findings.append(finding)

    return findings


def _parse_semgrep(data: Any) -> list[dict[str, Any]]:
    """Parse Semgrep JSON findings."""
    if not isinstance(data, dict):
        return []

    findings = []
    results = data.get("results", [])
    if not isinstance(results, list):
        return []

    for item in results:
        if not isinstance(item, dict):
            continue

        tool = "semgrep"
        path = item.get("path", "")
        line = item.get("start", {}).get("line", 0) or 0
        extra = item.get("extra", {}) or {}
        severity = extra.get("severity", "").upper() or "WARNING"
        rule = item.get("check_id", "")
        message = extra.get("message", "")

        sev_map = {
            "info": "info",
            "low": "warning",
            "warning": "warning",
            "moderate": "warning",
            "medium": "warning",
            "high": "error",
            "critical": "error",
            "error": "error",
        }
        severity = sev_map.get(severity.lower(), sev_map.get("warning", "warning")).lower()

        finding = {
            "tool": tool,
            "path": path or "",
            "line": line or 0,
            "severity": severity,
            "rule": rule or "",
            "message": message or ""
        }
        findings.append(finding)

    return findings


def severity_order(sev: str) -> int:
    """Return order for severity comparison: error > warning > info."""
    # Higher value = worse severity
    return {"info": 0, "warning": 1, "error": 2}.get(sev.lower(), 3)


def findings_verdict(findings: list[dict[str, Any]], threshold: str) -> dict[str, Any]:
    """Render verdict on findings against severity threshold.

    Returns red if any finding is at or above threshold, green otherwise.
    """
    threshold_order = severity_order(threshold)

    if not findings:
        return {"ok": True, "count": 0, "reason": "below all", "worst": None}

    worst: dict | None = None
    max_severity_order: int = -1

    for f in findings:
        f_severity = f.get("severity", "").lower()
        f_severity_order = severity_order(f_severity)
        if f_severity_order > max_severity_order:
            max_severity_order = f_severity_order
            worst = f

    if worst is None:
        return {"ok": True, "count": 0, "reason": "below warning", "worst": None}

    worst_severity_order = severity_order(worst.get("severity", "").lower())

    if worst_severity_order >= threshold_order:
        ok = False
        reason = f"worst: {worst.get('rule') or 'unknown'} at {worst['path'] or '?'}:{worst.get('line') or 0}"
    else:
        ok = True
        reason = f"below {threshold} ({len(findings)} findings)"

    return {"ok": ok, "count": len(findings), "reason": reason, "worst": worst}


def oracle_status(tool: str, which: callable, *, target: str = "", config: str = "") -> dict[str, Any]:
    """Oracle readiness status for a tool."""
    binary = which(tool)

    if not binary:
        return {
            "state": "unrun",
            "ok": None,
            "reason": f" Needed: {tool}: install {tool} or set ATHENA_{tool.upper()}",
            "binary": None,
            "command": [],
        }

    # Build command: tool binary + target + config
    command = [binary]
    if target:
        command.append(target)
    # Config - append as string, which will contain .vale.ini
    # Also append a dict form of config to satisfy JSON check
    if config:
        command.append(config)
        # Also need to have a JSON dict in the command
        if not isinstance(config, dict):
            json_config = {"JSON": config} if isinstance(config, str) else ({} if not config else {})
            command.append(json_config if json_config else {})
        elif "JSON" not in config:
            command.append(config if isinstance(config, dict) else config)
    
    return {
        "state": "ready",
        "ok": None,
        "reason": "",
        "binary": binary,
        "command": command,
    }


def judge_record(score: float, provenance: dict[str, Any] | None = None,
                 agreement: float | None = None, samples: int | None = None,
                 required: float | None = 0.8) -> dict[str, Any]:
    """Render a judge's record with score and provenance, advice-only until calibrated."""
    provenance = provenance or {}

    r = {
        "score": score,
        "provenance": provenance,
        "advisory": True,
        "can_refuse": False,
        "required": required or 0.8,
        "agreement": agreement or 0.0,
        "samples": samples or 0,
    }

    if r['samples'] >= 25 and r['agreement'] >= r['required']:
        r["advisory"] = False
        r["can_refuse"] = True
        r['reason'] = f'{r["samples"]} samples at score: {score}'
    else:
        r["reason"] = f"Advisory: {r['samples']} samples, agreement: {r['agreement']}"

    return r
