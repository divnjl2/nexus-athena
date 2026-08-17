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

### S1.8 — attributes may be sub bullets instead of inline markers
- **verifies:** C-1.8
- **pins:** 0456b2f3efc812d0
- **run_cmd:** `python -m pytest tests/test_contract.py::test_attributes_may_be_sub_bullets_instead_of_inline_markers -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_attributes_may_be_sub_bullets_instead_of_inline_markers` is executed
- **Then** the sub-bullet form is the same statement as the inline marker.

### S1.9 — lint reports an empty clause
- **verifies:** C-1.9
- **pins:** c47350855ebf4210
- **run_cmd:** `python -m pytest tests/test_contract.py::test_lint_reports_an_empty_clause -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_lint_reports_an_empty_clause` is executed
- **Then** an id with no sentence behind it is a broken reference waiting to happen.

### S1.10 — lint reports a self supersede
- **verifies:** C-1.10
- **pins:** 921bac6fea3c62c3
- **run_cmd:** `python -m pytest tests/test_contract.py::test_lint_reports_a_self_supersede -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_lint_reports_a_self_supersede` is executed
- **Then** a clause replacing itself makes resolve() meaningless.

### S1.11 — lint reports a superseded clause with no successor
- **verifies:** C-1.11
- **pins:** 5fceb4a444353ffd
- **run_cmd:** `python -m pytest tests/test_contract.py::test_lint_reports_a_superseded_clause_with_no_successor -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_lint_reports_a_superseded_clause_with_no_successor` is executed
- **Then** "superseded" without a target leaves every old reference dangling.

### S1.12 — lint reports a clause that is both withdrawn and superseded
- **verifies:** C-1.12
- **pins:** 29b41c6de4833e93
- **run_cmd:** `python -m pytest tests/test_contract.py::test_lint_reports_a_clause_that_is_both_withdrawn_and_superseded -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_lint_reports_a_clause_that_is_both_withdrawn_and_superseded` is executed
- **Then** a requirement is replaced or dropped, never both; the reader cannot tell which one is true.

### S1.13 — lint reports an unknown status
- **verifies:** C-1.13
- **pins:** 1658e48809eb4d32
- **run_cmd:** `python -m pytest tests/test_contract.py::test_lint_reports_an_unknown_status -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_lint_reports_an_unknown_status` is executed
- **Then** an unrecognised status must not silently read as active.

### S1.14 — tags may be declared in the inline marker
- **verifies:** C-1.14
- **pins:** 777a69d97180cb35
- **run_cmd:** `python -m pytest tests/test_contract.py::test_tags_may_be_declared_in_the_inline_marker -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_tags_may_be_declared_in_the_inline_marker` is executed
- **Then** the marker accepts every attribute the sub-bullets do, so an author never has to remember which form supports what.

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

### S3.18 — a lane of one worker runs its specs strictly one at a time
- **verifies:** C-3.18
- **pins:** 196a20c19f969f48
- **run_cmd:** `python -m pytest tests/test_spec_runner.py::test_a_lane_of_one_worker_runs_its_specs_strictly_one_at_a_time -q`
- **Given** the executable-spec runner (lib/spec_runner.py)
- **When** the spec `test_a_lane_of_one_worker_runs_its_specs_strictly_one_at_a_time` is executed
- **Then** a spec that needs an exclusive external resource (a real database, a `bd` repo) fails when two of them overlap. Tag that clause and run its lane with one worker while everything else still runs wide.

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

### S5.13 — a sibling contract is attached and pinned by the frontend
- **verifies:** C-5.13
- **pins:** 4bec28b438f082b4
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_a_sibling_contract_is_attached_and_pinned_by_the_frontend -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_a_sibling_contract_is_attached_and_pinned_by_the_frontend` is executed
- **Then** the wiring that turns a flat plan.md into a contract-rooted Plan was only ever exercised through the CLI; the reverse leg found those lines owned by nothing.

---

## C-6 — proved by the clause parser / resolver (lib/contract.py)

### S5.14 — label references resolve to bd issue ids
- **verifies:** C-5.14
- **pins:** bf26febf12152e1a
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_label_references_resolve_to_bd_issue_ids -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_label_references_resolve_to_bd_issue_ids` is executed
- **Then** every external label in a compiled command is replaced by the issue id it resolves to, and an unknown label is left as it stands.

### S5.15 — an absent or flag-shaped positional is left alone
- **verifies:** C-5.15
- **pins:** df375683915cd369
- **run_cmd:** `python -m pytest tests/test_contract_graph.py::test_an_absent_or_flag_shaped_positional_is_left_alone -q`
- **Given** the compiler + gate (lib/plan2beads.py, lib/seams.py)
- **When** the spec `test_an_absent_or_flag_shaped_positional_is_left_alone` is executed
- **Then** a `bd dep add` with no positional refs is returned unchanged, and a flag sitting in a positional slot is not treated as an issue reference.

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

### S6.4 — import takes only the named section and falls back to the whole file
- **verifies:** C-6.4
- **pins:** 568c3c274a26ef1c
- **run_cmd:** `python -m pytest tests/test_contract.py::test_import_takes_only_the_named_section_and_falls_back_to_the_whole_file -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_import_takes_only_the_named_section_and_falls_back_to_the_whole_file` is executed
- **Then** importing must not sweep prose, user stories or edge cases into the contract.

### S6.5 — render keeps group headings and tags
- **verifies:** C-6.5
- **pins:** 840be16d92eee670
- **run_cmd:** `python -m pytest tests/test_contract.py::test_render_keeps_group_headings_and_tags -q`
- **Given** the clause parser / resolver (lib/contract.py)
- **When** the spec `test_render_keeps_group_headings_and_tags` is executed
- **Then** a rendered contract must stay human-editable, not just machine-parsable.

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

### S7.16 — a clause without an ears trigger is reported as non conforming
- **verifies:** C-7.16
- **pins:** 926413bd21aca417
- **run_cmd:** `python -m pytest tests/test_contract_critique.py::test_a_clause_without_an_ears_trigger_is_reported_as_non_conforming -q`
- **Given** the wording critique (lib/contract.py critique)
- **When** the spec `test_a_clause_without_an_ears_trigger_is_reported_as_non_conforming` is executed
- **Then** "THE SYSTEM SHALL log errors" hides WHEN it must, so nothing can trigger the check; a ubiquitous "THE SYSTEM SHALL ..." opening is legal EARS and passes.

---

## C-8 — proved by the reverse leg (lib/coverage_backed.py)

