# Contract: Athena Perimeter Layer (v3.18)

> Four of the nine limits named on 2026-09-27 (research digest of the same day) are wiring: the
> oracles exist, the stand-ins exist, the scanners exist, the eval runners exist, and none of them
> speaks the frame's language of clause, verdict and stage. This layer is the adapter in each
> direction: outside tools' findings become verdicts with a clause's threshold (C-1), the external
> world enters specs as fixtures with a freshness and a reproduction loop (C-2), the merge queue
> gains a scan and a policy stage (C-3), and the rungs are watched over time (C-4). Pure functions
> in `lib/` take text and injected runners; the CLI wires the real tools. Ids are allocated once
> and never reused.

## C-1 — Findings become verdicts (lib/findings.py)

- **C-1.1** — WHEN an outside oracle reports findings THE SYSTEM SHALL read them into one shape —
  tool, path, line, severity, rule, message — from Vale's JSON, Bandit's JSON, gitleaks' JSON and
  Semgrep's JSON alike, with severities mapped onto info, warning and error.
  - source: design
  - note: Vale keys `Check/Line/Message/Severity` per file; Bandit `results[].issue_severity`
    LOW/MEDIUM/HIGH; gitleaks a list of `RuleID/File/StartLine/Description`; Semgrep
    `results[].extra.severity` INFO/WARNING/ERROR. A finding the reader cannot place gets line 0,
    never a crash.
- **C-1.2** — WHEN a clause names a severity threshold THE SYSTEM SHALL judge the findings red
  when any finding is at or above it, naming the worst finding with its file and line, and green
  with the count of findings below it.
  - source: design
- **C-1.3** — WHEN an oracle's tool is missing on the host THE SYSTEM SHALL judge the clause unrun,
  neither green nor red, naming the tool and how to install it.
  - source: review
  - note: a lane inside the sandbox may lack a tool the operator's shell has; silence is not proof,
    and a missing scanner is not a finding either.
- **C-1.4** — THE rendered documents of the frame under `features/*/README.md` and `docs/research/`
  SHALL pass Vale with the frame's style in `features/perimeter-layer/vale/` at severity error.
  - source: review
  - note: the first prose oracle; the style is three rules (no emoji, no TBD or TODO, no double
    space) and the config names this clause, which is how the binding guard accepts it.
- **C-1.5** — WHEN a judge model scores a packet or a diff THE SYSTEM SHALL record the score as
  advisory with the judge's provenance, able to refuse only once its agreement with a human sample
  of twenty or more reaches the level the clause names.
  - source: design
  - note: an oracle of the third kind; calibrated before it gates, advisory until then.

## C-2 — The external world enters as fixtures (lib/stands.py)

- **C-2.1** — WHEN a path under a `cassettes/` directory changes in a workspace THE SYSTEM SHALL
  treat it as a spec artefact: the verdict names it as a spec edit and is not green.
  - source: design
  - note: an HTTP replay cassette is the spec's fixture; an executor that re-records it has moved
    the goalposts. Same rule as sealed and golden.
- **C-2.2** — WHEN a cassette is older than the freshness a clause names THE SYSTEM SHALL report
  it stale, advisory, naming the cassette and its age in days.
  - source: design
- **C-2.3** — WHEN a spec asks for a database THE SYSTEM SHALL provide a PostgreSQL from the
  embedded binary on a free local port with a fresh data directory, and stop it and remove the
  directory when the spec ends, leaving no process behind.
  - source: design
  - note: `embedded-postgres` (Apache-2.0, pip wheel with PostgreSQL 18 for win_amd64) — no Docker
    on this host. The port is taken from ATHENA_STAND_PORTS (default 60084-60089): loopback inside
    the range the sandbox's fence permits, so a spec inside the sandbox can reach its own stand.
- **C-2.4** — WHEN a red verdict is turned into a reproduction THE SYSTEM SHALL pack the failing
  command, its tail and the changed files into a packet that asks for a test passing on the
  present behaviour first and its inversion second, never for the fix.
  - source: design
  - note: AssertFlip's move (Apache-2.0, ICSE 2026): a test that passes on the bug, then inverted.
- **C-2.5** — WHEN a reproduction is judged THE SYSTEM SHALL admit it only when the uninverted test
  passes at HEAD and the inverted test fails at HEAD, and record both exits.
  - source: design
- **C-2.6** — WHEN `athena repro` is given a task and the index of one of its red records THE SYSTEM
  SHALL write the reproduction packet, dispatch it to the executor named, judge the result by
  C-2.5 and print the admission with both exits.
  - source: design

## C-3 — Scan and policy are stages of the queue (lib/scan.py)

