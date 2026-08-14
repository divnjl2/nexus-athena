# Plan: Athena Contract Layer

## Overview
Add a requirement CONTRACT under Athena's existing spec pipeline: numbered clauses with
immutable ids and supersede/branch semantics, per-clause version pins, an executable-spec
ledger, and the three linear-scan reports (coverage / todo / drift). The contract becomes
the root of the provenance graph — `clause <-validates- scenario <-tracks- task` — and a
fail-closed gate (`seam.contract_bound`) refuses to compile a contract that is not bound to
real, passing specs. Retro-compiled: the code shipped first, then this frame was fitted
over it, which is why every task's success_check is an already-green pytest node.

## Out of Scope
- A Gherkin/Cucumber parser (explicitly rejected in `skills/scenario-format`).
- Rewriting existing spec.md files — migration keeps EARS ids verbatim (`contract import`).
- An in-process (sub-second) spec runner; the current lane spawns one pytest per spec.
- Rendering the contract in the Tauri console UI.
- Any change to the v3.1 output when no contract is attached (compat is a requirement).

## Phase 1: Clause language — identity, supersede, branching
**Goal:** A contract file parses into immutable numbered clauses whose old references keep resolving.
**Depends on:** none
### Tasks
- [ ] T1.1 Add Clause/Contract to the Plan AST with resolve() over the supersede chain
  - success_check: `python -m pytest tests/test_contract.py -q`
  - files: `lib/ast.py, tests/test_contract.py`
  - verifies: S1.1, S1.2, S1.4
  - autonomy: high
- [ ] T1.2 Write the line-oriented contract parser with symmetric supersede inference
  - success_check: `python -m pytest tests/test_contract.py -q -k "symmetric or wrapped"`
  - files: `lib/contract.py, tests/test_contract.py`
  - verifies: S1.3, S1.6
- [ ] T1.3 Add lint for dangling refs and supersede cycles
  - success_check: `python -m pytest tests/test_contract.py -q -k "cycle or unknown_supersede"`
  - files: `lib/contract.py`
  - verifies: S1.5, S1.7
### Manual Verification
- `python athena.py contract lint features/contract-layer/contract.md` reports 49 clauses, 0 issues.

## Phase 2: Per-clause pins
**Goal:** A requirement's version is its own, so drift is detectable per clause instead of per file.
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 Hash each clause from its normalized normative text only
  - success_check: `python -m pytest tests/test_contract.py -q -k version`
  - files: `lib/contract.py`
  - verifies: S2.1, S2.2, S2.5
  - autonomy: high
- [ ] T2.2 Write/refresh `pins:` in scenarios.md and read it back in the scenario parser
  - success_check: `python -m pytest tests/test_contract.py -q -k pin`
  - files: `lib/contract.py, lib/scenario_parser.py`
  - verifies: S2.3, S2.4

## Phase 3: Executable-spec ledger
**Goal:** One command runs every spec and leaves a deterministic red/green artifact.
**Depends on:** Phase 2
### Tasks
- [ ] T3.1 Run specs concurrently shell-less, preserve document order, keep hung/unrunnable/refused specs red
  - success_check: `python -m pytest tests/test_spec_runner.py -q`
  - files: `lib/spec_runner.py, tests/test_spec_runner.py`
  - verifies: S3.1, S3.2, S3.3, S3.7, S3.8, S3.10
  - autonomy: high
- [ ] T3.2 Serialize the ledger with version pins, totals and safe degradation
  - success_check: `python -m pytest tests/test_spec_runner.py -q -k ledger`
  - files: `lib/spec_runner.py`
  - verifies: S3.4, S3.5, S3.6
- [ ] T3.3 Size the pool from the machine, allow env pinning, and split lanes by clause tag
  - success_check: `python -m pytest tests/test_spec_runner.py -q -k "worker_pool or tag"`
  - files: `lib/spec_runner.py, athena.py`
  - verifies: S3.11, S3.12

## Phase 4: The three questions
**Goal:** coverage / todo / drift answer in a linear pass over (contract x scenarios x ledger).
**Depends on:** Phase 3
### Tasks
- [ ] T4.1 Implement coverage: uncovered, orphan, redirected, draft-exempt
  - success_check: `python -m pytest tests/test_contract_report.py -q -k "uncovered or orphan or redirected or draft"`
  - files: `lib/contract_report.py, tests/test_contract_report.py`
  - verifies: S4.1, S4.2, S4.3, S4.4
  - autonomy: high