### S8.1 — coverage paths resolve across source roots
- **verifies:** C-8.1
- **pins:** b51964d1f823cbf0
- **run_cmd:** `python -m pytest tests/test_coverage_backed.py::test_coverage_paths_resolve_across_source_roots -q`
- **Given** the reverse leg (lib/coverage_backed.py)
- **When** the spec `test_coverage_paths_resolve_across_source_roots` is executed
- **Then** cobertura strips the <source> root off every filename, so a plan that says `lib/contract.py` must still find `contract.py` — otherwise every edge reads as fake.

### S8.2 — reverse leg separates in scope gaps from unclaimed code
- **verifies:** C-8.2
- **pins:** 38bccf7739463c91
- **run_cmd:** `python -m pytest tests/test_coverage_backed.py::test_reverse_leg_separates_in_scope_gaps_from_unclaimed_code -q`
- **Given** the reverse leg (lib/coverage_backed.py)
- **When** the spec `test_reverse_leg_separates_in_scope_gaps_from_unclaimed_code` is executed
- **Then** code this contract never claimed is not a spec_gap; burying the real signal under another feature's branches is how a report becomes noise nobody reads.

### S8.3 — an ambiguous basename resolves to nothing
- **verifies:** C-8.3
- **pins:** 26af657eb5058403
- **run_cmd:** `python -m pytest tests/test_coverage_backed.py::test_an_ambiguous_basename_resolves_to_nothing -q`
- **Given** the reverse leg (lib/coverage_backed.py)
- **When** the spec `test_an_ambiguous_basename_resolves_to_nothing` is executed
- **Then** two files named the same must not be silently conflated; an unproven edge a human looks at beats a proven edge that is a guess.

---

## C-9 — proved by the per-clause line map (lib/clause_map.py)

### S9.1 — a clause owns the union of the lines its specs execute
- **verifies:** C-9.1
- **pins:** 89788c8488691dde
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_clause_owns_the_union_of_the_lines_its_specs_execute -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_a_clause_owns_the_union_of_the_lines_its_specs_execute` is executed
- **Then** the map is DERIVED from the clause->spec binding, never authored by hand, so it cannot drift from the code the way an annotation would.

### S9.2 — owners answers which requirements a line serves
- **verifies:** C-9.2
- **pins:** 2a933ab0df796bd4
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_owners_answers_which_requirements_a_line_serves -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_owners_answers_which_requirements_a_line_serves` is executed
- **Then** "I am about to change this line; what am I allowed to break?" Shared code reports EVERY owner, because two requirements leaning on one line is normal.

### S9.3 — the map runner refuses the same commands the spec runner refuses
- **verifies:** C-9.3
- **pins:** 2abb6c2c599d9a85
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_the_map_runner_refuses_the_same_commands_the_spec_runner_refuses -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_the_map_runner_refuses_the_same_commands_the_spec_runner_refuses` is executed
- **Then** this path executes run_cmds too, so it must not become a way around the shell-less rule; the interpreter is normalized so `coverage run -m` can take its place.

### S9.4 — classification separates owned code from another features code
- **verifies:** C-9.4
- **pins:** 8d8f462ea727d991
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_classification_separates_owned_code_from_another_features_code -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_classification_separates_owned_code_from_another_features_code` is executed
- **Then** code the wider suite tests but no clause of THIS contract demands is not a gap; conflating the two is what made the file-level report unreadable.

### S9.5 — a spec that produces no coverage data is skipped not fatal
- **verifies:** C-9.5
- **pins:** c9739b92f2e1a8a8
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_spec_that_produces_no_coverage_data_is_skipped_not_fatal -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_a_spec_that_produces_no_coverage_data_is_skipped_not_fatal` is executed
- **Then** a partial map still answers most queries; aborting the whole collection because one spec misbehaved would make the map unbuildable on any real repo.

### S9.6 — the map pins the versions it was built from
- **verifies:** C-9.6
- **pins:** 5062eb268c4aa240
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_the_map_pins_the_versions_it_was_built_from -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_the_map_pins_the_versions_it_was_built_from` is executed
- **Then** a map is a proof artifact: without pins nobody can tell it went stale.

### S9.7 — lines from json reads coverage output
- **verifies:** C-9.7
- **pins:** 40a2e411cf0ac65d
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_lines_from_json_reads_coverage_output -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_lines_from_json_reads_coverage_output` is executed
- **Then** the collector reads coverage.py's own JSON, so no coverage import leaks into lib/ and the module stays stdlib-only like the rest of the freeze-line.

### S9.8 — a map pinned to another version is stale
- **verifies:** C-9.8
- **pins:** 5e01c4cd2a91792e
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_map_pinned_to_another_version_is_stale -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_a_map_pinned_to_another_version_is_stale` is executed
- **Then** the pins are the cheap check: a map built before the last edit describes a contract that no longer exists, and says nothing about it.

### S9.9 — a clause added since the map was built is unmapped
- **verifies:** C-9.9
- **pins:** 45591269e8897e97
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_clause_added_since_the_map_was_built_is_unmapped -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_a_clause_added_since_the_map_was_built_is_unmapped` is executed
- **Then** `owners()` would answer "nobody owns this" for a clause that simply was not in the world yet; the gate must call that stale, not empty.

### S9.10 — a map entry for a deleted clause is stale
- **verifies:** C-9.10
- **pins:** a1cc53814652a2c6
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_map_entry_for_a_deleted_clause_is_stale -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_a_map_entry_for_a_deleted_clause_is_stale` is executed
- **Then** territory owned by a requirement that no longer exists is a lie about scope.

### S9.11 — the gate fails closed when the map is absent or foreign
- **verifies:** C-9.11
- **pins:** ab19e41731ef4375
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_the_gate_fails_closed_when_the_map_is_absent_or_foreign -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_the_gate_fails_closed_when_the_map_is_absent_or_foreign` is executed
- **Then** "no map" must never read as "nothing to check".

### S9.12 — the gate hash moves when the map goes stale
- **verifies:** C-9.12
- **pins:** e1018f374ef72235
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_the_gate_hash_moves_when_the_map_goes_stale -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_the_gate_hash_moves_when_the_map_goes_stale` is executed
- **Then** the seam's artifact hash fingerprints the pins and the id deltas.

