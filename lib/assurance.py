"""Per-requirement, bounded assurance. Declarations are not independent attestations.

No execution, model calls, Git, release decision, or inferred requirements. Evidence
is reviewer supplied; hashes detect drift, not a dishonest evidence producer.
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from lib.contract import lint, parse

SCHEMA = "athena.assurance/1"
KINDS = {"execution", "valid_alternative", "violation", "spec_review", "code_review"}
STATES = ("SUPPORTED", "CONTRADICTED", "CONFLICT", "UNKNOWN")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bound(root: Path, name: str) -> bytes:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("evidence paths must be relative POSIX paths")
    path = root / name
    if Path(name).is_absolute() or any(p in ("..", ".") for p in name.split("/")):
        raise ValueError("evidence path escapes root")
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError("symlink evidence is not supported")
    if not path.resolve().is_relative_to(root):
        raise ValueError("evidence path escapes root")
    return path.read_bytes()


def combine(support: bool, contradiction: bool) -> str:
    """Reduce the presence of support and counterevidence without hiding either.

    post: (__return__ == "CONFLICT") == (support and contradiction)
    post: (__return__ == "SUPPORTED") == (support and not contradiction)
    post: (__return__ == "CONTRADICTED") == (contradiction and not support)
    post: (__return__ == "UNKNOWN") == (not support and not contradiction)
    """
    if support and contradiction:
        return "CONFLICT"
    return "SUPPORTED" if support else "CONTRADICTED" if contradiction else "UNKNOWN"


def assess(root: str | Path, manifest: str) -> dict:
    root = Path(root).resolve()
    raw = read_bound(root, manifest)
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("unsupported assurance schema")
    if not isinstance(data.get("implementation"), list) or not data["implementation"] or not all(isinstance(p, str) and p for p in data["implementation"]):
        raise ValueError("manifest requires implementation inputs")
    if not isinstance(data.get("evidence"), list):
        raise ValueError("manifest requires an evidence array")
    contract_bytes = read_bound(root, data["contract"])
    contract = parse(contract_bytes.decode("utf-8"))
    issues = lint(contract)
    if issues or len({c.id for c in contract.clauses}) != len(contract.clauses):
        raise ValueError("invalid contract: " + "; ".join(issues or ["duplicate clause ids"]))
    clauses = {c.id: c for c in contract.clauses if c.is_live}
    rows = {cid: [] for cid in clauses}
    seen = set()
    for ev in data["evidence"]:
        if not isinstance(ev, dict):
            raise ValueError("each evidence observation must be an object")
        if not isinstance(ev.get("id"), str) or not ev["id"] or ev["id"] in seen:
            raise ValueError("evidence ids must be nonempty and unique")
        seen.add(ev["id"])
        if ev["clause"] not in clauses or ev["kind"] not in KINDS:
            raise ValueError("unknown live clause or evidence kind")
        if ev["outcome"] not in ("PASS", "FAIL", "UNKNOWN"):
            raise ValueError("unknown observation outcome")
        if not all(isinstance(ev.get(k), str) and ev[k].strip() for k in ("scope", "producer", "basis")):
            raise ValueError("evidence requires scope, producer and basis")
        if not isinstance(ev.get("inputs"), dict) or not ev["inputs"]:
            raise ValueError("evidence requires exact input fingerprints")
        if data["contract"] not in ev["inputs"]:
            raise ValueError("evidence must bind the contract document")
        required = {data["contract"], *data["implementation"]}
        if not required.issubset(ev["inputs"]):
            raise ValueError("evidence must bind every implementation input")
        if ev["kind"] in {"execution", "valid_alternative", "violation"}:
            if not isinstance(ev.get("checks"), list) or not ev["checks"] or not set(ev["checks"]).issubset(ev["inputs"]):
                raise ValueError("execution and controls must bind their check inputs")
        problems = []
        if ev.get("pin") != clauses[ev["clause"]].version:
            problems.append("stale clause pin")
        for name, digest in ev["inputs"].items():
            try:
                if sha(read_bound(root, name)) != digest:
                    problems.append("changed input: " + name)
            except OSError:
                problems.append("missing input: " + name)
        try:
            if sha(read_bound(root, ev["artifact"])) != ev["artifact_sha256"]:
                problems.append("changed observation artifact")
        except OSError:
            problems.append("missing observation artifact")
        if ev["kind"] == "violation" and ev.get("activated") is not True:
            problems.append("violation activation not established")
        rows[ev["clause"]].append({**ev, "current": not problems, "problems": problems})
    result = []
    for cid, evidence in rows.items():
        current = [e for e in evidence if e["current"]]
        def observed(kind, outcome):
            return any(e["kind"] == kind and e["outcome"] == outcome for e in current)
        execution = combine(observed("execution", "PASS"), observed("execution", "FAIL"))
        # A control PASS means that control met its declared expectation: the valid
        # alternative passed, or the activated defect was detected by the check.
        def control_group(e):
            return (e["scope"], json.dumps(e["inputs"], sort_keys=True), tuple(sorted(e.get("checks", []))))
        alternatives = {control_group(e) for e in current if e['kind'] == 'valid_alternative' and e['outcome'] == 'PASS'}
        violations = {control_group(e) for e in current if e['kind'] == 'violation' and e['outcome'] == 'PASS'}
        executions = {control_group(e) for e in current if e['kind'] == 'execution' and e['outcome'] == 'PASS'}
        failures = {control_group(e) for e in current if e['kind'] == 'execution' and e['outcome'] == 'FAIL'}
        adequacy = combine(bool(alternatives & violations),
                           observed("valid_alternative", "FAIL") or observed("violation", "FAIL") or observed("spec_review", "FAIL"))
        implementation = combine(execution == "SUPPORTED" and adequacy == "SUPPORTED" and bool(executions & alternatives & violations),
                                 adequacy == "SUPPORTED" and bool(failures & alternatives & violations))
        if adequacy == "SUPPORTED" and executions & alternatives & violations and failures & alternatives & violations:
            implementation = "CONFLICT"
        spec = combine(observed("spec_review", "PASS"), observed("spec_review", "FAIL"))
        code = combine(observed("code_review", "PASS"), observed("code_review", "FAIL"))
        result.append({"clause": cid, "requirement": clauses[cid].text,
                       "execution": execution, "check_adequacy": adequacy,
                       "implementation": implementation, "specification": spec,
                       "code_correspondence": code, "evidence": evidence})
    return {"schema": SCHEMA, "manifest_sha256": sha(raw), "denominator": len(result),
            "counts": {dimension: {state: sum(r[dimension] == state for r in result) for state in STATES}
                       for dimension in ("execution", "check_adequacy", "implementation", "specification", "code_correspondence")},
            "limitations": ["Counts measure evidence coverage, not probability of correctness.",
                            "SUPPORTED is limited to the supplied checks and reviewed scope.",
                            "Producers and semantic labels are declarations, not authenticated independence.",
                            "Code review is a scoped judgment, not a proof of all code behavior.",
                            "No release decision is made."], "requirements": result}


def render(report: dict) -> str:
    esc = lambda value: html.escape(str(value))
    parts = ['<!doctype html><meta charset="utf-8"><title>Athena — карта доказательств</title>',
             '<style>body{font:16px system-ui;margin:32px;max-width:1300px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:8px}pre{white-space:pre-wrap}</style>',
             '<h1>Что сделано и чем подтверждено</h1>',
             '<p>Athena строит карту оснований по каждому требованию. Зелёный запуск отдельно; пригодность проверок отдельно; смысл спеки и кода требуют явного ревью. Непроверенные требования остаются в общем списке.</p>',
             '<p>Выполненность получает поддержку или опровержение только при совпадающих границах и входах исполнения, принятой допустимой альтернативы и обнаруженного активированного дефекта. Ошибка самого теста оставляет выполненность неизвестной.</p>',
             '<p>SUPPORTED — подтверждено в пределах указанных проверок; CONTRADICTED — есть опровержение; CONFLICT — свидетельства противоречат; UNKNOWN — оснований недостаточно.</p>',
             '<p>Это покрытие доказательствами, не процент истины. Решение о выдаче результата здесь не принимается.</p>',
             '<table><tr><th>Требование</th><th>Выполненность</th><th>Запуск тестов</th><th>Качество проверок</th><th>Ревью спеки</th><th>Смысл кода</th></tr>']
    for row in report['requirements']:
        parts.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (row['clause']+': '+row['requirement'], row['implementation'], row['execution'], row['check_adequacy'], row['specification'], row['code_correspondence']))+'</tr>')
    parts.append('</table><h2>Основания и ограничения</h2><pre>'+esc(json.dumps(report, ensure_ascii=False, indent=2))+'</pre>')
    return '\n'.join(parts)
