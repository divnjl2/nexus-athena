"""
Athena spec_runner — run the executable specs, emit a red/green LEDGER (v3.3; batching v3.10).

An executable spec is a `Scenario`: prose Given-When-Then (what the requirement means)
plus a `run_cmd` (how it is proved). Athena already had both; what it lacked was the
cheap aggregate — "run everything, tell me which CLAUSES are green" — that makes the
contract queryable in a second instead of by reading code.

Split along the repo's freeze-line:
  * `run_specs` is the ONLY effectful function (subprocess + wall clock, both injected
    at the boundary so tests never shell out).
  * `make_ledger` / `totals` / `plan_batches` / `attribute` are pure: same inputs -> same
    output, byte for byte.

The ledger is the artifact every report reads:
  contract_report.todo()  -> "what is left to implement"  (clauses whose specs are red)
  contract_report.drift() -> "what proof is stale"        (green earned under an old
                             clause_version — the requirement moved after the run)

SAFETY: `run_cmd` is an LLM-HOP OUTPUT, not authored code, so it never reaches a shell.
Commands are tokenized with shlex and executed shell-less; a command carrying shell
metacharacters is REFUSED (recorded red) instead of run. Same policy as `planner_verify`
in the MCP verbs — one rule for the whole repo.

BATCHING (v3.10, features/core-layer C-6.*): specs whose run_cmd is the same pytest
invocation apart from the test node are run in ONE process, and each spec's verdict and
duration are read back out of pytest's own junit report. Contract-layer clause C-3.9 named
batching and was refuted — plugin autoload was the ten seconds then. With autoload off the
floor moved to interpreter start (523 ms median per spec on one worker; 146 s for 183 specs
against 14.4 s batched) and batching became the lever; measured both times. Three rules keep
a batch from hiding a spec: a node the
report never mentions is RED, a batch that aborted before reporting is rerun one process per
spec, and a clause tagged `isolated` never shares a process.
"""
from __future__ import annotations

import functools
import json
import os
import pathlib
import shlex
import subprocess
import tempfile
import xml.etree.ElementTree as ET
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
_NOT_REPORTED = 4       # pytest's own "usage error / node not found" code, so a missing node
                        # reads the same whether it ran alone or in a batch

#: A clause carrying this tag gets a process of its own (C-6.4).
ISOLATED_TAG = "isolated"
#: Options that change what a run means for the OTHER specs in the process, or that claim
#: the report slot batching needs. An invocation carrying one is never batched (C-6.5).
_UNBATCHABLE = ("-x", "--exitfirst", "--maxfail", "--sw", "--stepwise", "--lf", "--last-failed",
                "--ff", "--failed-first", "--junitxml", "--junit-xml", "--co", "--collect-only")
#: Below this many specs a second process costs more than it saves.
_MIN_BATCH = 8


def default_jobs() -> int:
    """One worker per logical core.

    A spec is a PROCESS, not a coroutine, so the ceiling is the machine, not a guessed 8.
    Capped at 64 so a 128-thread server does not thrash on a 20-spec suite.
    """
    return max(1, min(64, os.cpu_count() or 4))


def _tokenize(cmd: str) -> tuple[list[str], str]:
    """PURE: shell-less argv for a run_cmd, or ([], reason) when it must be refused.

    A run_cmd is an LLM-hop output, so it is refused rather than trusted when it carries
    shell metacharacters — a red spec with a stated reason beats an executed pipeline.
    """
    bad = [ch for ch in _SHELL_METACHARS if ch in cmd]
    if bad:
        return [], f"refused: shell metacharacter(s) {bad} in run_cmd (never shell=True)"
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return [], f"refused: unparseable run_cmd ({e})"
    if not argv:
        return [], "refused: empty run_cmd"
    return argv, ""


