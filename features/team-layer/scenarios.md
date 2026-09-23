# Scenarios: Athena Team Layer (v3.11)

> Executable specs for `contract.md`. One spec per clause, ids `S<group>.<index>`
> mirroring the clause number. `pins:` is written by `athena contract pin --write`.

---

## C-1 — proved by the case runner (lib/cases.py)

### S1.1 — a case file parses given, when, then and refuses a missing part
- **verifies:** C-1.1
- **pins:** 1eb1208aef0c18d0
- **run_cmd:** `python -m pytest tests/test_cases.py::test_a_case_file_parses_given_when_then_and_refuses_a_missing_part -q`
- **Given** tests/test_cases.py
- **When** the spec `test_a_case_file_parses_given_when_then_and_refuses_a_missing_part` is executed
- **Then** a complete case parses; one without a `then` is refused with the missing part named.

### S1.2 — a case runs in the current process without spawning
- **verifies:** C-1.2
- **pins:** 24fbcd65350871e2
- **run_cmd:** `python -m pytest tests/test_cases.py::test_a_case_runs_in_the_current_process_without_spawning -q`
- **Given** tests/test_cases.py
- **When** the spec `test_a_case_runs_in_the_current_process_without_spawning` is executed
- **Then** a case against a pure function passes with no subprocess call.

### S1.3 — a failed then is red with expected and actual
- **verifies:** C-1.3
- **pins:** c33ce8f0ecd645d9
- **run_cmd:** `python -m pytest tests/test_cases.py::test_a_failed_then_is_red_with_expected_and_actual -q`
- **Given** tests/test_cases.py
- **When** the spec `test_a_failed_then_is_red_with_expected_and_actual` is executed
- **Then** the message of a failed check carries the expected and the actual value.

### S1.4 — an expected exception passes only when raised
- **verifies:** C-1.4
- **pins:** ff8db4461349adbd
- **run_cmd:** `python -m pytest tests/test_cases.py::test_an_expected_exception_passes_only_when_raised -q`
- **Given** tests/test_cases.py
- **When** the spec `test_an_expected_exception_passes_only_when_raised` is executed
- **Then** a `raises` check passes on the named exception and fails when nothing is raised.

### S1.5 — a case scenario derives a replayable run command
- **verifies:** C-1.5
- **pins:** e97de3054fe7bdde
- **run_cmd:** `python -m pytest tests/test_cases.py::test_a_case_scenario_derives_a_replayable_run_command -q`
- **Given** tests/test_cases.py
- **When** the spec `test_a_case_scenario_derives_a_replayable_run_command` is executed
- **Then** a scenario with `case:` and no `run_cmd` parses and its run_cmd replays the case through the CLI.

### S1.6 — case and command scenarios share one ledger
- **verifies:** C-1.6
- **pins:** 8145dc5815039950
- **run_cmd:** `python -m pytest tests/test_cases.py::test_case_and_command_scenarios_share_one_ledger -q`
- **Given** tests/test_cases.py
- **When** the spec `test_case_and_command_scenarios_share_one_ledger` is executed
- **Then** run_specs runs the case in-process, the command through the spawn seam, and returns both in document order.

### S1.7 — a case naming another clause is a broken binding
- **verifies:** C-1.7
- **pins:** 5e45005098edd3ad
- **run_cmd:** `python -m pytest tests/test_cases.py::test_a_case_naming_another_clause_is_a_broken_binding -q`
- **Given** tests/test_cases.py
- **When** the spec `test_a_case_naming_another_clause_is_a_broken_binding` is executed
- **Then** binding_issues names the scenario whose case documents a different clause.

## C-2 — proved by the decision-record module and the repository's own files (lib/adr.py)

### S2.1 — a decision record requires its six parts
- **verifies:** C-2.1
- **pins:** 213433a796b9055e
- **run_cmd:** `python -m pytest tests/test_adr.py::test_a_decision_record_requires_its_six_parts -q`
- **Given** tests/test_adr.py
- **When** the spec `test_a_decision_record_requires_its_six_parts` is executed
- **Then** a record missing Status or Consequences is a lint issue; the repository's own records pass.

### S2.2 — a decision nobody cites is unlinked
- **verifies:** C-2.2
- **pins:** fb8c311611a407b6
- **run_cmd:** `python -m pytest tests/test_adr.py::test_a_decision_nobody_cites_is_unlinked -q`
- **Given** tests/test_adr.py
- **When** the spec `test_a_decision_nobody_cites_is_unlinked` is executed
- **Then** a record cited by no clause is listed unlinked; a cited one is not.