### S9.14 — a map in the previous schema is refused
- **verifies:** C-9.14
- **pins:** 4cbc110b055a1226
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_map_in_the_previous_schema_is_refused -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_a_map_in_the_previous_schema_is_refused` is executed
- **Then** a v1 map cannot prove source freshness at all, so it fails rather than passing on the strength of pins it does not carry.

### S9.15 — only the clauses whose lines moved go stale
- **verifies:** C-9.15
- **pins:** 5df9f904c5afeb7d
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_only_the_clauses_whose_lines_moved_go_stale -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_only_the_clauses_whose_lines_moved_go_stale` is executed
- **Then** the pin covers the lines a clause OWNS, so an edit elsewhere in the same file costs nothing; whole-file pinning made the map unkeepable on an active file.

### S9.16 — a line that no longer exists counts as moved
- **verifies:** C-9.16
- **pins:** d8096b3456fb4366
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_line_that_no_longer_exists_counts_as_moved -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_a_line_that_no_longer_exists_counts_as_moved` is executed
- **Then** a clause whose file shrank past its lines must not digest as unchanged.

### S9.17 — an incremental rebuild keeps the clauses that still hold
- **verifies:** C-9.17
- **pins:** b0fc6f9fe07125ed
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_an_incremental_rebuild_keeps_the_clauses_that_still_hold -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_an_incremental_rebuild_keeps_the_clauses_that_still_hold` is executed
- **Then** re-deriving one clause must cost one spec run, not the whole suite; the untouched entries are carried over byte-for-byte.

### S9.18 — every source root reaches the coverage command
- **verifies:** C-9.18
- **pins:** 17b24da5f23c0301
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_every_source_root_reaches_the_coverage_command -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_every_source_root_reaches_the_coverage_command` is executed
- **Then** more than one coverage source root is passed as one option, because coverage.py lets the last repetition of the flag win.

### S9.20 — a spec that ran and owns nothing is not a failed collection
- **verifies:** C-9.20
- **pins:** 308e05b9aef9a1d0
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_spec_that_ran_and_owns_nothing_is_not_a_failed_collection -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_a_spec_that_ran_and_owns_nothing_is_not_a_failed_collection` is executed
- **Then** a spec that imports nothing from the source roots owns no lines and is still mapped, while a spec whose coverage never ran leaves its clause unmapped.

### S9.21 — merging nothing re-pins the map
- **verifies:** C-9.21
- **pins:** 59cc61fada482100
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_merging_nothing_re_pins_the_map -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_merging_nothing_re_pins_the_map` is executed
- **Then** an incremental rebuild with nothing to re-derive still updates the contract and spec pins, and moves no ownership.

### S9.22 — the map reads branch evidence, not only executed lines
- **verifies:** C-9.22
- **pins:** eb3052927088b188
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_the_map_reads_branch_evidence_not_only_executed_lines -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_the_map_reads_branch_evidence_not_only_executed_lines` is executed
- **Then** an owned line with an arm nothing took is reported half-proved, while an arm out of a line nobody ran stays plain uncovered.

### S9.23 — two specs of one clause can prove both arms between them
- **verifies:** C-9.23
- **pins:** 258c225775c9dcb5
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_two_specs_of_one_clause_can_prove_both_arms_between_them -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_two_specs_of_one_clause_can_prove_both_arms_between_them` is executed
- **Then** partiality is a property of the clause, so one spec taking the true arm and another the false one leaves the branch proved.

### S9.24 — a strengthened spec invalidates the clause it proves
- **verifies:** C-9.24
- **pins:** 12e2ea2e128b812e
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_strengthened_spec_invalidates_the_clause_it_proves -q`
- **Given** the per-clause line map (lib/clause_map.py)
- **When** the spec `test_a_strengthened_spec_invalidates_the_clause_it_proves` is executed
- **Then** a changed test body moves that spec's digest and only that one, and a run_cmd naming no node pins nothing.

### S10.1 — mutations are ast level and skip prose
- **verifies:** C-10.1
- **pins:** 2b289d163041f18e
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_mutations_are_ast_level_and_skip_prose -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_mutations_are_ast_level_and_skip_prose` is executed
- **Then** a regex mutation hits comments and docstrings and produces equivalent mutants that "survive" while meaning nothing; the first probe of this idea drowned in exactly that noise.

### S10.2 — a mutant is run against every owner of its line
- **verifies:** C-10.2
- **pins:** 484147558acc46fd
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_mutant_is_run_against_every_owner_of_its_line -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_mutant_is_run_against_every_owner_of_its_line` is executed
- **Then** scoping to the owning clause alone reported false vacuity: a line owned by 93 clauses is proved by whichever of them asserts it.

### S10.3 — the hunt restores the file and stops at the first killer
- **verifies:** C-10.3
- **pins:** d2a6361c6acddce6
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_the_hunt_restores_the_file_and_stops_at_the_first_killer -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_the_hunt_restores_the_file_and_stops_at_the_first_killer` is executed
- **Then** a harness that leaves the tree dirty on a crash is worse than none, and a mutant needs one killer, not a full sweep.

### S10.4 — the summary names the survivors
- **verifies:** C-10.4
- **pins:** d3ab09f6a162543f
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_the_summary_names_the_survivors -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_the_summary_names_the_survivors` is executed
- **Then** the answer wanted is "which specs prove nothing", not a percentage.

### S10.5 — the corpus labels come from mechanical edits not from a model
- **verifies:** C-10.5
- **pins:** 334a3e4bcef23727
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_the_corpus_labels_come_from_mechanical_edits_not_from_a_model -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_the_corpus_labels_come_from_mechanical_edits_not_from_a_model` is executed
- **Then** ground truth a model produced would make the whole measurement circular.

### S10.6 — a misbound spec is labelled vacuous for the clause it names
- **verifies:** C-10.6
- **pins:** 8374b8af391986ef
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_misbound_spec_is_labelled_vacuous_for_the_clause_it_names -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_misbound_spec_is_labelled_vacuous_for_the_clause_it_names` is executed
- **Then** a perfectly good spec bound to the wrong clause proves nothing about it.

### S10.7 — a refutation without an executable counterexample is discarded
- **verifies:** C-10.7
- **pins:** 2b781b52ff1e9853
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_refutation_without_an_executable_counterexample_is_discarded -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_refutation_without_an_executable_counterexample_is_discarded` is executed
- **Then** the model proposes, the runner disposes: an opinion cannot reject a spec.

### S10.8 — thresholds are fixed before any judge runs and decide eligibility
- **verifies:** C-10.8
- **pins:** 0fd36bd4b42989fb
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_thresholds_are_fixed_before_any_judge_runs_and_decide_eligibility -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_thresholds_are_fixed_before_any_judge_runs_and_decide_eligibility` is executed
- **Then** the promotion from advisory to gate is a number, not an impression.

