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

### S3.12 — specs can be included or excluded by clause tag
- **verifies:** C-3.12
- **pins:** 299151d9d3e018ac
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_specs_can_be_included_or_excluded_by_clause_tag -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_specs_can_be_included_or_excluded_by_clause_tag` is executed
- **Then** one slow spec must not hold the fast lane hostage.

### S3.13 — a dangerous or unparseable run cmd is refused and recorded red
- **verifies:** C-3.13
- **pins:** 74b503401465c50a
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_a_dangerous_or_unparseable_run_cmd_is_refused_and_recorded_red -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_a_dangerous_or_unparseable_run_cmd_is_refused_and_recorded_red` is executed
- **Then** a run_cmd is an LLM-hop output: refuse it, and say why in the ledger.

### S3.14 — an accepted run cmd is tokenized and never shelled
- **verifies:** C-3.14
- **pins:** b7799b069c08d8e2
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_an_accepted_run_cmd_is_tokenized_and_never_shelled -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_an_accepted_run_cmd_is_tokenized_and_never_shelled` is executed
- **Then** the accepted path runs argv-style with shell=False.

### S3.15 — the worker pool is sized from the machines cores
- **verifies:** C-3.15
- **pins:** 7d0462523910a00b
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_the_worker_pool_is_sized_from_the_machines_cores -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_the_worker_pool_is_sized_from_the_machines_cores` is executed
- **Then** specs are processes, so an 8-worker default on an 18-core box is pure waste.

### S3.16 — pinned env is merged over the inherited environment
- **verifies:** C-3.16
- **pins:** d5445ed57dccc77f
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_pinned_env_is_merged_over_the_inherited_environment -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_pinned_env_is_merged_over_the_inherited_environment` is executed
- **Then** a spec runs in the developer's real env PLUS what the caller pins.

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

### S4.14 — a spec on a superseded clause is reported as redirected
- **verifies:** C-4.14
- **pins:** 3db3976c55b68287
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_a_spec_on_a_superseded_clause_is_reported_as_redirected -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_a_spec_on_a_superseded_clause_is_reported_as_redirected` is executed
- **Then** the old reference still resolves, and the report says where it now points.

### S4.15 — a redirected spec does not credit coverage to the successor
- **verifies:** C-4.15
- **pins:** b44a62340d471d7a
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_a_redirected_spec_does_not_credit_coverage_to_the_successor -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_a_redirected_spec_does_not_credit_coverage_to_the_successor` is executed
- **Then** a spec written against the old wording proves nothing about the new one.

### S4.16 — todo puts every live clause in exactly one bucket
- **verifies:** C-4.16
- **pins:** 4fccc2873a0bce32
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_todo_puts_every_live_clause_in_exactly_one_bucket -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_todo_puts_every_live_clause_in_exactly_one_bucket` is executed
- **Then** the "what is left" answer, in one linear pass, with no clause in limbo.

### S4.17 — a clause proved only against an older wording counts as remaining work
- **verifies:** C-4.17
- **pins:** 59fe1831bf69ebe0
- **run_cmd:** `python -m pytest tests/test_contract_report.py::test_a_clause_proved_only_against_an_older_wording_counts_as_remaining_work -q`
- **Given** the three reports (lib/contract_report.py)
- **When** the spec `test_a_clause_proved_only_against_an_older_wording_counts_as_remaining_work` is executed
- **Then** green is not done when the requirement moved under the spec.

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
- **pins:** 5497f7656e1b8dd6
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

---

## C-7 — proved by the wording critique (lib/contract.py critique)

### S7.1 — a clause with two obligations is reported as not atomic
- **verifies:** C-7.1
- **pins:** 179d44a2bd289fb3
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_a_clause_with_two_obligations_is_reported_as_not_atomic -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_a_clause_with_two_obligations_is_reported_as_not_atomic` is executed
- **Then** one clause proves one thing; two SHALLs cannot be proved by one spec.

### S7.2 — obligations joined with and shall are reported as conjoined
- **verifies:** C-7.2
- **pins:** 2b79fce1fa7cb964
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_obligations_joined_with_and_shall_are_reported_as_conjoined -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_obligations_joined_with_and_shall_are_reported_as_conjoined` is executed
- **Then** the conjunction is the tell; ordinary lists are not.