def _spawn(argv: list[str], *, cwd: str, timeout: int, env: dict | None = None) -> tuple[int, str]:
    """Default effectful process runner: argv in, (exit code, output tail) out. Shell-less.

    `env` is merged OVER the inherited environment (not replacing it) — a spec runs in the
    developer's real environment plus whatever the caller pins. The reason this exists is
    measured: on a machine with 22 third-party pytest plugins installed, autoloading them
    cost 10.3s of the 10.8s a spec took. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` is a per-project
    decision (a suite may NEED a plugin), so it is a caller knob, never a default.
    """
    try:
        p = subprocess.run(argv, shell=False, cwd=cwd, capture_output=True,
                           text=True, timeout=timeout, errors="replace",
                           env=({**os.environ, **env} if env else None))
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        return p.returncode, out[-_TAIL_CHARS:]
    except subprocess.TimeoutExpired:
        # a hung spec is a RED spec, never an aborted run — the ledger must stay complete
        return 124, f"TIMEOUT after {timeout}s"
    except OSError as e:                      # command not found / not executable
        return 127, f"OSError: {e}"


def _exec(cmd: str, *, cwd: str, timeout: int, env: dict | None = None) -> tuple[int, str]:
    """Default per-command executor: tokenize, refuse or run shell-less (kept as the seam
    every runner spec injects)."""
    argv, why = _tokenize(cmd)
    if not argv:
        return _REFUSED, why
    return _spawn(argv, cwd=cwd, timeout=timeout, env=env)


# --- batching: many specs, one process, every verdict still its own -------------------

def batch_key(run_cmd: str):
    """PURE: (prefix, nodes) when a run_cmd is a batchable pytest invocation, else None.

    Batchable means: pytest (as `pytest ...` or `python -m pytest ...`), at least one test
    node (`path::name` or a `.py` file), and none of the options that would change what the
    run means for the other specs in the process (C-6.5). The prefix is everything that is
    not a node, in order — two specs share a process only when their prefixes are identical.
    """
    argv, why = _tokenize(run_cmd)
    if not argv:
        return None
    prog = pathlib.PurePath(argv[0]).name.lower()
    module_form = "-m" in argv and argv[argv.index("-m") + 1:argv.index("-m") + 2] == ["pytest"]
    if not (prog.startswith("pytest") or module_form):
        return None
    for tok in argv[1:]:
        if any(tok == opt or tok.startswith(opt + "=") for opt in _UNBATCHABLE):
            return None
        if tok.startswith("-") and not tok.startswith("--") and "x" in tok[1:]:
            return None                      # `-xq`: exitfirst folded into a short cluster
    nodes = tuple(t for t in argv[1:]
                  if not t.startswith("-") and t != "pytest" and ("::" in t or t.endswith(".py")))
    if not nodes:
        return None
    prefix = tuple(t for t in argv if t not in nodes)
    return prefix, nodes


def plan_batches(scenarios: tuple[Scenario, ...], *, isolated: frozenset = frozenset(),
                 batch: bool = True) -> tuple[tuple[str, tuple[Scenario, ...]], ...]:
    """PURE: split the spec set into units — ("batch", specs sharing a prefix) or ("one", (spec,)).

    Units keep first-appearance order and members keep document order, so the plan itself is
    deterministic. A spec in `isolated`, a non-pytest command, an unbatchable option or a lone
    member of its prefix group all become a unit of one.
    """
    if not batch:
        return tuple(("one", (s,)) for s in scenarios)
    groups: dict[tuple, list[Scenario]] = {}
    order: list[tuple[str, object]] = []
    for s in scenarios:
        key = None if s.id in isolated else batch_key(s.run_cmd)
        if key is None:
            order.append(("one", (s,)))
            continue
        prefix = key[0]
        if prefix not in groups:
            groups[prefix] = []
            order.append(("group", prefix))
        groups[prefix].append(s)
    out: list[tuple[str, tuple[Scenario, ...]]] = []
    for kind, payload in order:
        if kind == "one":
            out.append((kind, payload))              # type: ignore[arg-type]
        else:
            members = tuple(groups[payload])          # type: ignore[index]
            out.append(("batch" if len(members) > 1 else "one", members))
    return tuple(out)