### S10.9 — a false reject costs more than a miss
- **verifies:** C-10.9
- **pins:** 9f1572d662e63ff8
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_false_reject_costs_more_than_a_miss -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_false_reject_costs_more_than_a_miss` is executed
- **Then** rejecting a good spec is what gets a gate switched off, so it is scored separately and per defect kind.

### S10.10 — the judge is pinned like every other artifact
- **verifies:** C-10.10
- **pins:** 5808de4541765070
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_the_judge_is_pinned_like_every_other_artifact -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_the_judge_is_pinned_like_every_other_artifact` is executed
- **Then** swapping the model must be drift in the record, not silence.

### S10.11 — clause text is neutralised before it reaches a prompt
- **verifies:** C-10.11
- **pins:** 5582f1adc6720fdf
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_clause_text_is_neutralised_before_it_reaches_a_prompt -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_clause_text_is_neutralised_before_it_reaches_a_prompt` is executed
- **Then** a note in a contract is untrusted input the moment a model reads it.

### S10.12 — disagreement with the mutation runner demotes the judge
- **verifies:** C-10.12
- **pins:** 719577111bab1cfe
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_disagreement_with_the_mutation_runner_demotes_the_judge -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_disagreement_with_the_mutation_runner_demotes_the_judge` is executed
- **Then** the dangerous direction is the judge granting a green light the deterministic runner refuses; that alone is enough to demote it.

### S10.13 — a spec function is extracted from its module by name
- **verifies:** C-10.13
- **pins:** 0d6cb9d6aa5a18a4
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_spec_function_is_extracted_from_its_module_by_name -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_spec_function_is_extracted_from_its_module_by_name` is executed
- **Then** the corpus needs the spec's own source, not the whole test file.

### S10.14 — degrading an unknown defect is refused
- **verifies:** C-10.14
- **pins:** 34dd359ef66f306b
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_degrading_an_unknown_defect_is_refused -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_degrading_an_unknown_defect_is_refused` is executed
- **Then** the corpus may only contain degradations this module knows how to make.

### S10.15 — a mutant carries where the break is
- **verifies:** C-10.15
- **pins:** 76cf503b7939b184
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_mutant_carries_where_the_break_is -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_mutant_carries_where_the_break_is` is executed
- **Then** a survivor is only actionable if it says which line stopped mattering.

### S10.16 — a killed run is recoverable from disk
- **verifies:** C-10.16
- **pins:** 87f1faf279309a09
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_killed_run_is_recoverable_from_disk -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_killed_run_is_recoverable_from_disk` is executed
- **Then** `finally` does not survive a kill. The first real run of this harness was stopped by a timeout and left a mutant sitting in lib/, so the pristine sources go to disk BEFORE the first mutation and recovery belongs to the next invocation.

### S10.17 — the hunt stops at the mutant cap
- **verifies:** C-10.17
- **pins:** 6e316e87365b7d68
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_the_hunt_stops_at_the_mutant_cap -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_the_hunt_stops_at_the_mutant_cap` is executed
- **Then** an uncapped sweep ran for ten minutes and was killed; a cap makes the harness usable in CI, and a partial report is still a report.

### S10.18 — mutation runs in a mirror and never touches the working tree
- **verifies:** C-10.18
- **pins:** c3afb2b9f5f7e4fd
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_mutation_runs_in_a_mirror_and_never_touches_the_working_tree -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_mutation_runs_in_a_mirror_and_never_touches_the_working_tree` is executed
- **Then** two runs were killed mid-mutation and left a mutant in lib/ despite `finally`. The harness now mirrors the repo and mutates the copy: the worst a kill can leave behind is a temp folder.

### S10.19 — the prompt template is pinned so changing it is visible
- **verifies:** C-10.19
- **pins:** 4f3000f976a5c14a
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_the_prompt_template_is_pinned_so_changing_it_is_visible -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_the_prompt_template_is_pinned_so_changing_it_is_visible` is executed
- **Then** the first pin hashed the system prompt twice and the user template never, so swapping v1 for v2 — which moved recall from 0.056 to 0.420 — left the record byte-identical. A pin that cannot see the change it exists to record is decoration.

### S10.20 — a surviving raises block is neutralised in a degraded pair
- **verifies:** C-10.20
- **pins:** 620abefcf18c5f49
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_surviving_raises_block_is_neutralised_in_a_degraded_pair -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_surviving_raises_block_is_neutralised_in_a_degraded_pair` is executed
- **Then** `with pytest.raises(...)` IS an assertion. Gutting only the `assert` lines left 18 of 468 pairs labelled vacuous while still proving something, and the judge was RIGHT on 17 of them: the corpus was punishing correctness.

### S10.21 — docstrings are stripped from both halves of the corpus
- **verifies:** C-10.21
- **pins:** 17cee234644a80b9
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_docstrings_are_stripped_from_both_halves_of_the_corpus -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_docstrings_are_stripped_from_both_halves_of_the_corpus` is executed
- **Then** a docstring here NAMES the clause it proves. That is a claim, and showing it to a judge asks it to trust prose over the body; measured cost, 5 points of recall.

### S10.22 — resume reuses only verdicts from the same run
- **verifies:** C-10.22
- **pins:** 3c31e0fc478fb159
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_resume_reuses_only_verdicts_from_the_same_run -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_resume_reuses_only_verdicts_from_the_same_run` is executed
- **Then** a resumed judge run re-judges every pair whose verdict is absent, errored, or recorded under a different pin.

---

## C-11 — proved by the one-command loop (lib/check.py)

### S10.25 — the sweep can be aimed at the lines worth attacking
- **verifies:** C-10.25
- **pins:** 6ceff51c75e60a21
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_the_sweep_can_be_aimed_at_the_lines_worth_attacking -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_the_sweep_can_be_aimed_at_the_lines_worth_attacking` is executed
- **Then** the sweep targets every owned line, the exclusively owned ones, or the half-proved ones, and refuses a selector it does not know.

### S10.26 — a spec the ledger calls red is not a witness
- **verifies:** C-10.26
- **pins:** 0bae9e39d0c6fe7f
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_spec_the_ledger_calls_red_is_not_a_witness -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_spec_the_ledger_calls_red_is_not_a_witness` is executed
- **Then** a spec failing on clean source is disqualified, and a mutant whose only owner is disqualified is unowned rather than survived.

### S11.1 — the loop answers with one verdict and names the failing leg
- **verifies:** C-11.1
- **pins:** 71c4a265a4d3424a
- **run_cmd:** `python -m pytest tests/test_check.py::test_the_loop_answers_with_one_verdict_and_names_the_failing_leg -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_the_loop_answers_with_one_verdict_and_names_the_failing_leg` is executed
- **Then** eight commands in a remembered order is a library; one verdict is a product.