### S7.3 — unprovable wording is reported as vague
- **verifies:** C-7.3
- **pins:** c0f0d9277c21f329
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_unprovable_wording_is_reported_as_vague -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_unprovable_wording_is_reported_as_vague` is executed
- **Then** "properly" cannot be a run_cmd; quoted mentions are exempt.

### S7.4 — identical wording is reported as duplication not coverage
- **verifies:** C-7.4
- **pins:** e7fa7503d9b83f0f
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_identical_wording_is_reported_as_duplication_not_coverage -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_identical_wording_is_reported_as_duplication_not_coverage` is executed
- **Then** inflation looks like coverage until you compare the sentences.

### S7.5 — superseded and withdrawn wording is exempt from the quality pass
- **verifies:** C-7.5
- **pins:** fc230c81f90b12be
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_superseded_and_withdrawn_wording_is_exempt_from_the_quality_pass -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_superseded_and_withdrawn_wording_is_exempt_from_the_quality_pass` is executed
- **Then** policing dead text would punish the discipline the format asks for.

### S7.6 — wording findings are advisory unless the caller asks for a gate
- **verifies:** C-7.6
- **pins:** 059cb9d8a49345d9
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_wording_findings_are_advisory_unless_the_caller_asks_for_a_gate -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_wording_findings_are_advisory_unless_the_caller_asks_for_a_gate` is executed
- **Then** a linter that fails the build on style gets switched off.

### S7.7 — a multi line note stays out of the normative text and version
- **verifies:** C-7.7
- **pins:** f487c46b44dfe286
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_a_multi_line_note_stays_out_of_the_normative_text_and_version -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_a_multi_line_note_stays_out_of_the_normative_text_and_version` is executed
- **Then** a note leaking into the sentence corrupts both the wording and the pin.

### S7.8 — the frames own contract passes its own quality bar
- **verifies:** C-7.8
- **pins:** edb4562298f63e0f
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_the_frames_own_contract_passes_its_own_quality_bar -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_the_frames_own_contract_passes_its_own_quality_bar` is executed
- **Then** the rules are applied to the file that states them, not only to examples.

### S7.9 — a preference is not an obligation
- **verifies:** C-7.9
- **pins:** f21c5ebb495db86f
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_a_preference_is_not_an_obligation -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_a_preference_is_not_an_obligation` is executed
- **Then** should/may/can leave "is it required?" unanswerable (RFC 2119 keeps them for the non-binding case).

### S7.10 — and or makes the obligation undecidable
- **verifies:** C-7.10
- **pins:** 6f19ab4b093ebef0
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_and_or_makes_the_obligation_undecidable -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_and_or_makes_the_obligation_undecidable` is executed
- **Then** "and/or" hides two requirements behind one sentence.

### S7.11 — a passive obligation without an actor is reported
- **verifies:** C-7.11
- **pins:** 5281257dda7582c1
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_a_passive_obligation_without_an_actor_is_reported -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_a_passive_obligation_without_an_actor_is_reported` is executed
- **Then** "SHALL be logged" — by whom? A spec needs someone to hold responsible.

### S7.12 — a placeholder marks the requirement as unwritten
- **verifies:** C-7.12
- **pins:** 12647edd551cf2d5
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_a_placeholder_marks_the_requirement_as_unwritten -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_a_placeholder_marks_the_requirement_as_unwritten` is executed
- **Then** tBD is an admission, and it must not sit silently in a live clause.

### S7.13 — a clause that dictates the mechanism is reported
- **verifies:** C-7.13
- **pins:** ee0de43ecfa1827a
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_a_clause_that_dictates_the_mechanism_is_reported -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_a_clause_that_dictates_the_mechanism_is_reported` is executed
- **Then** "by ...ing" is HOW, and HOW belongs in design; this frame made exactly that mistake in draft clause C-3.9 and measurement refuted the mechanism.

### S7.14 — an unquantified quality has no exit code
- **verifies:** C-7.14
- **pins:** 800351498f76d04f
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_an_unquantified_quality_has_no_exit_code -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_an_unquantified_quality_has_no_exit_code` is executed
- **Then** "as responsive as possible" cannot be a run_cmd.

### S7.15 — every rule the linter defines fires on the known bad contract
- **verifies:** C-7.15
- **pins:** 66706df7ab6f5a06
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_every_rule_the_linter_defines_fires_on_the_known_bad_contract -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_every_rule_the_linter_defines_fires_on_the_known_bad_contract` is executed
- **Then** a check that can never fire is decoration; this is the dead-rule guard.
