# Scenarios: Athena Contract Layer (v3.3)

> Executable specs for `contract.md`. One spec per clause, ids `S<group>.<index>`
> mirroring the clause number. Each `run_cmd` is a real pytest node in this repo, so
> `athena spec run features/contract-layer/scenarios.md` proves the contract against
> the code that implements it. `pins:` is written by `athena contract pin --write`.

---

## C-1 — proved by the clause parser / resolver (lib/contract.py)

### S1.1 — clause ids are unique and immutable
- **verifies:** C-1.1
- **pins:** 5825240045f27c79
- **run_cmd:** `python -m pytest tests/test_contract.py::test_clause_ids_are_unique_and_immutable -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_clause_ids_are_unique_and_immutable` is executed
- **Then** every clause gets a stable id; a duplicate id is rejected outright.

### S1.2 — old reference still resolves after supersede
- **verifies:** C-1.2
- **pins:** c88c51aa2c8e2c3c
- **run_cmd:** `python -m pytest tests/test_contract.py::test_old_reference_still_resolves_after_supersede -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_old_reference_still_resolves_after_supersede` is executed
- **Then** a clause with successors is superseded, and the OLD id keeps resolving.

### S1.3 — supersede relation is symmetric from either end
- **verifies:** C-1.3
- **pins:** be5a7595ebfcd6d1
- **run_cmd:** `python -m pytest tests/test_contract.py::test_supersede_relation_is_symmetric_from_either_end -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_supersede_relation_is_symmetric_from_either_end` is executed
- **Then** declaring the link on the new OR the old clause yields the same graph.

### S1.4 — branched clause resolves transitively to all current clauses
- **verifies:** C-1.4
- **pins:** 6b2c311480993ca6
- **run_cmd:** `python -m pytest tests/test_contract.py::test_branched_clause_resolves_transitively_to_all_current_clauses -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_branched_clause_resolves_transitively_to_all_current_clauses` is executed
- **Then** a reference follows the chain through several hops and both branches.

### S1.5 — supersede cycle is linted and resolve terminates
- **verifies:** C-1.5
- **pins:** d9a72c266430d91c
- **run_cmd:** `python -m pytest tests/test_contract.py::test_supersede_cycle_is_linted_and_resolve_terminates -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_supersede_cycle_is_linted_and_resolve_terminates` is executed
- **Then** a cycle is reported by lint and never hangs resolve().

### S1.6 — wrapped clause text is not truncated
- **verifies:** C-1.6
- **pins:** d675507a8c51e102
- **run_cmd:** `python -m pytest tests/test_contract.py::test_wrapped_clause_text_is_not_truncated -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_wrapped_clause_text_is_not_truncated` is executed
- **Then** a continuation line is appended, not dropped (the silent-drop class).

### S1.7 — unknown supersede target is linted not crashed
- **verifies:** C-1.7
- **pins:** 1637d6a48a8caf53
- **run_cmd:** `python -m pytest tests/test_contract.py::test_unknown_supersede_target_is_linted_not_crashed -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_unknown_supersede_target_is_linted_not_crashed` is executed
- **Then** a dangling reference is a lint issue, not a parse crash.

---

## C-2 — proved by the clause parser / resolver (lib/contract.py)

### S2.1 — clause version is per clause not whole file
- **verifies:** C-2.1
- **pins:** 546fd715c5f188c3
- **run_cmd:** `python -m pytest tests/test_contract.py::test_clause_version_is_per_clause_not_whole_file -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_clause_version_is_per_clause_not_whole_file` is executed
- **Then** editing one clause must not move any other clause's pin.

### S2.2 — reflowing text does not change the clause version
- **verifies:** C-2.2
- **pins:** 26b95287234b65a1
- **run_cmd:** `python -m pytest tests/test_contract.py::test_reflowing_text_does_not_change_the_clause_version -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_reflowing_text_does_not_change_the_clause_version` is executed
- **Then** re-wrapping a paragraph is not a requirement change.

### S2.3 — pin inserts and refreshes the clause version in scenarios
- **verifies:** C-2.3
- **pins:** f5328f950bf37f01
- **run_cmd:** `python -m pytest tests/test_contract.py::test_pin_inserts_and_refreshes_the_clause_version_in_scenarios -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_pin_inserts_and_refreshes_the_clause_version_in_scenarios` is executed
- **Then** pinning writes `pins:` under `verifies:` and replaces a stale pin.