### S11.2 — the first cause is the most upstream failure not the loudest
- **verifies:** C-11.2
- **pins:** 07ffe4e92d7f7906
- **run_cmd:** `python -m pytest tests/test_check.py::test_the_first_cause_is_the_most_upstream_failure_not_the_loudest -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_the_first_cause_is_the_most_upstream_failure_not_the_loudest` is executed
- **Then** a broken contract makes every downstream report meaningless, so it is reported as the cause instead of the ten consequences it produces.

### S11.3 — a leg with no evidence is incomplete never green
- **verifies:** C-11.3
- **pins:** cfc5a713e63441bf
- **run_cmd:** `python -m pytest tests/test_check.py::test_a_leg_with_no_evidence_is_incomplete_never_green -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_a_leg_with_no_evidence_is_incomplete_never_green` is executed
- **Then** silence must not read as proof. The first cut computed `all()` over an EMPTY list of steps, so a leg that never ran was True and a run with a mis-typed --map printed `verdict: PASS` having checked nothing. An audit reproduced exactly that.

### S11.4 — wording and mutation are advisory until asked to block
- **verifies:** C-11.4
- **pins:** b03d23554a5f47ba
- **run_cmd:** `python -m pytest tests/test_check.py::test_wording_and_mutation_are_advisory_until_asked_to_block -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_wording_and_mutation_are_advisory_until_asked_to_block` is executed
- **Then** a linter that fails the build on style, or on a partial mutation sweep, gets switched off; both become gates only on --strict.

### S11.5 — the judge can never block the verdict
- **verifies:** C-11.5
- **pins:** 10d3688a77159fe5
- **run_cmd:** `python -m pytest tests/test_check.py::test_the_judge_can_never_block_the_verdict -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_the_judge_can_never_block_the_verdict` is executed
- **Then** a local model's opinion is advisory by construction; the only door to a gate is a scored corpus, and it is not this file.

### S11.6 — the map gate belongs to the reverse leg
- **verifies:** C-11.6
- **pins:** ed0b831b73d33c70
- **run_cmd:** `python -m pytest tests/test_check.py::test_the_map_gate_belongs_to_the_reverse_leg -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_the_map_gate_belongs_to_the_reverse_leg` is executed
- **Then** map freshness is a code->specs question; putting it under the forward leg would hide which direction actually broke.

### S11.7 — the text view shows every leg and the verdict
- **verifies:** C-11.7
- **pins:** 074a4c32b9a2a6a4
- **run_cmd:** `python -m pytest tests/test_check.py::test_the_text_view_shows_every_leg_and_the_verdict -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_the_text_view_shows_every_leg_and_the_verdict` is executed
- **Then** the answer has to be readable in a terminal without a JSON parser.

### S11.8 — a scaffolded feature is already wired clause to spec to task
- **verifies:** C-11.8
- **pins:** de3a22acb1c37ab8
- **run_cmd:** `python -m pytest tests/test_scaffold.py::test_a_scaffolded_feature_is_already_wired_clause_to_spec_to_task -q`
- **Given** the scaffold (lib/scaffold.py)
- **When** the spec `test_a_scaffolded_feature_is_already_wired_clause_to_spec_to_task` is executed
- **Then** the three files reference each other on creation; a scaffold whose parts do not connect teaches the user the tool is broken, not that their contract is empty.

### S11.9 — a fresh scaffold passes the gates it will be judged by
- **verifies:** C-11.9
- **pins:** 45305c30f415fe5a
- **run_cmd:** `python -m pytest tests/test_scaffold.py::test_a_fresh_scaffold_passes_the_gates_it_will_be_judged_by -q`
- **Given** the scaffold (lib/scaffold.py)
- **When** the spec `test_a_fresh_scaffold_passes_the_gates_it_will_be_judged_by` is executed
- **Then** the first `check` on a new project must be green, or the frame reads as broken before the user has written a single requirement.

### S11.10 — the scaffold tells the user what to do next
- **verifies:** C-11.10
- **pins:** 6c99657035721ea1
- **run_cmd:** `python -m pytest tests/test_scaffold.py::test_the_scaffold_tells_the_user_what_to_do_next -q`
- **Given** the scaffold (lib/scaffold.py)
- **When** the spec `test_the_scaffold_tells_the_user_what_to_do_next` is executed
- **Then** the step after `init` is the one people get wrong; it is printed, not left in a skill file.

### S11.11 — a clean map means the deep lane has nothing to do
- **verifies:** C-11.11
- **pins:** 867c513119746240
- **run_cmd:** `python -m pytest tests/test_check.py::test_a_clean_map_means_the_deep_lane_has_nothing_to_do -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_a_clean_map_means_the_deep_lane_has_nothing_to_do` is executed
- **Then** with nothing drifted there is nothing new to re-prove. Falling back to a whole-repo sweep looked like diligence and cost 1541 owned lines at up to 129 specs per mutant; a sweep is an explicit choice, never a default.

### S11.12 — a mutant whose spec budget ran out is undetermined not a survivor
- **verifies:** C-11.12
- **pins:** 46daafc36ad4f0de
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_mutant_whose_spec_budget_ran_out_is_undetermined_not_a_survivor -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_mutant_whose_spec_budget_ran_out_is_undetermined_not_a_survivor` is executed
- **Then** a line owned by 129 clauses cannot be swept inside a CI budget, and calling the leftover "survived" manufactures a vacuity claim nobody checked. Three outcomes.

### S11.13 — a named but absent input fails instead of vanishing
- **verifies:** C-11.13
- **pins:** 505682789ef8d4b6
- **run_cmd:** `python -m pytest tests/test_check.py::test_a_named_but_absent_input_fails_instead_of_vanishing -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_a_named_but_absent_input_fails_instead_of_vanishing` is executed
- **Then** a path the user typed and the tool cannot find is a mistake, not a choice; it used to make its whole step disappear and the verdict read PASS.

### S11.14 — every mutation outcome reaches the report
- **verifies:** C-11.14
- **pins:** f962bbd9048182f3
- **run_cmd:** `python -m pytest tests/test_check.py::test_every_mutation_outcome_reaches_the_report -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_every_mutation_outcome_reaches_the_report` is executed
- **Then** the detail whitelist dropped `undetermined`, so a run of 20 mutants where NONE was decided rendered as a clean "ok mutation" row. All four states are shown.

### S11.15 — a line no spec owns is unowned not survived
- **verifies:** C-11.15
- **pins:** 3b0c44f5875fb36d
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_line_no_spec_owns_is_unowned_not_survived -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_line_no_spec_owns_is_unowned_not_survived` is executed
- **Then** with no owner there is no witness, so nothing was asked to notice the break. `0 >= 0` used to class that as a survivor: a vacuity claim nobody tested.