- [ ] T4.2 Implement todo bucketing (incl. the stale-proof bucket) with actionable payloads
  - success_check: `python -m pytest tests/test_contract_report.py -q -k todo`
  - files: `lib/contract_report.py`
  - verifies: S4.6, S4.12, S4.13
- [ ] T4.3 Implement drift: spec_drift, stale_proof, missing/extra, unpinned advisory
  - success_check: `python -m pytest tests/test_contract_report.py -q -k "drift or unpinned"`
  - files: `lib/contract_report.py`
  - verifies: S4.7, S4.8, S4.9, S4.10
- [ ] T4.4 Add the text renderer for all three reports
  - success_check: `python -m pytest tests/test_contract_report.py -q -k render`
  - files: `lib/contract_report.py`
  - verifies: S4.11

## Phase 5: Contract in the graph + the gate
**Goal:** Clauses become graph nodes and an unbound contract cannot compile; v3.1 output is untouched.
**Depends on:** Phase 4
### Tasks
- [ ] T5.1 Emit clause nodes, supersede edges and clause-rooted validates edges
  - success_check: `python -m pytest tests/test_contract_graph.py -q -k "clause_nodes or supersede or validates"`
  - files: `lib/plan2beads.py, lib/frontend.py, tests/test_contract_graph.py`
  - verifies: S5.1, S5.2, S5.3, S5.11
- [ ] T5.2 Fail closed on out-of-contract refs; keep unpinned contracts inert and recompiles idempotent
  - success_check: `python -m pytest tests/test_contract_graph.py -q -k "refuses or unpinned or idempotent or identical"`
  - files: `lib/plan2beads.py`
  - verifies: S5.4, S5.5, S5.6, S5.7
- [ ] T5.3 Add seam.contract_bound and wire it into the CLI
  - success_check: `python -m pytest tests/test_contract_graph.py -q -k gate`
  - files: `lib/seams.py, athena.py`
  - verifies: S5.8, S5.9
### Manual Verification
- `python athena.py seam contract_bound features/contract-layer/plan.md --speckit off` passes.

## Phase 6: Migration
**Goal:** An existing Athena project adopts the contract without renumbering a single id.
**Depends on:** Phase 1
### Tasks
- [ ] T6.1 Import EARS criteria out of a spec.md, preserving ids, and reject empty contracts
  - success_check: `python -m pytest tests/test_contract.py -q -k "import or empty or status_changes"`
  - files: `lib/contract.py, athena.py`
  - verifies: S6.1, S6.2, S6.3
  - autonomy: high
### Manual Verification
- `python athena.py contract import examples/snake_game/spec.md -o /tmp/c.md` keeps `R1.1`.

## Phase 7: The reverse leg made honest
**Goal:** code->spec answers survive a real coverage.xml and separate unclaimed code from gaps.
**Depends on:** Phase 5
### Tasks
- [ ] T7.1 Resolve coverage paths across source roots without guessing on ambiguity
  - success_check: `python -m pytest tests/test_coverage_backed.py -q -k "resolve or ambiguous"`
  - files: `lib/coverage_backed.py, tests/test_coverage_backed.py`
  - verifies: S8.1, S8.3
- [ ] T7.2 Separate in-scope spec gaps from code this contract never claimed
  - success_check: `python -m pytest tests/test_coverage_backed.py -q -k separates`
  - files: `lib/coverage_backed.py`
  - verifies: S8.2
### Manual Verification
- `python athena.py --speckit off trace-coverage features/contract-layer/plan.md --coverage <xml>`
  reports 0 unproven edges on a coverage run of the specs themselves.

## Phase 8: Line-level ownership
**Goal:** every requirement knows which lines it owns, so "what breaks if I change this" is a query.
**Depends on:** Phase 7
### Tasks
- [ ] T8.1 Derive the per-clause line map by running each spec alone under coverage
  - success_check: `python -m pytest tests/test_clause_map.py -q`
  - files: `lib/clause_map.py, tests/test_clause_map.py`
  - verifies: S9.1, S9.3, S9.5, S9.6, S9.7
  - autonomy: high
- [ ] T8.2 Answer line ownership and separate owned code from another feature's code
  - success_check: `python -m pytest tests/test_clause_map.py -q -k "owners or classification"`
  - files: `lib/clause_map.py, athena.py`
  - verifies: S9.2, S9.4
### Manual Verification
- `python athena.py contract map features/contract-layer/contract.md` maps every live clause.
- `python athena.py contract owners lib/seams.py:214 --map .athena/clause_map.json` names C-5.8.
