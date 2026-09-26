# Plan: Athena Foundry Layer

## Overview
Ten gaps between lanes that land clauses and a factory that runs itself, each closed as a
clause group with a red spec before the code exists. Pure functions per gap in their own
module under `lib/`; injected runners for git, crosshair and the lanes; the CLI wires the
loop (`athena daemon`) last. OSS picks from the 2026-09-25 digest are wrapped, not rewritten:
cosmic-ray, beads, import-linter, pytest-benchmark, syrupy, in-toto attestation, aider's
repomap, CrossHair, sandbox-runtime.

## Out of Scope
- Running cosmic-ray, crosshair or sandbox-runtime inside the specs: every spec takes an
  injected runner or parses recorded output.
- A learned router: features are logged first (C-5.1); a model comes after a hundred verdicts.
- Signing merged statements with a key: the statement shape first, DSSE later.

## Phase 1: Mutation is a gate; drafts are admitted
**Goal:** the refinery can refuse at a mutation stage on changed lines, and a model-drafted
test or clause is admitted by rule.
**Depends on:** none
### Tasks
- [ ] T1.1 Changed lines to per-clause mutation targets and scores
  - success_check: `python -m pytest tests/test_foundry_gate.py::test_the_sweep_is_restricted_to_changed_lines_mapped_to_their_clauses tests/test_foundry_gate.py::test_a_per_clause_mutation_score_is_computed_over_owned_lines_with_survivors_listed -q`
  - files: `lib/mutgate.py`
  - verifies: S1.1, S1.2
- [ ] T1.2 The mutation stage verdict and the sealed-run summary
  - success_check: `python -m pytest tests/test_foundry_gate.py::test_the_offer_is_refused_at_the_mutation_stage_on_added_lines_only tests/test_foundry_gate.py::test_a_sealed_run_is_reduced_to_pass_or_fail_per_test_id -q`
  - files: `lib/mutgate.py`
  - verifies: S1.3, S1.4
- [ ] T1.3 Draft admission and the EARS validator
  - success_check: `python -m pytest tests/test_foundry_gate.py::test_a_drafted_test_is_admitted_only_when_red_at_base_green_at_head_and_covering_owned_lines tests/test_foundry_gate.py::test_a_clause_draft_is_accepted_only_in_an_ears_shape_with_one_shall -q`
  - files: `lib/drafts.py`
  - verifies: S2.1, S2.2
- [ ] T1.4 Acceptance per drafting model
  - success_check: `python -m pytest tests/test_foundry_gate.py::test_acceptance_is_kept_per_drafting_model_and_rendered_as_a_rate -q`
  - files: `lib/drafts.py`
  - verifies: S2.3

## Phase 2: The daemon and the lanes
**Goal:** the tick, the lease, the resume and the ledger are pure and proven; lanes are
admitted by their own metrics; the loop is a command.
**Depends on:** Phase 1
### Tasks
- [ ] T2.1 The tick: next task, worktree name, stale claims
  - success_check: `python -m pytest tests/test_foundry_daemon.py::test_a_tick_takes_the_highest_priority_ready_task_no_lane_runs_and_names_its_worktree tests/test_foundry_daemon.py::test_a_stale_heartbeat_releases_the_claim_and_counts_a_crashed_attempt -q`
  - files: `lib/daemon.py`
  - verifies: S3.1, S3.2
- [ ] T2.2 Resume on restart and the capped ledger
  - success_check: `python -m pytest tests/test_foundry_daemon.py::test_on_restart_a_green_worktree_is_offered_not_run_again tests/test_foundry_daemon.py::test_every_daemon_action_is_one_ledger_line_and_actions_per_task_are_capped -q`
  - files: `lib/daemon.py`
  - verifies: S3.3, S3.4
- [ ] T2.3 Lane state from metrics and slots; admission by capacity
  - success_check: `python -m pytest tests/test_foundry_daemon.py::test_vllm_metrics_and_llama_cpp_slots_parse_into_one_lane_state tests/test_foundry_daemon.py::test_a_lane_admits_only_with_nothing_waiting_kv_under_the_ceiling_and_headroom -q`
  - files: `lib/lanes.py`
  - verifies: S4.1, S4.2