### S2.4 — scenario parser reads the pin
- **verifies:** C-2.4
- **pins:** 1606d5a8dbcd9289
- **run_cmd:** `python -m pytest tests/test_contract.py::test_scenario_parser_reads_the_pin -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_scenario_parser_reads_the_pin` is executed
- **Then** a pinned spec carries clause_version into the AST; unpinned stays empty.

### S2.5 — render round trips through parse
- **verifies:** C-2.5
- **pins:** c7136eb569ad0405
- **run_cmd:** `python -m pytest tests/test_contract.py::test_render_round_trips_through_parse -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_render_round_trips_through_parse` is executed
- **Then** render(parse(x)) preserves ids, statuses, links and the registry pin.

---

## C-3 — proved by the executable-spec runner (lib/spec_runner.py)

### S3.1 — results keep document order regardless of completion order
- **verifies:** C-3.1
- **pins:** 88031b035435f6e6
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_results_keep_document_order_regardless_of_completion_order -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_results_keep_document_order_regardless_of_completion_order` is executed
- **Then** two runs of the same suite must diff cleanly, so order is by document.

### S3.2 — a hung spec is red and never aborts the run
- **verifies:** C-3.2
- **pins:** a2b05423613897f3
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_a_hung_spec_is_red_and_never_aborts_the_run -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_a_hung_spec_is_red_and_never_aborts_the_run` is executed
- **Then** a timeout makes ONE spec red; the ledger stays complete.

### S3.3 — missing command is red with the os error
- **verifies:** C-3.3
- **pins:** 316ab8df31db9329
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_missing_command_is_red_with_the_os_error -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_missing_command_is_red_with_the_os_error` is executed
- **Then** an unrunnable run_cmd is a red spec, not a crashed runner.

### S3.4 — ledger carries versions and totals
- **verifies:** C-3.4
- **pins:** 78d0566af764a0cc
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_ledger_carries_versions_and_totals -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_ledger_carries_versions_and_totals` is executed
- **Then** the ledger pins contract + scenario versions and rolls up pass/fail.

### S3.5 — ledger is deterministic for the same results
- **verifies:** C-3.5
- **pins:** 40f6c4d0e22eaea0
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_ledger_is_deterministic_for_the_same_results -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_ledger_is_deterministic_for_the_same_results` is executed
- **Then** same results + same injected ts -> byte-identical JSON (golden-able).

### S3.6 — absent or corrupt ledger degrades to unrun
- **verifies:** C-3.6
- **pins:** 8770d7d64c24fe89
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_absent_or_corrupt_ledger_degrades_to_unrun -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_absent_or_corrupt_ledger_degrades_to_unrun` is executed
- **Then** no verdict is 'unrun', never a crash: reports must still answer.

### S3.7 — select filters by clause or spec prefix
- **verifies:** C-3.7
- **pins:** 397833124a320007
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_select_filters_by_clause_or_spec_prefix -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_select_filters_by_clause_or_spec_prefix` is executed
- **Then** running one area's specs is the fast inner loop.

### S3.8 — empty spec set is an empty run not an error
- **verifies:** C-3.8
- **pins:** 68f7fdb181c35ce5
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_empty_spec_set_is_an_empty_run_not_an_error -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_empty_spec_set_is_an_empty_run_not_an_error` is executed
- **Then** filtering everything out yields an empty, still-valid ledger.

### S3.10 — a run cmd with shell metacharacters is refused not executed
- **verifies:** C-3.10
- **pins:** 35235d6704b17b0b
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_a_run_cmd_with_shell_metacharacters_is_refused_not_executed -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_a_run_cmd_with_shell_metacharacters_is_refused_not_executed` is executed
- **Then** a run_cmd is an LLM-hop output: refuse it, never hand it to a shell.

### S3.11 — worker pool follows the machine and env is pinnable
- **verifies:** C-3.11
- **pins:** 34107ed1bb4aacf3
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_worker_pool_follows_the_machine_and_env_is_pinnable -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_worker_pool_follows_the_machine_and_env_is_pinnable` is executed
- **Then** the pool defaults to the machine's cores, and the caller can pin env vars.

### S3.12 — specs can be included or excluded by clause tag
- **verifies:** C-3.12
- **pins:** 299151d9d3e018ac
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_specs_can_be_included_or_excluded_by_clause_tag -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_specs_can_be_included_or_excluded_by_clause_tag` is executed
- **Then** one slow spec must not hold the fast lane hostage.

---

## C-4 — proved by the three reports (lib/contract_report.py)

### S4.1 — a live clause with no spec is uncovered
- **verifies:** C-4.1
- **pins:** 3dd8cbd711131db0
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_a_live_clause_with_no_spec_is_uncovered -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_a_live_clause_with_no_spec_is_uncovered` is executed
- **Then** the "which requirements have no executable spec" answer.

