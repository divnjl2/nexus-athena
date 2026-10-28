"""Curated semantic challenges and valid alternatives for executable specifications.

The manifest and all declared inputs belong to the reviewer, not to the implementer.
Fresh filesystem copies and hash checks are NOT an OS sandbox for malicious programs.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import pathlib
import sys
import tempfile
from dataclasses import asdict

from lib.contract import parse as parse_contract
from lib.scenario_parser import parse as parse_scenarios
from lib.verification import execution_environment, outcome, run_command

SCHEMA = "athena.spec_trust/1"
_IGNORED = {"__pycache__", ".pytest_cache", ".git", ".beads", ".venv", "node_modules"}


def digest(value) -> str:
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def relative(name: str) -> pathlib.PurePosixPath:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError(f"invalid relative path: {name!r}")
    p = pathlib.PurePosixPath(name)
    if p.is_absolute() or any(s in ("..", ".") for s in name.split("/")) or any(s in _IGNORED for s in p.parts):
        raise ValueError(f"path escapes trusted inputs: {name!r}")
    return p


def read_inputs(root: pathlib.Path, names: list[str]) -> dict[str, bytes]:
    files = {}
    for name in names:
        p = root / relative(name)
        if p.is_symlink() or not p.resolve().is_relative_to(root):
            raise ValueError(f"symlink outside trusted inputs: {name}")
        if not p.exists():
            raise ValueError(f"missing trusted input: {name}")
        candidates = [p] if p.is_file() else sorted(p.rglob("*"))
        for f in candidates:
            rel = f.relative_to(root)
            if any(s in _IGNORED for s in rel.parts):
                continue
            if f.is_symlink() or not f.resolve().is_relative_to(root):
                raise ValueError(f"symlink outside trusted inputs: {rel}")
            if f.is_file():
                files[rel.as_posix()] = f.read_bytes()
    if not files:
        raise ValueError("no trusted inputs")
    return files


def environment() -> dict:
    packages = sorted((d.metadata.get("Name", ""), d.version) for d in importlib.metadata.distributions())
    # Hash values, including secrets, without recording their plaintext.
    env = execution_environment()
    return {"python": sys.version, "executable": sys.executable,
            "interpreter_digest": digest(pathlib.Path(sys.executable).read_bytes()),
            "packages_digest": digest(packages), "environment_digest": digest(env)}


def prepare(root: str, manifest: str) -> tuple[dict, dict, dict]:
    base = pathlib.Path(root).resolve()
    path = base / relative(manifest)
    if path.is_symlink() or not path.resolve().is_relative_to(base):
        raise ValueError("manifest outside root")
    m = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(m, dict) or m.get("schema") != SCHEMA:
        raise ValueError("unsupported trust manifest schema")
    required = ("contract", "scenarios", "inputs", "implementation", "passports")
    if any(not m.get(k) for k in required):
        raise ValueError("manifest requires contract, scenarios, inputs, implementation and passports")
    if any(not isinstance(m[k], list) for k in ("inputs", "implementation", "passports")):
        raise ValueError("inputs, implementation and passports must be lists")
    inputs = read_inputs(base, [*m["inputs"], m["contract"], m["scenarios"], manifest])
    contract = parse_contract(inputs[m["contract"]].decode("utf-8"))
    scenarios = parse_scenarios(inputs[m["scenarios"]].decode("utf-8"))
    specs = {s.id: s for s in scenarios}
    allowed = set(m["implementation"])
    for name in allowed:
        p = relative(name)
        if name not in inputs or p.suffix != ".py" or p.name == "conftest.py" or p.name.startswith("test_") or "tests" in p.parts:
            raise ValueError(f"not an implementation input: {name}")
        if name in (manifest, m["contract"], m["scenarios"]):
            raise ValueError(f"protected input: {name}")
    seen = set()
    for p in m["passports"]:
        if not isinstance(p, dict):
            raise ValueError("passport must be an object")
        cid = p.get("clause")
        c = contract.by_id(cid or "")
        if cid in seen or c is None or not c.is_live or p.get("pin") != c.version:
            raise ValueError(f"unknown, duplicate, inactive or stale clause: {cid}")
        seen.add(cid)
        for k in ("intent_source", "owner_decision", "input_domain", "observable_outcome", "oracle_source"):
            if not isinstance(p.get(k), str) or not p[k].strip():
                raise ValueError(f"{cid}: missing {k}")
        for k in ("assumptions", "undefined_behavior", "known_gaps"):
            if not isinstance(p.get(k), list) or any(not isinstance(v, str) for v in p[k]):
                raise ValueError(f"{cid}: {k} must be an explicit list")
        if not isinstance(p.get("specs"), list) or not p["specs"]:
            raise ValueError(f"{cid}: no specs")
        for sid in p["specs"]:
            s = specs.get(sid)
            if s is None or s.requirement_key != cid or s.clause_version != c.version:
                raise ValueError(f"{cid}: unknown, misbound or stale spec {sid}")
        ids = set()
        if not isinstance(p.get("variants", []), list):
            raise ValueError(f"{cid}: variants must be a list")
        for v in p.get("variants", []):
            if not isinstance(v, dict):
                raise ValueError(f"{cid}: variant must be an object")
            if not v.get("id") or v["id"] in ids or v.get("kind") not in ("valid", "violation"):
                raise ValueError(f"{cid}: invalid or duplicate variant")
            ids.add(v["id"])
            if not v.get("reason") or not isinstance(v.get("files"), dict) or not v["files"]:
                raise ValueError(f"{cid}: variant needs rationale and implementation overlay")
            for name, source in v["files"].items():
                relative(name)
                if name not in allowed or not isinstance(source, str):
                    raise ValueError(f"{cid}: unauthorized overlay {name}")
            if v["kind"] == "violation" and not v.get("activation"):
                raise ValueError(f"{cid}: violation needs independent activation")
    context = {"manifest": digest(m), "inputs": {n: digest(b) for n, b in sorted(inputs.items())},
               "environment": environment()}
    return m, inputs, context


def _snapshot(root: pathlib.Path) -> dict:
    return {p.relative_to(root).as_posix(): "SYMLINK" if p.is_symlink() else digest(p.read_bytes())
            for p in root.rglob("*")
            if (p.is_file() or p.is_symlink()) and not any(s in _IGNORED for s in p.relative_to(root).parts)}


def execute(inputs: dict, overlay: dict, cmd: str, *, timeout: int, runner=run_command) -> dict:
    """One command gets a fresh directory; activation cannot contaminate spec execution."""
    with tempfile.TemporaryDirectory(prefix="athena-trust-") as tmp:
        root = pathlib.Path(tmp)
        for name, data in inputs.items():
            target = root / relative(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for name, source in overlay.items():
            (root / relative(name)).write_text(source, encoding="utf-8")
        before = _snapshot(root)
        result = outcome(runner(cmd, cwd=tmp, timeout=timeout))
        after = _snapshot(root)
        changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
        if changed:
            return {"status": "INTEGRITY_FAIL", "exit_code": result.exit_code,
                    "tail": "verifier inputs changed: " + ", ".join(changed), "tests": result.tests}
        return asdict(result)


def audit(root: str, manifest: str, *, timeout: int = 120, runner=run_command) -> dict:
    m, inputs, context = prepare(root, manifest)
    specs = {s.id: s for s in parse_scenarios(inputs[m["scenarios"]].decode("utf-8"))}
    rows = []
    for p in m["passports"]:
        commands = [specs[sid].run_cmd for sid in p["specs"]]
        baseline = [execute(inputs, {}, cmd, timeout=timeout, runner=runner) for cmd in commands]
        challenges = []
        for v in p.get("variants", []):
            row = {"id": v["id"], "kind": v["kind"], "state": "INCOMPLETE", "checks": []}
            if all(r["status"] == "PASS" for r in baseline):
                activated = True
                if v["kind"] == "violation":
                    row["activation_baseline"] = execute(inputs, {}, v["activation"], timeout=timeout, runner=runner)
                    if row["activation_baseline"]["status"] == "ASSERTION_FAIL":
                        row["activation"] = execute(inputs, v["files"], v["activation"], timeout=timeout, runner=runner)
                        activated = row["activation"]["status"] == "PASS"
                    else:
                        activated = False
                        if row["activation_baseline"]["status"] in ("PASS", "INTEGRITY_FAIL"):
                            row["state"] = "FAIL"
                if activated:
                    row["checks"] = [execute(inputs, v["files"], cmd, timeout=timeout, runner=runner) for cmd in commands]
                    states = [r["status"] for r in row["checks"]]
                    if "INTEGRITY_FAIL" in states:
                        row["state"] = "FAIL"
                    elif any(s not in ("PASS", "ASSERTION_FAIL") for s in states):
                        row["state"] = "INCOMPLETE"
                    elif v["kind"] == "valid":
                        row["state"] = "PASS" if all(s == "PASS" for s in states) else "FAIL"
                    else:
                        row["state"] = "PASS" if "ASSERTION_FAIL" in states else "FAIL"
                elif row.get("activation", {}).get("status") == "INTEGRITY_FAIL":
                    row["state"] = "FAIL"
            challenges.append(row)
        controls = {k: sum(v["kind"] == k for v in challenges) for k in ("valid", "violation")}
        bad_baseline = any(r["status"] in ("ASSERTION_FAIL", "INTEGRITY_FAIL") for r in baseline)
        failed = bad_baseline or any(v["state"] == "FAIL" for v in challenges)
        incomplete = (not all(r["status"] == "PASS" for r in baseline) or bool(p["known_gaps"])
                      or not all(controls.values()) or any(v["state"] == "INCOMPLETE" for v in challenges))
        rows.append({"clause": p["clause"], "state": "FAIL" if failed else "INCOMPLETE" if incomplete else "PASS",
                     "baseline": baseline, "controls": controls, "challenges": challenges,
                     "known_gaps": p["known_gaps"], "validity": "DECLARED_BY_OWNER",
                     "adequacy": "CHALLENGED" if challenges else "UNKNOWN"})
    state = "FAIL" if any(r["state"] == "FAIL" for r in rows) else (
        "PASS" if rows and all(r["state"] == "PASS" for r in rows) else "INCOMPLETE")
    challenges = [v for r in rows for v in r["challenges"]]
    metrics = {"clauses": len(rows), "valid_controls": sum(v["kind"] == "valid" for v in challenges),
               "violation_controls": sum(v["kind"] == "violation" for v in challenges),
               "activated": sum(v.get("activation", {}).get("status") == "PASS" for v in challenges),
               "evaluated": sum(v["state"] != "INCOMPLETE" for v in challenges),
               "inconclusive": sum(v["state"] == "INCOMPLETE" for v in challenges),
               "false_accepts": sum(v["kind"] == "violation" and v["state"] == "FAIL"
                                    and bool(v["checks"]) and all(c["status"] == "PASS" for c in v["checks"])
                                    for v in challenges),
               "false_rejects": sum(v["kind"] == "valid" and any(c["status"] == "ASSERTION_FAIL" for c in v["checks"])
                                    for v in challenges)}
    return {"schema": SCHEMA, "state": state, "passed": state == "PASS", "context": context, "metrics": metrics,
            "scope": [r["clause"] for r in rows], "clauses": rows,
            "limits": ["Curated challenges are not completeness or a correctness probability.",
                       "Fresh filesystem copies are not an OS sandbox for hostile code."]}


def check_evidence(root: str, manifest: str, evidence: dict, *, contract_path: str = "") -> dict:
    m, _, context = prepare(root, manifest)
    if not isinstance(evidence, dict):
        return {"state": "FAIL", "reason": "trust receipt must be an object"}
    if contract_path and (pathlib.Path(root) / m["contract"]).resolve() != pathlib.Path(contract_path).resolve():
        return {"state": "FAIL", "reason": "trust evidence belongs to another contract"}
    if evidence.get("schema") != SCHEMA or evidence.get("context") != context:
        return {"state": "FAIL", "reason": "stale or mismatched trust evidence"}
    expected = [p["clause"] for p in m["passports"]]
    rows = evidence.get("clauses", [])
    if evidence.get("scope") != expected or [r.get("clause") for r in rows] != expected:
        return {"state": "FAIL", "reason": "trust evidence scope mismatch"}
    # Receipts are trusted local artifacts, not signed remote attestations. Recheck states
    # rather than trusting the top-level passed boolean alone.
    state = evidence.get("state")
    if state == "PASS" and (not rows or any(r.get("state") != "PASS" for r in rows)):
        return {"state": "FAIL", "reason": "inconsistent trust evidence"}
    return {"state": state if state in ("PASS", "FAIL", "INCOMPLETE") else "FAIL",
            "scope": expected, "reason": "scoped curated challenge evidence"}
