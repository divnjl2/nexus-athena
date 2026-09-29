"""Perimeter layer, C-3: scan and policy as stages of the merge queue.

T3.1 and T3.2, finished by the frontier under ADR-0007 (29.09) after the ai-server lane's iterations: the first
landing planned gitleaks only for Markdown, bandit with `-o json` and a 2,000-entry `-t` list and pip-audit as
`pip audit` (a grader fit that S3.1 then closed); the rework hit the lane's 8,192-token answer cap and left an
unterminated string; T3.2 edited the spec's own test file, which the frame refuses.

The stage plans from the changed paths (C-3.1): Bandit for Python files, gitleaks over the diff whenever anything
changed, pip-audit when a requirements file changed, nothing for nothing. A missing scanner is unrun, never a
finding. The policy input (C-3.2) is the merge record about to be written, the changed paths, the stages seen and
whether the task's last dispatch carries its provenance; conftest evaluates the layer's Rego over it.
"""
from __future__ import annotations

import json
from typing import Callable, Iterable

BANDIT_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
THRESHOLD_RANK = {"info": 0, "low": 0, "warning": 1, "medium": 1, "error": 2, "high": 2}


def scan_plan(paths: Iterable[str], diff_ref: str | None = None) -> list:
    """PURE (C-3.1): the scanners a set of changed paths calls for, each with the tool's own argv.
    Bandit for Python files; gitleaks over the git range whenever anything changed (a secret can sit in any
    file); pip-audit per requirements file. An empty change plans nothing."""
    paths = [str(p).replace("\\", "/") for p in (paths or []) if str(p).strip()]
    if not paths:
        return []
    plan: list = []
    py = [p for p in paths if p.endswith(".py")]
    if py:
        plan.append({"tool": "bandit", "files": py, "argv": ["bandit", "-f", "json", "-q", *py]})
    leaks_argv = ["gitleaks", "git", ".", "--report-format", "json", "--report-path", "-", "--no-banner"]
    if diff_ref:
        leaks_argv.append(f"--log-opts={diff_ref}")
    plan.append({"tool": "gitleaks", "files": list(paths), "argv": leaks_argv})
    reqs = [p for p in paths if p.rsplit("/", 1)[-1] in ("requirements.txt", "requirements-dev.txt") or p.endswith("requirements.txt")]
    for req in reqs:
        plan.append({"tool": "pip-audit", "files": [req], "argv": ["pip-audit", "-r", req, "-f", "json"]})
    return plan


def _json(text: str):
    try:
        return json.loads(text or "")
    except (ValueError, TypeError):
        return None


def _findings_of(tool: str, code: int, out: str) -> tuple:
    """(findings, unrun): the tool's JSON read into one shape — {tool, rule, severity, file, line, text};
    a scanner that is absent (exit 127, or no JSON and a not-found tail) is unrun."""
    data = _json(out)
    if code == 127 or (data is None and ("not found" in (out or "").lower() or "not recognized" in (out or "").lower())):
        return [], True
    found: list = []
    if tool == "bandit":
        for it in ((data or {}).get("results") or []) if isinstance(data, dict) else []:
            found.append({"tool": tool, "rule": it.get("test_id", ""), "severity": str(it.get("issue_severity", "LOW")).upper(),
                          "file": it.get("filename", ""), "line": it.get("line_number", 0), "text": it.get("issue_text", "")})
    elif tool == "gitleaks":
        rows = data if isinstance(data, list) else ((data or {}).get("findings") if isinstance(data, dict) else []) or []
        for it in rows:
            found.append({"tool": tool, "rule": it.get("RuleID") or it.get("rule_id") or "leak", "severity": "HIGH",
                          "file": it.get("File") or it.get("file", ""), "line": it.get("StartLine") or it.get("line", 0),
                          "text": "a secret in the diff"})
    elif tool == "pip-audit":
        deps = (data or {}).get("dependencies") if isinstance(data, dict) else data
        for dep in deps or []:
            for v in (dep.get("vulns") or []) if isinstance(dep, dict) else []:
                found.append({"tool": tool, "rule": v.get("id", ""), "severity": "HIGH",
                              "file": f"{dep.get('name', '')}=={dep.get('version', '')}", "line": 0,
                              "text": "fix: " + ", ".join(v.get("fix_versions") or []) if v.get("fix_versions") else "no fix released"})
    elif data is None and code != 0:
        return [], True
    return found, False