### S4.2 — a spec naming an unknown or withdrawn clause is an orphan
- **verifies:** C-4.2
- **pins:** d45e89032f4dc9b9
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_a_spec_naming_an_unknown_or_withdrawn_clause_is_an_orphan -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_a_spec_naming_an_unknown_or_withdrawn_clause_is_an_orphan` is executed
- **Then** a rotted reference is surfaced, never silently ignored.

### S4.3 — a spec on a superseded clause is redirected and does not credit the successor
- **verifies:** C-4.3
- **pins:** 309748b7f5027574
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_a_spec_on_a_superseded_clause_is_redirected_and_does_not_credit_the_successor -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_a_spec_on_a_superseded_clause_is_redirected_and_does_not_credit_the_successor` is executed
- **Then** the reference resolves forward, but the successor still needs its own proof.

### S4.4 — draft clauses are exempt from coverage
- **verifies:** C-4.4
- **pins:** 294756121b4a2d2d
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_draft_clauses_are_exempt_from_coverage -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_draft_clauses_are_exempt_from_coverage` is executed
- **Then** `draft` is how a requirement is written down before it is owed a proof.

### S4.6 — unspecified clause carries its text so an agent can act
- **verifies:** C-4.6
- **pins:** 2b20895ce8173d9e
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_unspecified_clause_carries_its_text_so_an_agent_can_act -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_unspecified_clause_carries_its_text_so_an_agent_can_act` is executed
- **Then** the todo entry is actionable without re-reading the contract.

### S4.7 — drift flags a spec pinned to an older clause version
- **verifies:** C-4.7
- **pins:** 6b549660553da0ae
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_drift_flags_a_spec_pinned_to_an_older_clause_version -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_drift_flags_a_spec_pinned_to_an_older_clause_version` is executed
- **Then** the requirement moved, the executable spec did not follow.

### S4.8 — drift flags a green earned under a stale clause version
- **verifies:** C-4.8
- **pins:** c11de1096c1488cd
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_drift_flags_a_green_earned_under_a_stale_clause_version -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_drift_flags_a_green_earned_under_a_stale_clause_version` is executed
- **Then** a passing spec can still be proving yesterday's requirement.

### S4.9 — unpinned specs are instrumentation not divergence
- **verifies:** C-4.9
- **pins:** 013909ee03672b07
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_unpinned_specs_are_instrumentation_not_divergence -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_unpinned_specs_are_instrumentation_not_divergence` is executed
- **Then** a repo that never pinned must not look permanently broken.

### S4.10 — drift reports missing and extra specs
- **verifies:** C-4.10
- **pins:** a224cb9d1f4b36da
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_drift_reports_missing_and_extra_specs -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_drift_reports_missing_and_extra_specs` is executed
- **Then** "нет лишних и нет пропущенных" is one report, not two guesses.

### S4.11 — render produces a readable table for any report
- **verifies:** C-4.11
- **pins:** 4c822576521815f3
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_render_produces_a_readable_table_for_any_report -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_render_produces_a_readable_table_for_any_report` is executed
- **Then** the same reports are consumable by a human, not only by JSON.

### S4.12 — todo lists draft clauses as backlog
- **verifies:** C-4.12
- **pins:** 204d06b75b3ba1aa
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_todo_lists_draft_clauses_as_backlog -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_todo_lists_draft_clauses_as_backlog` is executed
- **Then** a written-down-but-not-yet-owed requirement stays visible in the answer.

### S4.13 — todo splits live clauses into unspecified red unrun stale done
- **verifies:** C-4.13
- **pins:** cd49fd34f3fe86a1
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_todo_splits_live_clauses_into_unspecified_red_unrun_stale_done -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_todo_splits_live_clauses_into_unspecified_red_unrun_stale_done` is executed
- **Then** the "what is left" answer, and a stale-proof clause counts as work.

---

## C-5 — proved by the compiler + gate (lib/plan2beads.py, lib/seams.py)

### S5.1 — clause nodes are emitted for every clause with its own version label
- **verifies:** C-5.1
- **pins:** 03c8f3575f65b4bd
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_clause_nodes_are_emitted_for_every_clause_with_its_own_version_label -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_clause_nodes_are_emitted_for_every_clause_with_its_own_version_label` is executed
- **Then** the clause registry (history included) becomes graph structure.