- **C-3.1** — WHEN an offer reaches the scan stage THE SYSTEM SHALL plan the scanners from the
  changed files only (Bandit for Python, gitleaks over the diff, pip-audit for a requirements
  file) and refuse on a finding at or above the configured severity, naming it.
  - source: design
- **C-3.2** — WHEN a merge record is evaluated by policy THE SYSTEM SHALL render it with the
  changed paths and the stages seen into one JSON input and evaluate the Rego policies under
  `features/perimeter-layer/policy/` with conftest, refusing on the first denial by its message.
  - source: design
  - note: the policies are three: provenance present on the last dispatch record, no sealed, golden
    or cassette path in the diff, the mutation stage seen. conftest (Apache-2.0) is the OSS
    evaluator; the Python side only builds the input.
- **C-3.3** — THE merge queue SHALL run the scan stage after check and the policy stage after
  mutation and before fast-forward, each ending in a merge record like the others.
  - source: design
- **C-3.4** — WHEN a review by a model is attached to an offer THE SYSTEM SHALL record it in the
  merge record as advisory, with the reviewer's provenance, and never refuse on it.
  - source: review
  - note: PR-Agent through LiteLLM to the 9B lane is the reviewer; a 9B flatters, so it advises.

## C-4 — The rungs are watched (lib/drift.py)

- **C-4.1** — WHEN a bench run ends THE SYSTEM SHALL append one row per executor to the series
  under `.athena/bench_series.jsonl`: timestamp, executor, model id, runtime version, the task
  set's digest, tasks run, tasks green and the pass rate.
  - source: design
- **C-4.2** — WHEN the series holds at least the number of points a clause names for an executor
  THE SYSTEM SHALL detect a drop in its pass rate with a one-sided CUSUM and name the point where
  the drop began.
  - source: design
  - note: ruptures (BSD) is available for change points; a CUSUM with two parameters is enough for
    a series of tens of points and is a pure function.
- **C-4.3** — WHEN a drop is detected THE SYSTEM SHALL emit the bd command that opens a bead
  naming the executor, the model, the runtime and the drop, once per drop.
  - source: design
- **C-4.4** — WHEN the task set or its packets differ from the previous row's digest THE SYSTEM
  SHALL report the change of the set apart from a change of the rung, and not count the row in
  the CUSUM.
  - source: review
  - note: a rung's pass rate moves with the packets, not only with the model; the frozen set is
    what makes the series about the model.
- **C-4.5** — WHEN `athena bench` runs with the series flag or `athena drift` is called THE SYSTEM
  SHALL append the rows, evaluate the series per executor and print the drops with their bd
  commands.
  - source: design

## C-5 — The substrate: the scheduler the box does not have (lib/host.py)

- **C-5.1** — WHEN a dispatch or a heavy gate is about to start THE SYSTEM SHALL read the host's free
  RAM and each GPU's free VRAM and park when either is under the floor named, naming the resource
  and both numbers.
  - source: incident
  - note: 27.09 20:02 — vLLM died of a host malloc while crosshair, cosmic-ray, pytest and two foreign
    GPU jobs ran beside two lanes. Windows has no OOM killer and no scheduler that knows a card's
    free memory; every tool places by static config. The floors are this frame's scheduler.
- **C-5.2** — WHEN a lane answers no state THE SYSTEM SHALL wake it through the router with one
  minimal request and wait up to the timeout named for its health before parking with the reason.
  - source: incident
  - note: llama-swap relaunches a dead upstream only on the next request; the daemon parked for
    twenty minutes on 27.09 waiting for a request nobody sent.
- **C-5.3** — WHEN a GPU's compute processes are read THE SYSTEM SHALL name every process whose
  executable is not in that GPU's allow-list and emit one bd command per stranger, once per pid.
  - source: incident
  - note: a foreign llama-server on :8091 held the 3090 for five hours on 27.09 and once before on
    23.09; NVML on WDDM shows presence, not size, so the inventory reports and never kills.
- **C-5.4** — WHEN a heavy gate is spawned THE SYSTEM SHALL wrap its command in the process governor
  with the commit ceiling named when the governor is on the host, and run without it otherwise,
  saying which.
  - source: design
  - note: procgov (MIT) turns the tree into a job object with a commit ceiling and kill-on-close;
    a runaway gate then hits its own cap instead of the lane's malloc.
- **C-5.5** — WHEN `athena daemon` runs with host floors THE SYSTEM SHALL apply C-5.1 before every
  dispatch and C-5.2 and C-5.3 on every tick, and `athena merge` SHALL run the mutation stage under
  C-5.4.
  - source: design