- [ ] T2.4 Prefix affinity and cooldown
  - success_check: `python -m pytest tests/test_foundry_daemon.py::test_a_shared_packet_prefix_is_routed_to_the_lane_that_last_served_it_while_warm tests/test_foundry_daemon.py::test_two_server_errors_in_a_row_cool_a_lane_down_for_a_period -q`
  - files: `lib/lanes.py`
  - verifies: S4.3, S4.4
- [ ] T2.6 The speculation oracle: paired verdicts and greedy outputs
  - success_check: `python -m pytest tests/test_foundry_daemon.py::test_a_speculation_flag_is_admitted_only_when_verdicts_and_temperature_zero_outputs_agree -q`
  - files: `lib/lanes.py`
  - verifies: S4.5
- [ ] T2.5 `athena daemon`: the loop as a command, dry by flag
  - success_check: `python -m pytest tests/test_foundry_daemon.py::test_the_daemon_command_prints_its_tick_without_running_when_dry -q`
  - files: `athena.py, lib/daemon.py`
  - verifies: S3.5

## Phase 3: The ladder and provenance
**Goal:** escalation is a rule with logged features and a handoff; a verdict names what
produced it and can become a statement.
**Depends on:** Phase 2
### Tasks
- [ ] T3.1 Features and the escalation rule with its handoff
  - success_check: `python -m pytest tests/test_foundry_ladder.py::test_pre_dispatch_features_are_logged_per_task tests/test_foundry_ladder.py::test_a_rung_escalates_on_two_reds_or_a_fail_fast_signal_with_a_handoff -q`
  - files: `lib/ladder.py`
  - verifies: S5.1, S5.2
- [ ] T3.2 The rung table and disabled rungs
  - success_check: `python -m pytest tests/test_foundry_ladder.py::test_the_rung_table_reports_win_rate_and_gpu_minutes_and_disables_a_losing_rung -q`
  - files: `lib/ladder.py`
  - verifies: S5.3
- [ ] T3.3 Provenance block, in-toto statement, missing fields
  - success_check: `python -m pytest tests/test_foundry_ladder.py::test_a_verdict_carries_the_provenance_of_what_produced_it tests/test_foundry_ladder.py::test_a_merged_verdict_becomes_an_in_toto_statement_with_a_slsa_shaped_predicate tests/test_foundry_ladder.py::test_a_record_missing_provenance_names_the_missing_fields -q`
  - files: `lib/provenance.py`
  - verifies: S6.1, S6.2, S6.3

## Phase 4: Memory and regeneration
**Goal:** the packet carries a capped map and lessons; a module can be regenerated from its
spec and judged equivalent.
**Depends on:** Phase 3
### Tasks
- [ ] T4.1 The repo map in the packet
  - success_check: `python -m pytest tests/test_foundry_memory.py::test_a_repo_map_seeded_from_the_tasks_files_fits_the_budget_after_the_prefix -q`
  - files: `lib/memory.py`
  - verifies: S7.1
- [ ] T4.2 Lessons: from a red verdict, selected, decayed
  - success_check: `python -m pytest tests/test_foundry_memory.py::test_a_red_verdict_becomes_a_lesson_with_a_failure_class_and_a_rule_never_the_diff tests/test_foundry_memory.py::test_lessons_are_selected_by_exact_clause_and_file_capped_and_retired_after_ten_green_rides -q`
  - files: `lib/memory.py`
  - verifies: S7.2, S7.3
- [ ] T4.3 Regeneration: the packet, the behaviour diff, the equivalence verdict
  - success_check: `python -m pytest tests/test_foundry_memory.py::test_a_regeneration_packet_carries_clauses_specs_and_signatures_never_the_old_body tests/test_foundry_memory.py::test_the_behaviour_diff_runs_per_public_typed_function_and_records_counterexamples tests/test_foundry_memory.py::test_equivalence_needs_green_specs_no_counterexample_and_mutation_score_not_under_the_original -q`
  - files: `lib/regen.py`
  - verifies: S8.1, S8.2, S8.3