### S5.2 — supersede edge keeps an old clause id reachable
- **verifies:** C-5.2
- **pins:** 2aa5d6382c0ec269
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_supersede_edge_keeps_an_old_clause_id_reachable -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_supersede_edge_keeps_an_old_clause_id_reachable` is executed
- **Then** successor --related--> predecessor, in canonical sorted order.

### S5.3 — validates edge points at the clause not the whole spec
- **verifies:** C-5.3
- **pins:** 553a4f332aea3621
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_validates_edge_points_at_the_clause_not_the_whole_spec -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_validates_edge_points_at_the_clause_not_the_whole_spec` is executed
- **Then** same edge count as v3.1, rooted at the requirement actually proved.

### S5.4 — a spec naming a clause outside the contract refuses to compile
- **verifies:** C-5.4
- **pins:** ca4fa2bfd05656b6
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_a_spec_naming_a_clause_outside_the_contract_refuses_to_compile -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_a_spec_naming_a_clause_outside_the_contract_refuses_to_compile` is executed
- **Then** fail-closed: a rotted reference must never reach the graph.

### S5.5 — without a contract the output is byte identical to v31
- **verifies:** C-5.5
- **pins:** 357aaad8385c4e08
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_without_a_contract_the_output_is_byte_identical_to_v31 -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_without_a_contract_the_output_is_byte_identical_to_v31` is executed
- **Then** adopting the contract layer is opt-in; v3.1 projects see no change.

### S5.6 — an attached but unpinned contract is inert
- **verifies:** C-5.6
- **pins:** 4b1852495f1d562f
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_an_attached_but_unpinned_contract_is_inert -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_an_attached_but_unpinned_contract_is_inert` is executed
- **Then** an unpinned contract must not emit `athena:clause:` labels with no version.

### S5.7 — clause nodes are idempotent on recompile
- **verifies:** C-5.7
- **pins:** 9f4754b9b48eb757
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_clause_nodes_are_idempotent_on_recompile -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_clause_nodes_are_idempotent_on_recompile` is executed
- **Then** a second compile against the same graph creates nothing new.

### S5.8 — the gate fails closed on uncovered clauses and orphan specs
- **verifies:** C-5.8
- **pins:** b1ce5cdfb7546563
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_the_gate_fails_closed_on_uncovered_clauses_and_orphan_specs -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_the_gate_fails_closed_on_uncovered_clauses_and_orphan_specs` is executed
- **Then** seam.contract_bound blocks a contract that is not bound to real specs.

### S5.9 — the gate hash moves when a clause changes
- **verifies:** C-5.9
- **pins:** 4eb74f7656ed4a75
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_the_gate_hash_moves_when_a_clause_changes -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_the_gate_hash_moves_when_a_clause_changes` is executed
- **Then** the seam artifact hash is a fingerprint of ids+versions+statuses.

### S5.11 — clause nodes and edges materialize in a real bd graph
- **verifies:** C-5.11
- **pins:** e52be852a7ebeae3
- **run_cmd:** `python -m pytest tests/test_bd_integration_contract.py::test_clause_nodes_and_edges_materialize_in_a_real_bd_graph -q`
- **Given** the compiled graph against a real bd
- **When** the spec `test_clause_nodes_and_edges_materialize_in_a_real_bd_graph` is executed
- **Then** a real bd accepts the clause nodes, the supersede edge and the clause-rooted validates edge; the graph reads back with one clause node per clause.

---

## C-6 — proved by the clause parser / resolver (lib/contract.py)

### S6.1 — import from spec preserves ears ids verbatim
- **verifies:** C-6.1
- **pins:** 6abb6b0b28a70982
- **run_cmd:** `python -m pytest tests/test_contract.py::test_import_from_spec_preserves_ears_ids_verbatim -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_import_from_spec_preserves_ears_ids_verbatim` is executed
- **Then** migrating an existing spec.md must NOT renumber anything.

### S6.2 — empty contract is rejected
- **verifies:** C-6.2
- **pins:** d62e352e4f681002
- **run_cmd:** `python -m pytest tests/test_contract.py::test_empty_contract_is_rejected -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_empty_contract_is_rejected` is executed
- **Then** a file with no clauses is a parse error, never an empty green contract.

### S6.3 — contract version tracks status changes
- **verifies:** C-6.3
- **pins:** 7b163a9ea7b8913d
- **run_cmd:** `python -m pytest tests/test_contract.py::test_contract_version_tracks_status_changes -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_contract_version_tracks_status_changes` is executed
- **Then** withdrawing a clause moves the registry pin even if no text changed.
