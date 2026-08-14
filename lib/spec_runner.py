"""
Athena spec_runner — run the executable specs, emit a red/green LEDGER (v3.3).

An executable spec is a `Scenario`: prose Given-When-Then (what the requirement means)
plus a `run_cmd` (how it is proved). Athena already had both; what it lacked was the
cheap aggregate — "run everything, tell me which CLAUSES are green" — that makes the
contract queryable in a second instead of by reading code.

Split along the repo's freeze-line:
  * `run_specs` is the ONLY effectful function (subprocess + wall clock, both injected
    at the boundary so tests never shell out).
  * `make_ledger` / `totals` are pure: same results -> same JSON, byte for byte.

The ledger is the artifact every report reads:
  contract_report.todo()  -> "what is left to implement"  (clauses whose specs are red)
  contract_report.drift() -> "what proof is stale"        (green earned under an old
                             clause_version — the requirement moved after the run)

SAFETY: `run_cmd` is an LLM-HOP OUTPUT, not authored code, so it never reaches a shell.
Commands are tokenized with shlex and executed shell-less; a command carrying shell
metacharacters is REFUSED (recorded red) instead of run. Same policy as `planner_verify`
in the MCP verbs — one rule for the whole repo.
"""
from __future__ import annotations

import json
import pathlib
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from lib.ast import Contract, Scenario

_TAIL_CHARS = 400          # keep failures diagnosable without bloating the ledger


@dataclass(frozen=True)
class SpecResult:
    scenario_id: str
    clause_id: str
    passed: bool
    exit_code: int
    duration_ms: int
    clause_version: str = ""   # the pin the spec carried WHEN IT RAN (staleness input)
    run_cmd: str = ""
    output_tail: str = ""


_SHELL_METACHARS = (";", "|", "&", "`", "$", ">", "<", "\n")
_REFUSED = 126          # distinct from 124 timeout / 127 not-found so the ledger says WHY


def _exec(cmd: str, *, cwd: str, timeout: int) -> tuple[int, str]:
    """Default effectful runner: tokenize, run SHELL-LESS, return (exit_code, output tail).

    A run_cmd is an LLM-hop output, so it is refused rather than trusted when it carries
    shell metacharacters — a red spec with a stated reason beats an executed pipeline.
    """
    bad = [ch for ch in _SHELL_METACHARS if ch in cmd]
    if bad:
        return _REFUSED, f"refused: shell metacharacter(s) {bad} in run_cmd (never shell=True)"
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return _REFUSED, f"refused: unparseable run_cmd ({e})"
    if not argv:
        return _REFUSED, "refused: empty run_cmd"
    try:
        p = subprocess.run(argv, shell=False, cwd=cwd, capture_output=True,
                           text=True, timeout=timeout, errors="replace")
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        return p.returncode, out[-_TAIL_CHARS:]
    except subprocess.TimeoutExpired:
        # a hung spec is a RED spec, never an aborted run — the ledger must stay complete
        return 124, f"TIMEOUT after {timeout}s"
    except OSError as e:                      # command not found / not executable
        return 127, f"OSError: {e}"


def select(scenarios: tuple[Scenario, ...], *, clause_prefix: str = "",
           scenario_prefix: str = "") -> tuple[Scenario, ...]:
    """Filter the spec set — running one area's specs is the fast inner loop."""
    out = scenarios
    if clause_prefix:
        out = tuple(s for s in out if s.requirement_key.startswith(clause_prefix))
    if scenario_prefix:
        out = tuple(s for s in out if s.id.startswith(scenario_prefix))
    return out


def run_specs(scenarios: tuple[Scenario, ...], *, cwd: str = ".", timeout: int = 120,
              jobs: int = 8, executor=_exec, clock=None) -> tuple[SpecResult, ...]:
    """EFFECTFUL: run every scenario's run_cmd, concurrently, and time each one.

    Results are returned in DOCUMENT order regardless of completion order, so two runs
    of the same suite produce ledgers that diff cleanly. `executor` and `clock` are
    injected so the pure rollup below can be tested without a shell.
    """
    if clock is None:
        import time
        clock = time.perf_counter

    def one(sc: Scenario) -> SpecResult:
        t0 = clock()
        code, tail = executor(sc.run_cmd, cwd=cwd, timeout=timeout)
        return SpecResult(
            scenario_id=sc.id, clause_id=sc.requirement_key, passed=(code == 0),
            exit_code=code, duration_ms=int((clock() - t0) * 1000),
            clause_version=sc.clause_version, run_cmd=sc.run_cmd,
            output_tail="" if code == 0 else tail,
        )

    if not scenarios:
        return ()
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        return tuple(pool.map(one, scenarios))


def totals(results: tuple[SpecResult, ...]) -> dict:
    """Pure roll-up over the raw results."""
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "duration_ms": sum(r.duration_ms for r in results),
    }


def make_ledger(results: tuple[SpecResult, ...], *, contract: Contract | None = None,
                scenario_version: str = "", ts: str = "") -> dict:
    """Pure: results -> the ledger dict. `ts` is INJECTED (no clock in a pure function)."""
    return {
        "schema": "athena.spec_ledger/1",
        "contract_version": contract.version if contract else "",
        "scenario_version": scenario_version,
        "ts": ts,
        "totals": totals(results),
        "results": [
            {"scenario": r.scenario_id, "clause": r.clause_id,
             "clause_version": r.clause_version, "passed": r.passed,
             "exit_code": r.exit_code, "duration_ms": r.duration_ms,
             "run_cmd": r.run_cmd, "output_tail": r.output_tail}
            for r in results
        ],
    }


def write_ledger(ledger: dict, path: str | pathlib.Path) -> pathlib.Path:
    """EFFECTFUL: persist the ledger (default home: `.athena/spec_ledger.json`)."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    return p


def load_ledger(path: str | pathlib.Path) -> dict:
    """Read a ledger back; `{}` when absent — reports degrade to 'unrun', never crash."""
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