def scan_stage(files: Iterable[str], run: Callable, threshold: str = "warning", diff_ref: str | None = None) -> dict:
    """EFFECTFUL through `run(argv) -> (exit, output)` (C-3.1): the plan for the changed files is executed;
    the stage refuses at the first finding at or above the threshold, naming the rule and the place, and passes
    below it with the findings kept; a leak from gitleaks refuses whatever the threshold; a missing scanner
    is reported as unrun and does not refuse on silence."""
    thr = THRESHOLD_RANK.get(str(threshold).lower(), 1)
    plan = scan_plan(files, diff_ref)
    if not plan:
        return {"ok": True, "stage": "scan", "reason": "nothing changed, nothing scanned", "findings": []}
    findings: list = []
    unrun: list = []
    for step in plan:
        tool = step["tool"]
        try:
            code, out = run(step["argv"])
        except Exception as e:  # noqa: BLE001 — a scanner that cannot be started is unrun, not a finding
            unrun.append(f"{tool} ({e})")
            continue
        found, absent = _findings_of(tool, int(code), out if isinstance(out, str) else str(out))
        if absent:
            unrun.append(tool)
            continue
        for f in found:
            rank = 2 if tool in ("gitleaks", "pip-audit") else BANDIT_RANK.get(f["severity"], 0)
            if tool == "gitleaks" or rank >= thr:
                where = f"{f['file']}:{f['line']}" if f.get("line") else f["file"]
                return {"ok": False, "stage": "scan",
                        "reason": f"{f['rule']}: {f['text']} at {where} ({tool}, {f['severity'].lower()}, threshold {threshold})",
                        "findings": findings + [f], "unrun": unrun}
            findings.append(f)
    reason = "scan passed" + (f"; unrun: {', '.join(unrun)}" if unrun else "")
    return {"ok": True, "stage": "scan", "reason": reason, "findings": findings, "unrun": unrun}


def policy_input(record: dict, *, changed, stages, last_dispatch) -> dict:
    """PURE (C-3.2): the document the Rego policies judge — the merge record about to be written, the offer's
    changed paths, the stages the queue has run so far, and whether the task's last dispatch record carries its
    provenance (C-8.6). Every denial the policies raise names its clause."""
    prov = last_dispatch.get("provenance") if isinstance(last_dispatch, dict) else None
    return {
        "record": dict(record or {}),
        "changed": [str(p).replace("\\", "/") for p in (changed or [])],
        "stages": [str(s) for s in (stages or [])],
        "provenance_present": bool(prov),
    }


def conftest_command(input_path: str, policy_dir: str, *, conftest: str = "conftest", namespace: str = "main") -> list:
    """PURE (C-3.2): conftest over one JSON input and the layer's policy directory; exit 0 passes, non-zero
    denies with messages that name the clause."""
    return [str(conftest), "test", str(input_path), "-p", str(policy_dir), "--namespace", str(namespace), "--no-color"]


def attach_review(record: dict, text: str, prov: dict) -> dict:
    """Attach a model's review as advisory to a merge record (C-3.4).
    
    If the record is ok, returns a new record with the review attached.
    If the record is not ok, returns it unchanged (never refuses on advisory).
    Never mutates the input record.
    """
    if not isinstance(record, dict):
        return record
    if record.get("ok") is not True:
        return record
    result = dict(record)
    result["review"] = {
        "text": text,
        "provenance": prov,
        "advisory": True,
    }
    return result