### S11.16 — a spec that is already red cannot be a witness
- **verifies:** C-11.16
- **pins:** 88ab6eff4273f022
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_spec_that_is_already_red_cannot_be_a_witness -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_spec_that_is_already_red_cannot_be_a_witness` is executed
- **Then** hunt reads any non-zero exit as "the spec noticed". Without a baseline that includes a spec which was failing before anything was mutated, or a collection error.

### S11.17 — the mirror refuses to delete anything that is not its own
- **verifies:** C-11.17
- **pins:** 7d04d175efa243c2
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_the_mirror_refuses_to_delete_anything_that_is_not_its_own -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_the_mirror_refuses_to_delete_anything_that_is_not_its_own` is executed
- **Then** `isolate` is rm -rf pointed at a user path. An audit ran `mutate --mirror vendor` and it DELETED the vendor directory, reporting success.

### S11.18 — default paths are resolved next to the contract
- **verifies:** C-11.18
- **pins:** 6bb6d047be8eebbd
- **run_cmd:** `python -m pytest tests/test_check.py::test_default_paths_are_resolved_next_to_the_contract -q`
- **Given** the one-command loop (lib/check.py)
- **When** the spec `test_default_paths_are_resolved_next_to_the_contract` is executed
- **Then** an audit checked a scaffolded project from inside this repo and the reverse leg judged it against THIS repo's clause map. A gate answering about the wrong codebase is worse than one that does not run.

### S11.19 — every spec resolves to a test that names the same clause
- **verifies:** C-11.19
- **pins:** a03587e191babc34
- **run_cmd:** `python -m pytest tests/test_binding_guard.py::test_every_spec_resolves_to_a_test_that_names_the_same_clause -q`
- **Given** the clause<->spec binding guard
- **When** the spec `test_every_spec_resolves_to_a_test_that_names_the_same_clause` is executed
- **Then** a binding nobody checks is how a clause gets reported as proved by a test that never mentions it.

### S11.20 — the guard would notice a mis binding
- **verifies:** C-11.20
- **pins:** f93488578608a0a2
- **run_cmd:** `python -m pytest tests/test_binding_guard.py::test_the_guard_would_notice_a_mis_binding -q`
- **Given** the clause<->spec binding guard
- **When** the spec `test_the_guard_would_notice_a_mis_binding` is executed
- **Then** a guard that cannot fail proves nothing; this is its negative control.

### S11.21 — the scaffold ships the test its spec points at
- **verifies:** C-11.21
- **pins:** 13d7eef8e97f5eab
- **run_cmd:** `python -m pytest tests/test_scaffold.py::test_the_scaffold_ships_the_test_its_spec_points_at -q`
- **Given** the scaffold (lib/scaffold.py)
- **When** the spec `test_the_scaffold_ships_the_test_its_spec_points_at` is executed
- **Then** an audit ran the quick start on a clean directory and the first `check` failed: the spec named tests/test_example.py, a path `init` never created.

### S11.22 — the outline names each group's home by exclusivity, not by reach
- **verifies:** C-11.22
- **pins:** d5d297e32478f68b
- **run_cmd:** `python -m pytest tests/test_outline.py::test_the_outline_names_each_group_home_by_exclusivity_not_by_reach -q`
- **Given** the derived outline (lib/outline.py)
- **When** the spec `test_the_outline_names_each_group_home_by_exclusivity_not_by_reach` is executed
- **Then** the module a group owns is named as its home, and the module every group merely passes through is marked shared.

### S11.23 — the outline separates the four statuses and counts proofs
- **verifies:** C-11.23
- **pins:** 31097ea97251ce82
- **run_cmd:** `python -m pytest tests/test_outline.py::test_the_outline_separates_the_four_statuses_and_counts_proofs -q`
- **Given** the derived outline (lib/outline.py)
- **When** the spec `test_the_outline_separates_the_four_statuses_and_counts_proofs` is executed
- **Then** a withdrawn clause is not owed a proof and is not counted live; the outline is where this format's status vocabulary becomes visible.

### S11.24 — the outline says so when there is no map
- **verifies:** C-11.24
- **pins:** cb34381162a7fba2
- **run_cmd:** `python -m pytest tests/test_outline.py::test_the_outline_says_so_when_there_is_no_map -q`
- **Given** the derived outline (lib/outline.py)
- **When** the spec `test_the_outline_says_so_when_there_is_no_map` is executed
- **Then** without a clause map the outline still answers about the contract and says the module column is missing rather than rendering an empty one.

### S11.25 — a module many groups reach is still a home when it holds lines only one owns
- **verifies:** C-11.25
- **pins:** 642fb591aece0905
- **run_cmd:** `python -m pytest tests/test_outline.py::test_a_module_many_groups_reach_is_still_a_home_when_it_holds_lines_only_one_owns -q`
- **Given** the derived outline (lib/outline.py)
- **When** the spec `test_a_module_many_groups_reach_is_still_a_home_when_it_holds_lines_only_one_owns` is executed
- **Then** exclusivity is measured per line, so a module several groups execute is still the home of the group that owns lines in it nobody else owns.