def _chunks(members: tuple[Scenario, ...], jobs: int) -> tuple[tuple[Scenario, ...], ...]:
    """PURE: split one batch across workers without re-creating the per-process overhead."""
    parts = max(1, min(jobs, len(members) // _MIN_BATCH))
    if parts == 1:
        return (members,)
    size = -(-len(members) // parts)
    return tuple(members[i:i + size] for i in range(0, len(members), size))


def parse_junit(text: str) -> dict:
    """PURE: pytest junit XML -> {(classname, name): {passed, skipped, time, message}}.

    Empty on empty or malformed input, so a batch that aborted before writing a report is
    indistinguishable from one that wrote nothing — which is exactly the case C-6.6 handles.
    """
    if not (text or "").strip():
        return {}
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    out: dict = {}
    for tc in root.iter("testcase"):
        bad = tc.find("failure")
        if bad is None:
            bad = tc.find("error")
        msg = ""
        if bad is not None:
            msg = ((bad.get("message") or "") + "\n" + (bad.text or "")).strip()
        try:
            t = float(tc.get("time") or 0)
        except ValueError:
            t = 0.0
        out[(tc.get("classname", ""), tc.get("name", ""))] = {
            "passed": bad is None, "skipped": tc.find("skipped") is not None,
            "time": t, "message": msg,
        }
    return out


def _node_key(node: str) -> tuple[str, str]:
    """PURE: a pytest node id -> (junit classname, junit name). `tests/test_x.py::TestK::t[1]`
    -> ("tests.test_x.TestK", "t[1]"); a bare file -> ("tests.test_x", "")."""
    path, _, tail = node.replace("\\", "/").partition("::")
    if path.startswith("./"):
        path = path[2:]
    mod = path[:-3] if path.endswith(".py") else path
    mod = mod.strip("/").replace("/", ".")
    parts = tail.split("::") if tail else []
    if parts:
        return ".".join([mod, *parts[:-1]]), parts[-1]
    return mod, ""


def attribute(sc: Scenario, cases: dict) -> SpecResult:
    """PURE: one spec's verdict out of the runner's report (C-6.2, C-6.3, C-6.7).

    A node the report never mentions did not pass: it is red with a stated reason and
    pytest's own not-found code, never silently green.
    """
    key = batch_key(sc.run_cmd)
    nodes = key[1] if key else ()
    hits: list[dict] = []
    for node in nodes:
        cls, name = _node_key(node)
        if name:
            hit = cases.get((cls, name))
            if hit:
                hits.append(hit)
        else:
            hits += [c for (k_cls, _), c in cases.items()
                     if k_cls == cls or k_cls.startswith(cls + ".")]
    duration = int(sum(c["time"] for c in hits) * 1000)
    base = dict(scenario_id=sc.id, clause_id=sc.requirement_key,
                clause_version=sc.clause_version, run_cmd=sc.run_cmd)
    if not hits:
        return SpecResult(passed=False, exit_code=_NOT_REPORTED, duration_ms=0,
                          output_tail=f"not in the runner's report: {' '.join(nodes)}", **base)
    failed = [c for c in hits if not c["passed"]]
    if failed:
        return SpecResult(passed=False, exit_code=1, duration_ms=duration,
                          output_tail=failed[0]["message"][-_TAIL_CHARS:], **base)
    return SpecResult(passed=True, exit_code=0, duration_ms=duration, output_tail="", **base)


def _run_batch(members: tuple[Scenario, ...], *, cwd: str, timeout: int, spawn):
    """EFFECTFUL: one process for the whole batch; None when it ended before any spec reported."""
    prefix = batch_key(members[0].run_cmd)[0]
    nodes = [n for s in members for n in batch_key(s.run_cmd)[1]]
    fd, path = tempfile.mkstemp(prefix="athena-junit-", suffix=".xml")
    os.close(fd)
    try:
        argv = [*prefix, *nodes, f"--junitxml={path}"]
        spawn(argv, cwd=cwd, timeout=timeout * len(members))
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8")
        except OSError:
            text = ""
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    cases = parse_junit(text)
    if not cases:
        return None                              # C-6.6: rerun one process per spec
    return tuple(attribute(s, cases) for s in members)


def select(scenarios: tuple[Scenario, ...], *, clause_prefix: str = "",
           scenario_prefix: str = "", contract: Contract | None = None,
           skip_tags: tuple[str, ...] = (), only_tags: tuple[str, ...] = ()
           ) -> tuple[Scenario, ...]:
    """Filter the spec set — running one area's specs is the fast inner loop.

    Tag filtering reads the CLAUSE's tags (identity lives on the clause, never on the spec),
    which is what makes a fast lane possible: a suite is only as quick as its slowest spec,
    so one `tags: slow` clause must not hold the other forty-five hostage.
    """
    out = scenarios
    if clause_prefix:
        out = tuple(s for s in out if s.requirement_key.startswith(clause_prefix))
    if scenario_prefix:
        out = tuple(s for s in out if s.id.startswith(scenario_prefix))
    if (skip_tags or only_tags) and contract is not None:
        def tags_of(s: Scenario) -> set[str]:
            cl = contract.by_id(s.requirement_key)
            return set(cl.tags) if cl else set()
        if only_tags:
            out = tuple(s for s in out if tags_of(s) & set(only_tags))
        if skip_tags:
            out = tuple(s for s in out if not (tags_of(s) & set(skip_tags)))
    return out


def run_specs(scenarios: tuple[Scenario, ...], *, cwd: str = ".", timeout: int = 120,
              jobs: int = 0, executor=None, clock=None, env: dict | None = None,
              spawn=None, batch: bool = True, contract: Contract | None = None,
              isolate_tag: str = ISOLATED_TAG) -> tuple[SpecResult, ...]:
    """EFFECTFUL: run every scenario's run_cmd and time each one.

    Results are returned in DOCUMENT order regardless of completion order, so two runs
    of the same suite produce ledgers that diff cleanly. `executor` (per command) and `spawn`
    (per argv) and `clock` are injected so the pure rollup below can be tested without a shell.

    Two paths, on purpose:
      * `executor` given -> every spec goes through it, one command at a time (C-6.8). This
        is the seam the runner's own specs rely on, and it never batches.
      * otherwise specs that share a pytest invocation are batched into one process (C-6.1)
        and attributed from its junit report; `batch=False` or a clause tagged `isolated`
        opts a spec out (C-6.4).

    jobs=0 means `default_jobs()` — the machine's core count. Specs are independent
    processes, so under-provisioning the pool is pure wall-clock waste.
    """
    if clock is None:
        import time
        clock = time.perf_counter
    if jobs <= 0:
        jobs = default_jobs()
    if not scenarios:
        return ()

    if executor is not None:
        def one(sc: Scenario) -> SpecResult:
            t0 = clock()
            code, tail = executor(sc.run_cmd, cwd=cwd, timeout=timeout)
            return SpecResult(
                scenario_id=sc.id, clause_id=sc.requirement_key, passed=(code == 0),
                exit_code=code, duration_ms=int((clock() - t0) * 1000),
                clause_version=sc.clause_version, run_cmd=sc.run_cmd,
                output_tail="" if code == 0 else tail,
            )
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            return tuple(pool.map(one, scenarios))

    if spawn is None:
        spawn = functools.partial(_spawn, env=env) if env else _spawn

    isolated: set[str] = set()
    if contract is not None:
        for s in scenarios:
            cl = contract.by_id(s.requirement_key)
            if cl is not None and isolate_tag in cl.tags:
                isolated.add(s.id)

    units: list[tuple[str, tuple[Scenario, ...]]] = []
    for kind, members in plan_batches(scenarios, isolated=frozenset(isolated), batch=batch):
        if kind == "batch":
            units += [("batch", chunk) for chunk in _chunks(members, jobs)]
        else:
            units.append((kind, members))

    def single(sc: Scenario) -> SpecResult:
        t0 = clock()
        argv, why = _tokenize(sc.run_cmd)
        code, tail = (_REFUSED, why) if not argv else spawn(argv, cwd=cwd, timeout=timeout)
        return SpecResult(
            scenario_id=sc.id, clause_id=sc.requirement_key, passed=(code == 0),
            exit_code=code, duration_ms=int((clock() - t0) * 1000),
            clause_version=sc.clause_version, run_cmd=sc.run_cmd,
            output_tail="" if code == 0 else tail,
        )

    def run_unit(unit) -> tuple[SpecResult, ...]:
        kind, members = unit
        if kind == "batch":
            got = _run_batch(members, cwd=cwd, timeout=timeout, spawn=spawn)
            if got is not None:
                return got
        return tuple(single(sc) for sc in members)

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        per_unit = list(pool.map(run_unit, units))
    by_id = {r.scenario_id: r for results in per_unit for r in results}
    return tuple(by_id[s.id] for s in scenarios)


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