### S2.3 — the ownership file names a human for core, contracts and decisions
- **verifies:** C-2.3
- **pins:** afc4a8f5bde1cf97
- **run_cmd:** `python -m pytest tests/test_adr.py::test_the_ownership_file_names_a_human_for_core_contracts_and_decisions -q`
- **Given** tests/test_adr.py
- **When** the spec `test_the_ownership_file_names_a_human_for_core_contracts_and_decisions` is executed
- **Then** CODEOWNERS has an owner line for CORE.md, features/*/contract.md and docs/adr/.

### S2.4 — the design step sends decisions to the records directory
- **verifies:** C-2.4
- **pins:** 1793b388116072e5
- **run_cmd:** `python -m pytest tests/test_adr.py::test_the_design_step_sends_decisions_to_the_records_directory -q`
- **Given** tests/test_adr.py
- **When** the spec `test_the_design_step_sends_decisions_to_the_records_directory` is executed
- **Then** commands/crisp/3_design.md names docs/adr as where Design Decisions are written.

### S2.5 — a decision record parses, as a case
- **verifies:** C-2.1
- **pins:** 213433a796b9055e
- **case:** `features/team-layer/cases/S2.5-adr-parses.json`
- **Given** the text of a decision record
- **When** lib.adr:parse_adr is called on it in-process
- **Then** id, status, date and the decision section come back as written.

## C-3 — proved by the intake module (lib/intake.py)

### S3.1 — intake appends a draft clause with source and fresh id
- **verifies:** C-3.1
- **pins:** 72e6dfd41b36d6f7
- **run_cmd:** `python -m pytest tests/test_intake.py::test_intake_appends_a_draft_clause_with_source_and_fresh_id -q`
- **Given** tests/test_intake.py
- **When** the spec `test_intake_appends_a_draft_clause_with_source_and_fresh_id` is executed
- **Then** after intake the contract has one more clause, draft, with the given source and an unused id.

### S3.2 — intake binds a spec so coverage and todo see it
- **verifies:** C-3.2
- **pins:** c3b92666808ba1f8
- **run_cmd:** `python -m pytest tests/test_intake.py::test_intake_binds_a_spec_so_coverage_and_todo_see_it -q`
- **Given** tests/test_intake.py
- **When** the spec `test_intake_binds_a_spec_so_coverage_and_todo_see_it` is executed
- **Then** coverage shows no draft_uncovered and todo lists the clause as backlog.

### S3.3 — intake cites the failure record with its fingerprint
- **verifies:** C-3.3
- **pins:** b885035af93f445f
- **run_cmd:** `python -m pytest tests/test_intake.py::test_intake_cites_the_failure_record_with_its_fingerprint -q`
- **Given** tests/test_intake.py
- **When** the spec `test_intake_cites_the_failure_record_with_its_fingerprint` is executed
- **Then** the new clause carries `see: <trace>@<fingerprint>` and docrefs reports it ok.

### S3.4 — intake never writes an active clause
- **verifies:** C-3.4
- **pins:** 3f1adea239230948
- **run_cmd:** `python -m pytest tests/test_intake.py::test_intake_never_writes_an_active_clause -q`
- **Given** tests/test_intake.py
- **When** the spec `test_intake_never_writes_an_active_clause` is executed
- **Then** the new clause is draft whatever the caller asked for.

### S3.5 — an intake skeleton is red until the then is written
- **verifies:** C-3.5
- **pins:** ce5267dc6a13f1c2
- **run_cmd:** `python -m pytest tests/test_intake.py::test_an_intake_skeleton_is_red_until_the_then_is_written -q`
- **Given** tests/test_intake.py
- **When** the spec `test_an_intake_skeleton_is_red_until_the_then_is_written` is executed
- **Then** the skeleton case runs red with a pending message; with a real then it can go green.

## C-4 — proved by the id allocator (lib/allocate.py)

### S4.1 — the next id is one no clause carries
- **verifies:** C-4.1
- **pins:** f6d99cc62eea45bf
- **run_cmd:** `python -m pytest tests/test_allocate.py::test_the_next_id_is_one_no_clause_carries -q`
- **Given** tests/test_allocate.py
- **When** the spec `test_the_next_id_is_one_no_clause_carries` is executed
- **Then** next_id returns an id absent from the contract, after the highest in the group.

### S4.2 — two lanes never draw from the same range
- **verifies:** C-4.2
- **pins:** cfd2fe56598493ff
- **run_cmd:** `python -m pytest tests/test_allocate.py::test_two_lanes_never_draw_from_the_same_range -q`
- **Given** tests/test_allocate.py
- **When** the spec `test_two_lanes_never_draw_from_the_same_range` is executed
- **Then** lane 0 and lane 2 allocate from disjoint ranges however many ids each takes.

### S4.3 — the lane comes from the environment or zero
- **verifies:** C-4.3
- **pins:** 74385c94234fcc5a
- **run_cmd:** `python -m pytest tests/test_allocate.py::test_the_lane_comes_from_the_environment_or_zero -q`
- **Given** tests/test_allocate.py
- **When** the spec `test_the_lane_comes_from_the_environment_or_zero` is executed
- **Then** with ATHENA_LANE set the CLI allocates in that lane; without it, in lane zero.

### S4.4 — the lane is read from the environment, as a case
- **verifies:** C-4.3
- **pins:** 74385c94234fcc5a
- **case:** `features/team-layer/cases/S4.4-lane-from-env.json`
- **Given** an environment naming lane two
- **When** lib.allocate:lane_from_env is called on it in-process
- **Then** the lane is two.

## C-5 — proved by the hook and lint modules (lib/hooks.py, lib/archlint.py)

### S5.1 — a pending edit names the clauses it touches across contracts
- **verifies:** C-5.1
- **pins:** c34e62cdfa2b9d1c
- **run_cmd:** `python -m pytest tests/test_harness.py::test_a_pending_edit_names_the_clauses_it_touches_across_contracts -q`
- **Given** tests/test_harness.py
- **When** the spec `test_a_pending_edit_names_the_clauses_it_touches_across_contracts` is executed
- **Then** the pre-edit context lists owning clauses from two maps for one file and nothing for an unowned file.

### S5.2 — an edit of a derived artifact is refused with the rebuild command
- **verifies:** C-5.2
- **pins:** 182cabf3641c03d4
- **run_cmd:** `python -m pytest tests/test_harness.py::test_an_edit_of_a_derived_artifact_is_refused_with_the_rebuild_command -q`
- **Given** tests/test_harness.py
- **When** the spec `test_an_edit_of_a_derived_artifact_is_refused_with_the_rebuild_command` is executed
- **Then** a ledger or map path yields a deny decision whose reason names the rebuilding command.

### S5.3 — the bypass allows the derived edit and says so
- **verifies:** C-5.3
- **pins:** 19fd7f37ce2d622c
- **run_cmd:** `python -m pytest tests/test_harness.py::test_the_bypass_allows_the_derived_edit_and_says_so -q`
- **Given** tests/test_harness.py
- **When** the spec `test_the_bypass_allows_the_derived_edit_and_says_so` is executed
- **Then** with the bypass set the derived edit is allowed and the context says bypassed.

### S5.4 — a pure module importing an effect module is reported
- **verifies:** C-5.4
- **pins:** 18252b3af314b21d
- **run_cmd:** `python -m pytest tests/test_harness.py::test_a_pure_module_importing_an_effect_module_is_reported -q`
- **Given** tests/test_harness.py
- **When** the spec `test_a_pure_module_importing_an_effect_module_is_reported` is executed
- **Then** a module not on the allowlist that imports subprocess is reported with the import line.

### S5.5 — this repository passes its own architecture lint
- **verifies:** C-5.5
- **pins:** 14a6bc4ddfc3618e
- **run_cmd:** `python -m pytest tests/test_harness.py::test_this_repository_passes_its_own_architecture_lint -q`
- **Given** tests/test_harness.py
- **When** the spec `test_this_repository_passes_its_own_architecture_lint` is executed
- **Then** arch lint over lib/ reports nothing.

### S5.6 — the project settings register the pre-edit hook
- **verifies:** C-5.6
- **pins:** 2c5bc4e8cc07ec03
- **run_cmd:** `python -m pytest tests/test_harness.py::test_the_project_settings_register_the_pre_edit_hook -q`
- **Given** tests/test_harness.py
- **When** the spec `test_the_project_settings_register_the_pre_edit_hook` is executed
- **Then** .claude/settings.json has a PreToolUse hook on Edit|Write|MultiEdit running hooks/pre-edit.sh.

### S5.7 — a long owner list is capped to the twelve heaviest, with a count of the rest
- **verifies:** C-5.7
- **pins:** 4187fdb2635f2889
- **run_cmd:** `python -m pytest tests/test_harness.py::test_a_long_owner_list_is_capped_to_the_heaviest_twelve -q`
- **Given** tests/test_harness.py
- **When** the spec `test_a_long_owner_list_is_capped_to_the_heaviest_twelve` is executed
- **Then** the context names exactly the twelve clauses with most owned lines and says how many more there are.

## C-6 — proved by the metrics module and a timed gate (lib/metrics.py)

### S6.1 — the gate over this repository answers within two seconds
- **verifies:** C-6.1
- **pins:** 4fe7cbf7740474f9
- **run_cmd:** `python -m pytest tests/test_budgets.py::test_the_gate_over_this_repository_answers_within_two_seconds -q`
- **Given** tests/test_budgets.py
- **When** the spec `test_the_gate_over_this_repository_answers_within_two_seconds` is executed
- **Then** `athena gate` over the repo root passes and takes under two seconds.

### S6.2 — a spec run appends one run record
- **verifies:** C-6.2
- **pins:** 1f309a343896a882
- **run_cmd:** `python -m pytest tests/test_budgets.py::test_a_spec_run_appends_one_run_record -q`
- **Given** tests/test_budgets.py
- **When** the spec `test_a_spec_run_appends_one_run_record` is executed
- **Then** after a spec run the runs file has one more line with totals and a timestamp.

### S6.3 — metrics report iterations to green and mean duration
- **verifies:** C-6.3
- **pins:** 5897149f12a40696
- **run_cmd:** `python -m pytest tests/test_budgets.py::test_metrics_report_iterations_to_green_and_mean_duration -q`
- **Given** tests/test_budgets.py
- **When** the spec `test_metrics_report_iterations_to_green_and_mean_duration` is executed
- **Then** over red, red, green, green, red, green the report says two cycles with 3 and 2 runs to green.

### S6.4 — a malformed run record is skipped and the answer still comes
- **verifies:** C-6.4
- **pins:** e6e0703cd372caad
- **run_cmd:** `python -m pytest tests/test_budgets.py::test_a_malformed_run_record_is_skipped_and_the_answer_still_comes -q`
- **Given** tests/test_budgets.py
- **When** the spec `test_a_malformed_run_record_is_skipped_and_the_answer_still_comes` is executed
- **Then** a garbage line among the records is counted as skipped and the metrics still compute.

## C-7 — proved by property-based specs (tests/test_properties.py, hypothesis)

### S7.1 — any contract survives render and parse
- **verifies:** C-7.1
- **pins:** 178710f69792107a
- **run_cmd:** `python -m pytest tests/test_properties.py::test_any_contract_survives_render_and_parse -q`
- **Given** tests/test_properties.py
- **When** the spec `test_any_contract_survives_render_and_parse` is executed
- **Then** for generated contracts, render then parse keeps ids, statuses, sources, tags and links.

### S7.2 — rewrapping never moves a clause version
- **verifies:** C-7.2
- **pins:** 65c5d54c6fdb2651
- **run_cmd:** `python -m pytest tests/test_properties.py::test_rewrapping_never_moves_a_clause_version -q`
- **Given** tests/test_properties.py
- **When** the spec `test_rewrapping_never_moves_a_clause_version` is executed
- **Then** for generated clause texts, any re-wrap yields the same version.

### S7.3 — a changed word always moves the version
- **verifies:** C-7.3
- **pins:** 141d29ce538721e9
- **run_cmd:** `python -m pytest tests/test_properties.py::test_a_changed_word_always_moves_the_version -q`
- **Given** tests/test_properties.py
- **When** the spec `test_a_changed_word_always_moves_the_version` is executed
- **Then** for generated clause texts, replacing any word changes the version.

### S7.4 — resolution terminates on any supersede graph
- **verifies:** C-7.4
- **pins:** fa6692db11d71ce5
- **run_cmd:** `python -m pytest tests/test_properties.py::test_resolution_terminates_on_any_supersede_graph -q`
- **Given** tests/test_properties.py
- **When** the spec `test_resolution_terminates_on_any_supersede_graph` is executed
- **Then** for random supersede graphs with cycles, resolve returns for every id.

### S7.5 — arbitrary text raises nothing but the parse error
- **verifies:** C-7.5
- **pins:** 514f8b52effc4095
- **run_cmd:** `python -m pytest tests/test_properties.py::test_arbitrary_text_raises_nothing_but_the_parse_error -q`
- **Given** tests/test_properties.py
- **When** the spec `test_arbitrary_text_raises_nothing_but_the_parse_error` is executed
- **Then** for arbitrary text, parse either returns or raises ContractParseError.

### S7.6 — batching keeps prefix and nodes equal to the tokens
- **verifies:** C-7.6
- **pins:** c18c276c9abec8e4
- **run_cmd:** `python -m pytest tests/test_properties.py::test_batching_keeps_prefix_and_nodes_equal_to_the_tokens -q`
- **Given** tests/test_properties.py
- **When** the spec `test_batching_keeps_prefix_and_nodes_equal_to_the_tokens` is executed
- **Then** for generated pytest commands, prefix plus nodes is the token multiset of the command.