### S10.24 — a partial run reports what it never judged and cannot pass
- **verifies:** C-10.24
- **pins:** 1ae65c2c7c49230b
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_a_partial_run_reports_what_it_never_judged_and_cannot_pass -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_a_partial_run_reports_what_it_never_judged_and_cannot_pass` is executed
- **Then** the score names the unjudged pairs per label, and perfect recall over the half it managed to judge does not open the gate.

### S11.26 — the outline names the half-proved lines of a group
- **verifies:** C-11.26
- **pins:** b5d52c3428661753
- **run_cmd:** `python -m pytest tests/test_outline.py::test_the_outline_names_the_half_proved_lines_of_a_group -q`
- **Given** the derived outline (lib/outline.py)
- **When** the spec `test_the_outline_names_the_half_proved_lines_of_a_group` is executed
- **Then** depth sits next to size in the outline, and the line is absent when nothing is half-proved.

### S11.27 — the default mirror is somewhere the guard will accept
- **verifies:** C-11.27
- **pins:** d3fbb848c4664e15
- **run_cmd:** `python -m pytest tests/test_judge_pilot.py::test_the_default_mirror_is_somewhere_the_guard_will_accept -q`
- **Given** the mutation runner + judge pilot (lib/mutation.py, lib/judge.py)
- **When** the spec `test_the_default_mirror_is_somewhere_the_guard_will_accept` is executed
- **Then** the sweep's default scratch tree sits outside the repository, carries the mirror marker and is reusable on the next run.

### S12.1 — a reference carries the fingerprint of what was reviewed
- **verifies:** C-12.1
- **pins:** c6a143840b1875b3
- **run_cmd:** `python -m pytest tests/test_docrefs.py::test_a_reference_carries_the_fingerprint_of_what_was_reviewed -q`
- **Given** tests/test_docrefs.py
- **When** the spec `test_a_reference_carries_the_fingerprint_of_what_was_reviewed` is executed
- **Then** `target@fingerprint` parses both ways round and the fingerprint stays optional.

### S12.2 — a target that moved since review is a suspect link
- **verifies:** C-12.2
- **pins:** e6e395ef8fdd4f55
- **run_cmd:** `python -m pytest tests/test_docrefs.py::test_a_target_that_moved_since_review_is_a_suspect_link -q`
- **Given** tests/test_docrefs.py
- **When** the spec `test_a_target_that_moved_since_review_is_a_suspect_link` is executed
- **Then** a reference whose document changed since review is reported as a suspect link.

### S12.3 — a missing target is broken and a url is not checked at all
- **verifies:** C-12.3
- **pins:** 579826c0cf848823
- **run_cmd:** `python -m pytest tests/test_docrefs.py::test_a_missing_target_is_broken_and_a_url_is_not_checked_at_all -q`
- **Given** tests/test_docrefs.py
- **When** the spec `test_a_missing_target_is_broken_and_a_url_is_not_checked_at_all` is executed
- **Then** an absent document is broken, a URL is external, and an unpinned reference is neither.

### S12.4 — repinning names only the references that moved
- **verifies:** C-12.4
- **pins:** a25fd9ebb57443ec
- **run_cmd:** `python -m pytest tests/test_docrefs.py::test_repinning_names_only_the_references_that_moved -q`
- **Given** tests/test_docrefs.py
- **When** the spec `test_repinning_names_only_the_references_that_moved` is executed
- **Then** re-pinning reports the edits for a human to read rather than agreeing silently.

### S12.5 — references survive a render round trip
- **verifies:** C-12.5
- **pins:** 699e145aa31b0081
- **run_cmd:** `python -m pytest tests/test_docrefs.py::test_references_survive_a_render_round_trip -q`
- **Given** tests/test_docrefs.py
- **When** the spec `test_references_survive_a_render_round_trip` is executed
- **Then** a render round-trip keeps every reference, so canonicalising is not a data-loss step.

### S13.1 — the marker notation is strictdocs and is read whole
- **verifies:** C-13.1
- **pins:** 37d9710c4df86d66
- **run_cmd:** `python -m pytest tests/test_markers.py::test_the_marker_notation_is_strictdocs_and_is_read_whole -q`
- **Given** tests/test_markers.py
- **When** the spec `test_the_marker_notation_is_strictdocs_and_is_read_whole` is executed
- **Then** markers are read with comma-separated ids and an optional scope.

### S13.2 — each scope resolves to the lines it claims
- **verifies:** C-13.2
- **pins:** 48270fcba55f298c
- **run_cmd:** `python -m pytest tests/test_markers.py::test_each_scope_resolves_to_the_lines_it_claims -q`
- **Given** tests/test_markers.py
- **When** the spec `test_each_scope_resolves_to_the_lines_it_claims` is executed
- **Then** every scope resolves to the lines it claims, at the granularity the clause map speaks.

### S13.3 — a marker the map does not back is decorative
- **verifies:** C-13.3
- **pins:** 2506c7de64858b4e
- **run_cmd:** `python -m pytest tests/test_markers.py::test_a_marker_the_map_does_not_back_is_decorative -q`
- **Given** tests/test_markers.py
- **When** the spec `test_a_marker_the_map_does_not_back_is_decorative` is executed
- **Then** a marker the map cannot back is reported unbacked: decoration, not traceability.

### S13.4 — unknown retired and unresolvable markers are reported apart
- **verifies:** C-13.4
- **pins:** da32e38df85ebc75
- **run_cmd:** `python -m pytest tests/test_markers.py::test_unknown_retired_and_unresolvable_markers_are_reported_apart -q`
- **Given** tests/test_markers.py
- **When** the spec `test_unknown_retired_and_unresolvable_markers_are_reported_apart` is executed
- **Then** unknown, retired and unresolvable markers are reported apart, calling for different fixes.

### S13.5 — a marker shown in backticks is a mention not a marker
- **verifies:** C-13.5
- **pins:** 9df45cc6c4abffc3
- **run_cmd:** `python -m pytest tests/test_markers.py::test_a_marker_shown_in_backticks_is_a_mention_not_a_marker -q`
- **Given** tests/test_markers.py
- **When** the spec `test_a_marker_shown_in_backticks_is_a_mention_not_a_marker` is executed
- **Then** a marker inside backticks or a fenced block is a mention, and line numbering survives.

### S14.1 — the index is the needs json shape a consumer already reads
- **verifies:** C-14.1
- **pins:** baa081e6c3dfda54
- **run_cmd:** `python -m pytest tests/test_export.py::test_the_index_is_the_needs_json_shape_a_consumer_already_reads -q`
- **Given** tests/test_export.py
- **When** the spec `test_the_index_is_the_needs_json_shape_a_consumer_already_reads` is executed
- **Then** the index carries their status vocabulary with ours beside it, and their id links.

### S14.2 — the index carries what a requirements index cannot say
- **verifies:** C-14.2
- **pins:** 9490e074a5f28159
- **run_cmd:** `python -m pytest tests/test_export.py::test_the_index_carries_what_a_requirements_index_cannot_say -q`
- **Given** tests/test_export.py
- **When** the spec `test_the_index_carries_what_a_requirements_index_cannot_say` is executed
- **Then** proved-or-not, owned lines and half-proved lines travel with the ids.

### S14.3 — the export is byte stable
- **verifies:** C-14.3
- **pins:** 86493cfaf133544e
- **run_cmd:** `python -m pytest tests/test_export.py::test_the_export_is_byte_stable -q`
- **Given** tests/test_export.py
- **When** the spec `test_the_export_is_byte_stable` is executed
- **Then** re-exporting an unchanged contract is a no-op in git.

### S14.4 — the oft export is specobject xml their tracer can ingest
- **verifies:** C-14.4
- **pins:** 2e61a9e5574aed7c
- **run_cmd:** `python -m pytest tests/test_export.py::test_the_oft_export_is_specobject_xml_their_tracer_can_ingest -q`
- **Given** tests/test_export.py
- **When** the spec `test_the_oft_export_is_specobject_xml_their_tracer_can_ingest` is executed
- **Then** the export parses as specobject XML, drops withdrawn clauses and escapes its text.

### S15.1 — a codebase is named by package url not by a path
- **verifies:** C-15.1
- **pins:** d267296836d69987
- **run_cmd:** `python -m pytest tests/test_purl.py::test_a_codebase_is_named_by_package_url_not_by_a_path -q`
- **Given** tests/test_purl.py
- **When** the spec `test_a_codebase_is_named_by_package_url_not_by_a_path` is executed
- **Then** a package URL parses into type, namespace, name and version; anything else is refused.

### S15.2 — the same codebase at two commits is the same subject
- **verifies:** C-15.2
- **pins:** 097f1432a9c774c5
- **run_cmd:** `python -m pytest tests/test_purl.py::test_the_same_codebase_at_two_commits_is_the_same_subject -q`
- **Given** tests/test_purl.py
- **When** the spec `test_the_same_codebase_at_two_commits_is_the_same_subject` is executed
- **Then** two package URLs differing only in version name one codebase.

### S15.3 — an unnamed subject is not agreement
- **verifies:** C-15.3
- **pins:** 8a0aaf48a646dc8a
- **run_cmd:** `python -m pytest tests/test_purl.py::test_an_unnamed_subject_is_not_agreement -q`
- **Given** tests/test_purl.py
- **When** the spec `test_an_unnamed_subject_is_not_agreement` is executed
- **Then** an absent or malformed subject on either side is not a match.

### S15.4 — a map from another codebase cannot answer about this one
- **verifies:** C-15.4
- **pins:** a014331bcbd94815
- **run_cmd:** `python -m pytest tests/test_clause_map.py::test_a_map_from_another_codebase_cannot_answer_about_this_one -q`
- **Given** tests/test_clause_map.py
- **When** the spec `test_a_map_from_another_codebase_cannot_answer_about_this_one` is executed
- **Then** a map naming another codebase fails the gate, and an unstated subject is not checked.

### S16.1 — the thinking is given a place to end
- **verifies:** C-16.1
- **pins:** ad6b75de3e68d4d1
- **run_cmd:** `python -m pytest tests/test_judgement_graph.py::test_the_thinking_is_given_a_place_to_end -q`
- **Given** tests/test_judgement_graph.py
- **When** the spec `test_the_thinking_is_given_a_place_to_end` is executed
- **Then** the reasoning call asks for a marked thinking block and caps nothing.

### S16.2 — the verdict call gets the analysis as data and only a shape to fill
- **verifies:** C-16.2
- **pins:** f1dd8d23c50fa2b3
- **run_cmd:** `python -m pytest tests/test_judgement_graph.py::test_the_verdict_call_gets_the_analysis_as_data_and_only_a_shape_to_fill -q`
- **Given** tests/test_judgement_graph.py
- **When** the spec `test_the_verdict_call_gets_the_analysis_as_data_and_only_a_shape_to_fill` is executed
- **Then** the verdict call carries the analysis as data and the answer schema, keeping its tail.

### S16.3 — a stop sequence eats the closing tag and that is not malformed
- **verifies:** C-16.3
- **pins:** eb090aeb32b171f0
- **run_cmd:** `python -m pytest tests/test_judgement_graph.py::test_a_stop_sequence_eats_the_closing_tag_and_that_is_not_malformed -q`
- **Given** tests/test_judgement_graph.py
- **When** the spec `test_a_stop_sequence_eats_the_closing_tag_and_that_is_not_malformed` is executed
- **Then** an unclosed thinking block still yields its reasoning.

### S16.4 — the record keeps the verdict and a handle on the reasoning
- **verifies:** C-16.4
- **pins:** 1410bfe45342ae3e
- **run_cmd:** `python -m pytest tests/test_judgement_graph.py::test_the_record_keeps_the_verdict_and_a_handle_on_the_reasoning -q`
- **Given** tests/test_judgement_graph.py
- **When** the spec `test_the_record_keeps_the_verdict_and_a_handle_on_the_reasoning` is executed
- **Then** the record keeps the verdict and a fingerprint, never the reasoning text.

### S16.5 — a judgement node is an index and never claims proof
- **verifies:** C-16.5
- **pins:** 4f558feea0447cae
- **run_cmd:** `python -m pytest tests/test_judgement_graph.py::test_a_judgement_node_is_an_index_and_never_claims_proof -q`
- **Given** tests/test_judgement_graph.py
- **When** the spec `test_a_judgement_node_is_an_index_and_never_claims_proof` is executed
- **Then** a judgement node carries the pin, links as related, and never claims proof.

### S16.6 — a judgement already in the graph is emitted no second time
- **verifies:** C-16.7
- **pins:** 24e1b121348cf546
- **run_cmd:** `python -m pytest tests/test_judgement_graph.py::test_a_judgement_already_in_the_graph_is_emitted_no_second_time -q`
- **Given** tests/test_judgement_graph.py
- **When** the spec `test_a_judgement_already_in_the_graph_is_emitted_no_second_time` is executed
- **Then** re-running a judge run over a corpus already recorded emits nothing and duplicates nothing.

### S16.8 — a judgement whose end the graph lacks is still recorded
- **verifies:** C-16.8
- **pins:** ce55270c07ebd773
- **run_cmd:** `python -m pytest tests/test_judgement_graph.py::test_a_judgement_whose_end_the_graph_lacks_is_still_recorded -q`
- **Given** tests/test_judgement_graph.py
- **When** the spec `test_a_judgement_whose_end_the_graph_lacks_is_still_recorded` is executed
- **Then** the node is kept while the link the graph cannot resolve is simply not emitted.

### S16.9 — a generation that cycles is told apart from one that is merely long
- **verifies:** C-16.9
- **pins:** 9703d5b3333f343d
- **run_cmd:** `python -m pytest tests/test_judgement_graph.py::test_a_generation_that_cycles_is_told_apart_from_one_that_is_merely_long -q`
- **Given** tests/test_judgement_graph.py
- **When** the spec `test_a_generation_that_cycles_is_told_apart_from_one_that_is_merely_long` is executed
- **Then** the verbatim shape of a ceiling-hitting transcript is caught while a long but progressing one is not.