## Phase 5: Oracles and the sandbox
**Goal:** structure, time budgets and golden files are clauses with run commands; the
executor's commands can run fenced.
**Depends on:** Phase 4
### Tasks
- [ ] T5.1 Import-linter and benchmark commands from clauses; refused baseline updates
  - success_check: `python -m pytest tests/test_foundry_oracles.py::test_an_import_clause_renders_an_import_linter_contract_and_its_run_command tests/test_foundry_oracles.py::test_a_time_budget_clause_renders_a_benchmark_command_against_a_stored_baseline tests/test_foundry_oracles.py::test_a_command_that_would_update_a_snapshot_baseline_is_refused -q`
  - files: `lib/oracles.py`
  - verifies: S9.1, S9.2, S9.3
- [ ] T5.2 The sandbox config, argv and decision
  - success_check: `python -m pytest tests/test_foundry_oracles.py::test_the_sandbox_wraps_a_command_with_the_worktree_writable_and_the_lane_ports_open tests/test_foundry_oracles.py::test_without_a_sandbox_the_frame_says_so_and_runs_unsandboxed_only_when_allowed -q`
  - files: `lib/sandbox.py`
  - verifies: S10.1, S10.2
- [ ] T5.3 The relay fence: paths and commands the executor may not touch
  - success_check: `python -m pytest tests/test_foundry_oracles.py::test_the_relay_fences_tool_calls_outside_the_worktree_or_on_the_deny_list -q`
  - files: `lib/sandbox.py, athena.py`
  - verifies: S10.3

## Phase 6: Wired into the loop
**Goal:** provenance in every record, the mutation stage in the queue, memory in the packet, the ladder and live admission in the daemon.
**Depends on:** Phase 5
### Tasks
- [ ] T6.1 Provenance for a dispatch and the record that carries it
  - success_check: `python -m pytest tests/test_foundry_wiring.py::test_a_dispatch_record_carries_provenance_built_from_the_executor_and_the_packet -q`
  - files: `lib/provenance.py, lib/dispatch.py`
  - verifies: S11.1
- [ ] T6.2 The mutation stage of the merge queue: stages, changed lines, verdict
  - success_check: `python -m pytest tests/test_foundry_wiring.py::test_the_merge_queue_has_a_mutation_stage_between_check_and_fast_forward -q`
  - files: `lib/refinery.py`
  - verifies: S11.2
- [ ] T6.3 Memory in the packet
  - success_check: `python -m pytest tests/test_foundry_wiring.py::test_the_packet_carries_the_repo_map_and_the_lessons_after_the_prefix -q`
  - files: `lib/memory.py`
  - verifies: S11.3
- [ ] T6.4 The next rung and the live lane state
  - success_check: `python -m pytest tests/test_foundry_wiring.py::test_the_daemon_climbs_the_ladder_on_the_escalation_rule_and_stops_at_its_top tests/test_foundry_wiring.py::test_lane_endpoints_are_derived_from_the_executor_and_the_admission_reads_them -q`
  - files: `lib/ladder.py, lib/lanes.py`
  - verifies: S11.4, S11.5
- [ ] T6.5 Iterations never regress: the better iteration is restored
  - success_check: `python -m pytest tests/test_foundry_wiring.py::test_an_iteration_that_lost_green_checks_is_rolled_back_to_the_better_one -q`
  - files: `lib/dispatch.py`
  - verifies: S11.6
- [ ] T6.6 The daemon's pool: prefix affinity among admitted lanes
  - success_check: `python -m pytest tests/test_foundry_daemon.py::test_the_daemon_with_a_pool_routes_by_prefix_affinity_among_admitted_lanes -q`
  - files: `lib/lanes.py, athena.py`
  - verifies: S11.7
- [ ] T6.7 A time and memory budget as a spec
  - success_check: `python -m pytest tests/test_foundry_perf.py::test_packing_a_packet_with_memory_stays_within_its_time_and_memory_budget -q`
  - files: `lib/memory.py, tests/test_foundry_perf.py`
  - verifies: S9.5
### Manual Verification
- `python athena.py daemon features/foundry-layer/contract.md --front features/foundry-layer/plan.md --dry-run --text` names the next task and the lane it would take.
