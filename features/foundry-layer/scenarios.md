# Scenarios: Athena Foundry Layer (v3.16)

> Executable specs for `contract.md`. One spec per clause, ids `S<group>.<index>`
> mirroring the clause number. `pins:` is written by `athena contract pin --write`.

---

## C-1 — mutation as a gate (lib/mutgate.py)

### S1.1 — the sweep is restricted to changed lines mapped to their clauses
- **verifies:** C-1.1
- **pins:** 5ea69c5aaf1fcb57
- **run_cmd:** `python -m pytest tests/test_foundry_gate.py::test_the_sweep_is_restricted_to_changed_lines_mapped_to_their_clauses -q`
- **Given** tests/test_foundry_gate.py
- **When** the spec `test_the_sweep_is_restricted_to_changed_lines_mapped_to_their_clauses` is executed
- **Then** changed lines become per-clause targets through the map, test files are not targets, a line two clauses own goes to both, and unowned changed lines are reported.

### S1.2 — a per clause mutation score is computed over owned lines with survivors listed
- **verifies:** C-1.2
- **pins:** 2dd11c271e280727
- **run_cmd:** `python -m pytest tests/test_foundry_gate.py::test_a_per_clause_mutation_score_is_computed_over_owned_lines_with_survivors_listed -q`
- **Given** tests/test_foundry_gate.py
- **When** the spec `test_a_per_clause_mutation_score_is_computed_over_owned_lines_with_survivors_listed` is executed
- **Then** score = killed / total per clause over its target lines; survivors carry path, line and kind; a clause with no mutants has no score, not zero.

### S1.3 — the offer is refused at the mutation stage on added lines only
- **verifies:** C-1.3
- **pins:** 6736d8d48324b663
- **run_cmd:** `python -m pytest tests/test_foundry_gate.py::test_the_offer_is_refused_at_the_mutation_stage_on_added_lines_only -q`
- **Given** tests/test_foundry_gate.py
- **When** the spec `test_the_offer_is_refused_at_the_mutation_stage_on_added_lines_only` is executed
- **Then** under threshold on added lines, or any survivor on an added line: refused with the clause and the first survivor; under threshold on untouched lines: advisory.

### S1.4 — a sealed run is reduced to pass or fail per test id
- **verifies:** C-1.4
- **pins:** 1351b7fe6900ffe6
- **run_cmd:** `python -m pytest tests/test_foundry_gate.py::test_a_sealed_run_is_reduced_to_pass_or_fail_per_test_id -q`
- **Given** tests/test_foundry_gate.py
- **When** the spec `test_a_sealed_run_is_reduced_to_pass_or_fail_per_test_id` is executed
- **Then** what the executor or a checkpoint sees of a sealed run is the outcome per test id and the counts; assertion messages, diffs and tracebacks are gone.

## C-2 — drafted specs admitted (lib/drafts.py)

### S2.1 — a drafted test is admitted only when red at base green at head and covering owned lines
- **verifies:** C-2.1
- **pins:** 5f3a7f43cc4c2ceb
- **run_cmd:** `python -m pytest tests/test_foundry_gate.py::test_a_drafted_test_is_admitted_only_when_red_at_base_green_at_head_and_covering_owned_lines -q`
- **Given** tests/test_foundry_gate.py
- **When** the spec `test_a_drafted_test_is_admitted_only_when_red_at_base_green_at_head_and_covering_owned_lines` is executed
- **Then** fail-before, pass-after, covers an owned line; each refusal names its reason.

### S2.2 — a clause draft is accepted only in an ears shape with one shall
- **verifies:** C-2.2
- **pins:** 3d65fc44116cdf7a
- **run_cmd:** `python -m pytest tests/test_foundry_gate.py::test_a_clause_draft_is_accepted_only_in_an_ears_shape_with_one_shall -q`
- **Given** tests/test_foundry_gate.py
- **When** the spec `test_a_clause_draft_is_accepted_only_in_an_ears_shape_with_one_shall` is executed
- **Then** the six EARS shapes are recognised; zero or two SHALLs, no shape, or nothing after SHALL are named defects.

### S2.3 — acceptance is kept per drafting model and rendered as a rate
- **verifies:** C-2.3
- **pins:** 01c6aa72a7778ae4
- **run_cmd:** `python -m pytest tests/test_foundry_gate.py::test_acceptance_is_kept_per_drafting_model_and_rendered_as_a_rate -q`
- **Given** tests/test_foundry_gate.py
- **When** the spec `test_acceptance_is_kept_per_drafting_model_and_rendered_as_a_rate` is executed
- **Then** drafted, admitted, accepted-without-edit per model; rates over drafted; the render names the model and both rates.

## C-3 — the daemon (lib/daemon.py, athena.py)

### S3.1 — a tick takes the highest priority ready task no lane runs and names its worktree
- **verifies:** C-3.1
- **pins:** 68339763225028f6
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_a_tick_takes_the_highest_priority_ready_task_no_lane_runs_and_names_its_worktree -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_a_tick_takes_the_highest_priority_ready_task_no_lane_runs_and_names_its_worktree` is executed
- **Then** priority first, then age, never a task already running, never another slug; the worktree name carries task id and packet digest, stable across restarts.

### S3.2 — a stale heartbeat releases the claim and counts a crashed attempt
- **verifies:** C-3.2
- **pins:** b60086a09e0b5b7f
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_a_stale_heartbeat_releases_the_claim_and_counts_a_crashed_attempt -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_a_stale_heartbeat_releases_the_claim_and_counts_a_crashed_attempt` is executed
- **Then** claims older than the lease are stale; the release plan names the pid to kill and the attempt counter to bump; fresh claims are left alone.

### S3.3 — on restart a green worktree is offered not run again
- **verifies:** C-3.3
- **pins:** 574e600307965e84
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_on_restart_a_green_worktree_is_offered_not_run_again -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_on_restart_a_green_worktree_is_offered_not_run_again` is executed
- **Then** a worktree whose last record for its task is green goes to the refinery; a red or unrecorded one is run; the record is matched on task and workspace.

### S3.4 — every daemon action is one ledger line and actions per task are capped
- **verifies:** C-3.4
- **pins:** 8fde19305d688c0a
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_every_daemon_action_is_one_ledger_line_and_actions_per_task_are_capped -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_every_daemon_action_is_one_ledger_line_and_actions_per_task_are_capped` is executed
- **Then** the line carries tick, task, action, reason and time; the cap counts this task's actions in the last hour and refuses the next one past it.

### S3.5 — the daemon command prints its tick without running when dry
- **verifies:** C-3.5
- **pins:** 0a7de9d4ad70e6bd
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_the_daemon_command_prints_its_tick_without_running_when_dry -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_the_daemon_command_prints_its_tick_without_running_when_dry` is executed
- **Then** `athena daemon --dry-run --ready-json <file>` reports the pick and the lane decision as text and exits 0, or says nothing is ready and exits 1; nothing is dispatched.

## C-4 — lanes admit by capacity (lib/lanes.py)

### S4.1 — vllm metrics and llama cpp slots parse into one lane state
- **verifies:** C-4.1
- **pins:** bfeed2c06ae2fe27
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_vllm_metrics_and_llama_cpp_slots_parse_into_one_lane_state -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_vllm_metrics_and_llama_cpp_slots_parse_into_one_lane_state` is executed
- **Then** running, waiting, kv_usage, prefix_hit_rate out of Prometheus text; slots give running and zero waiting with the rest unknown; garbage gives an empty state.

### S4.2 — a lane admits only with nothing waiting kv under the ceiling and headroom
- **verifies:** C-4.2
- **pins:** 09d739611eb8ab07
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_a_lane_admits_only_with_nothing_waiting_kv_under_the_ceiling_and_headroom -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_a_lane_admits_only_with_nothing_waiting_kv_under_the_ceiling_and_headroom` is executed
- **Then** the three conditions, each refusal named; an unknown kv_usage does not block.

### S4.3 — a shared packet prefix is routed to the lane that last served it while warm
- **verifies:** C-4.3
- **pins:** 2f4891dbf220e936
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_a_shared_packet_prefix_is_routed_to_the_lane_that_last_served_it_while_warm -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_a_shared_packet_prefix_is_routed_to_the_lane_that_last_served_it_while_warm` is executed
- **Then** the key is the packet's static prefix; the warm lane wins within the window, the first lane otherwise; serving a prefix refreshes its warmth.

### S4.4 — two server errors in a row cool a lane down for a period
- **verifies:** C-4.4
- **pins:** 9913cb08cc8ac238
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_two_server_errors_in_a_row_cool_a_lane_down_for_a_period -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_two_server_errors_in_a_row_cool_a_lane_down_for_a_period` is executed
- **Then** two consecutive 5xx start the cooldown; a 200 in between resets it; the lane is routable again when the period ends.

### S4.5 — a speculation flag is admitted only when verdicts and temperature zero outputs agree
- **verifies:** C-4.5
- **pins:** cc3fb42e64e67b4d
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_a_speculation_flag_is_admitted_only_when_verdicts_and_temperature_zero_outputs_agree -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_a_speculation_flag_is_admitted_only_when_verdicts_and_temperature_zero_outputs_agree` is executed
- **Then** paired runs with equal verdicts and identical greedy outputs admit the flag; a verdict that differs or a token that diverges refuses it naming the task and the position of the first divergence.

## C-5 — the ladder (lib/ladder.py)

### S5.1 — pre dispatch features are logged per task
- **verifies:** C-5.1
- **pins:** bf512fb778ad5c25
- **run_cmd:** `python -m pytest tests/test_foundry_ladder.py::test_pre_dispatch_features_are_logged_per_task -q`
- **Given** tests/test_foundry_ladder.py
- **When** the spec `test_pre_dispatch_features_are_logged_per_task` is executed
- **Then** packet tokens, files owned, clause count, spec count, lines owned, prior attempts; lines owned counts only the task's files in the map.

### S5.2 — a rung escalates on two reds or a fail fast signal with a handoff
- **verifies:** C-5.2
- **pins:** 588ab4fbaab004fd
- **run_cmd:** `python -m pytest tests/test_foundry_ladder.py::test_a_rung_escalates_on_two_reds_or_a_fail_fast_signal_with_a_handoff -q`
- **Given** tests/test_foundry_ladder.py
- **When** the spec `test_a_rung_escalates_on_two_reds_or_a_fail_fast_signal_with_a_handoff` is executed
- **Then** two red attempts on the rung escalate; so does one attempt with a fail-fast signal; one plain red does not; the handoff is files, last test output and notes, capped.

### S5.3 — the rung table reports win rate and gpu minutes and disables a losing rung
- **verifies:** C-5.3
- **pins:** 97f206d055d1663d
- **run_cmd:** `python -m pytest tests/test_foundry_ladder.py::test_the_rung_table_reports_win_rate_and_gpu_minutes_and_disables_a_losing_rung -q`
- **Given** tests/test_foundry_ladder.py
- **When** the spec `test_the_rung_table_reports_win_rate_and_gpu_minutes_and_disables_a_losing_rung` is executed
- **Then** per (rung, class): attempts, greens, win rate, GPU minutes per green; a rung under the floor for a class is disabled for that class only.

## C-6 — provenance (lib/provenance.py)

### S6.1 — a verdict carries the provenance of what produced it
- **verifies:** C-6.1
- **pins:** a28e0ecef93db1b5
- **run_cmd:** `python -m pytest tests/test_foundry_ladder.py::test_a_verdict_carries_the_provenance_of_what_produced_it -q`
- **Given** tests/test_foundry_ladder.py
- **When** the spec `test_a_verdict_carries_the_provenance_of_what_produced_it` is executed
- **Then** model identity, runtime, sampling and seed, packet digest, tool set digest and relay version, in one block the record carries.

### S6.2 — a merged verdict becomes an in toto statement with a slsa shaped predicate
- **verifies:** C-6.2
- **pins:** 9dfd59ae42d0c66a
- **run_cmd:** `python -m pytest tests/test_foundry_ladder.py::test_a_merged_verdict_becomes_an_in_toto_statement_with_a_slsa_shaped_predicate -q`
- **Given** tests/test_foundry_ladder.py
- **When** the spec `test_a_merged_verdict_becomes_an_in_toto_statement_with_a_slsa_shaped_predicate` is executed
- **Then** Statement v1 with the merged tree as subject and predicate athena/verdict/v1 whose buildDefinition and runDetails carry the record's provenance and outcome.

### S6.3 — a record missing provenance names the missing fields
- **verifies:** C-6.3
- **pins:** e0a682cc89e6cb26
- **run_cmd:** `python -m pytest tests/test_foundry_ladder.py::test_a_record_missing_provenance_names_the_missing_fields -q`
- **Given** tests/test_foundry_ladder.py
- **When** the spec `test_a_record_missing_provenance_names_the_missing_fields` is executed
- **Then** every missing field named, dotted, in a stable order; a complete record misses nothing; a record without the block misses all of them.

## C-7 — memory in the packet (lib/memory.py)

### S7.1 — a repo map seeded from the tasks files fits the budget after the prefix
- **verifies:** C-7.1
- **pins:** 85606d18ec2b6566
- **run_cmd:** `python -m pytest tests/test_foundry_memory.py::test_a_repo_map_seeded_from_the_tasks_files_fits_the_budget_after_the_prefix -q`
- **Given** tests/test_foundry_memory.py
- **When** the spec `test_a_repo_map_seeded_from_the_tasks_files_fits_the_budget_after_the_prefix` is executed
- **Then** seed files come first with all their signatures, then the rest until the budget; the map is placed after the static prefix, never before it.

### S7.2 — a red verdict becomes a lesson with a failure class and a rule never the diff
- **verifies:** C-7.2
- **pins:** 33de837c5cd8fd04
- **run_cmd:** `python -m pytest tests/test_foundry_memory.py::test_a_red_verdict_becomes_a_lesson_with_a_failure_class_and_a_rule_never_the_diff -q`
- **Given** tests/test_foundry_memory.py
- **When** the spec `test_a_red_verdict_becomes_a_lesson_with_a_failure_class_and_a_rule_never_the_diff` is executed
- **Then** clause id, file, failure class from the tail, a one-line rule, the verdict id; a green verdict yields none; no diff text travels.

### S7.3 — lessons are selected by exact clause and file capped and retired after ten green rides
- **verifies:** C-7.3
- **pins:** dd94e364562acb6e
- **run_cmd:** `python -m pytest tests/test_foundry_memory.py::test_lessons_are_selected_by_exact_clause_and_file_capped_and_retired_after_ten_green_rides -q`
- **Given** tests/test_foundry_memory.py
- **When** the spec `test_lessons_are_selected_by_exact_clause_and_file_capped_and_retired_after_ten_green_rides` is executed
- **Then** exact clause id or file match, at most n, each rule capped; a lesson that rode in ten green packets is retired.

## C-8 — regeneration (lib/regen.py)

### S8.1 — a regeneration packet carries clauses specs and signatures never the old body
- **verifies:** C-8.1
- **pins:** 89bb0c3254d36537
- **run_cmd:** `python -m pytest tests/test_foundry_memory.py::test_a_regeneration_packet_carries_clauses_specs_and_signatures_never_the_old_body -q`
- **Given** tests/test_foundry_memory.py
- **When** the spec `test_a_regeneration_packet_carries_clauses_specs_and_signatures_never_the_old_body` is executed
- **Then** the packet names the module, its clauses, its specs and the public signatures; no line of the old body appears in it.

### S8.2 — the behaviour diff runs per public typed function and records counterexamples
- **verifies:** C-8.2
- **pins:** c1100bd806b3ee7e
- **run_cmd:** `python -m pytest tests/test_foundry_memory.py::test_the_behaviour_diff_runs_per_public_typed_function_and_records_counterexamples -q`
- **Given** tests/test_foundry_memory.py
- **When** the spec `test_the_behaviour_diff_runs_per_public_typed_function_and_records_counterexamples` is executed
- **Then** one diffbehavior run per typed public function through the injected runner; counterexamples parsed out of its output; untyped or private functions are skipped.

### S8.3 — equivalence needs green specs no counterexample and mutation score not under the original
- **verifies:** C-8.3
- **pins:** 0ea728a71891ae5e
- **run_cmd:** `python -m pytest tests/test_foundry_memory.py::test_equivalence_needs_green_specs_no_counterexample_and_mutation_score_not_under_the_original -q`
- **Given** tests/test_foundry_memory.py
- **When** the spec `test_equivalence_needs_green_specs_no_counterexample_and_mutation_score_not_under_the_original` is executed
- **Then** three conditions; the first failing one is the reason; per clause the new score must not be under the old.

## C-9 — oracles of the second kind (lib/oracles.py)

### S8.4 — a task is judged by its own checks and regressions from a red base
- **verifies:** C-8.4
- **pins:** 9fb28d5e900d879b
- **run_cmd:** `python -m pytest tests/test_foundry_gate.py::test_a_task_is_judged_by_its_own_checks_and_regressions_from_a_red_base -q`
- **Given** tests/test_foundry_gate.py
- **When** the spec `test_a_task_is_judged_by_its_own_checks_and_regressions_from_a_red_base` is executed
- **Then** with a base that already fails a check outside the task, a verdict whose own checks are green and whose only reds are inherited is green and names them; a new red outside the base is a regression and red; an iteration that touched a spec file is restored to the best before it even when the green counts tie.

### S9.1 — an import clause renders an import linter contract and its run command
- **verifies:** C-9.1
- **pins:** 3941f21eba622b24
- **run_cmd:** `python -m pytest tests/test_foundry_oracles.py::test_an_import_clause_renders_an_import_linter_contract_and_its_run_command -q`
- **Given** tests/test_foundry_oracles.py
- **When** the spec `test_an_import_clause_renders_an_import_linter_contract_and_its_run_command` is executed
- **Then** "shall not import" becomes a forbidden contract, "layers" a layers contract, one .importlinter with both, and the command that checks it.

### S9.2 — a time budget clause renders a benchmark command against a stored baseline
- **verifies:** C-9.2
- **pins:** efdb9a58164eb65a
- **run_cmd:** `python -m pytest tests/test_foundry_oracles.py::test_a_time_budget_clause_renders_a_benchmark_command_against_a_stored_baseline -q`
- **Given** tests/test_foundry_oracles.py
- **When** the spec `test_a_time_budget_clause_renders_a_benchmark_command_against_a_stored_baseline` is executed
- **Then** "within N% of its baseline" becomes a compare-fail benchmark command on the clause's mark; a clause without a budget renders nothing.

### S9.3 — a command that would update a snapshot baseline is refused
- **verifies:** C-9.3
- **pins:** 6822032c421738ca
- **run_cmd:** `python -m pytest tests/test_foundry_oracles.py::test_a_command_that_would_update_a_snapshot_baseline_is_refused -q`
- **Given** tests/test_foundry_oracles.py
- **When** the spec `test_a_command_that_would_update_a_snapshot_baseline_is_refused` is executed
- **Then** the snapshot-update flags of the golden tools are refused with the reason; a plain test command passes.

### S9.4 — the frame's own structure holds under import-linter
- **verifies:** C-9.4
- **pins:** f51ccfbb67c843bb
- **run_cmd:** `lint-imports --config features/foundry-layer/importlinter.ini`
- **Given** features/foundry-layer/importlinter.ini, rendered from the clause by lib.oracles.importlinter_config
- **When** `lint-imports` runs the contracts in it
- **Then** every contract is kept: no module under lib imports athena or tests; a broken contract exits non-zero and the clause is red.
## C-10 — the sandbox (lib/sandbox.py)

### S9.5 — packing a packet with memory stays within its time and memory budget
- **verifies:** C-9.5
- **pins:** ced7945f04959115
- **run_cmd:** `python -m pytest tests/test_foundry_perf.py::test_packing_a_packet_with_memory_stays_within_its_time_and_memory_budget -q`
- **Given** tests/test_foundry_perf.py
- **When** the spec `test_packing_a_packet_with_memory_stays_within_its_time_and_memory_budget` is executed
- **Then** a 30k-character packet with a repository map and five lessons packs in under 5 ms mean over the benchmark rounds and under 2 MB peak allocation; a quadratic packing fails the spec.

### S10.1 — the sandbox wraps a command with the worktree writable and the lane ports open
- **verifies:** C-10.1
- **pins:** 0488ff516d9c047b
- **run_cmd:** `python -m pytest tests/test_foundry_oracles.py::test_the_sandbox_wraps_a_command_with_the_worktree_writable_and_the_lane_ports_open -q`
- **Given** tests/test_foundry_oracles.py
- **When** the spec `test_the_sandbox_wraps_a_command_with_the_worktree_writable_and_the_lane_ports_open` is executed
- **Then** the config allows writes in the worktree only, reads on the toolchain, no network but the loopback lane ports; the argv runs the command through the runtime.

### S10.2 — without a sandbox the frame says so and runs unsandboxed only when allowed
- **verifies:** C-10.2
- **pins:** 8af976973091de16
- **run_cmd:** `python -m pytest tests/test_foundry_oracles.py::test_without_a_sandbox_the_frame_says_so_and_runs_unsandboxed_only_when_allowed -q`
- **Given** tests/test_foundry_oracles.py
- **When** the spec `test_without_a_sandbox_the_frame_says_so_and_runs_unsandboxed_only_when_allowed` is executed
- **Then** flag required + unavailable: refuse; flag on + unavailable: run unsandboxed and say so; flag off: run plain; available: sandboxed.

### S10.3 — the relay fences tool calls outside the worktree or on the deny list
- **verifies:** C-10.3
- **pins:** b82fa0cb6be54fb2
- **run_cmd:** `python -m pytest tests/test_foundry_oracles.py::test_the_relay_fences_tool_calls_outside_the_worktree_or_on_the_deny_list -q`
- **Given** tests/test_foundry_oracles.py
- **When** the spec `test_the_relay_fences_tool_calls_outside_the_worktree_or_on_the_deny_list` is executed
- **Then** a write or edit outside the worktree, a read of a denied path and a deny-listed command are refused with the reason; a call inside the worktree passes; a completion whose calls are all refused comes back as a text refusal with no tool_calls.

## C-11 — wired into the loop (lib/provenance.py, lib/refinery.py, lib/memory.py, lib/ladder.py, lib/lanes.py, athena.py)

### S11.1 — a dispatch record carries provenance built from the executor and the packet
- **verifies:** C-11.1
- **pins:** 80f202ff2fbdf42d
- **run_cmd:** `python -m pytest tests/test_foundry_wiring.py::test_a_dispatch_record_carries_provenance_built_from_the_executor_and_the_packet -q`
- **Given** tests/test_foundry_wiring.py
- **When** the spec `test_a_dispatch_record_carries_provenance_built_from_the_executor_and_the_packet` is executed
- **Then** the block names the executor's model, the thinking level, the packet and tool digests and the frame's version; a record made with it carries it; unknown fields are named missing.

### S11.2 — the merge queue has a mutation stage between check and fast forward
- **verifies:** C-11.2
- **pins:** 840a8c370cd3bc55
- **run_cmd:** `python -m pytest tests/test_foundry_wiring.py::test_the_merge_queue_has_a_mutation_stage_between_check_and_fast_forward -q`
- **Given** tests/test_foundry_wiring.py
- **When** the spec `test_the_merge_queue_has_a_mutation_stage_between_check_and_fast_forward` is executed
- **Then** the stages name mutation after check; changed lines come out of a unified diff; the stage refuses on a survivor on an added line naming the clause.

### S11.3 — the packet carries the repo map and the lessons after the prefix
- **verifies:** C-11.3
- **pins:** 5a117e3c4a54258e
- **run_cmd:** `python -m pytest tests/test_foundry_wiring.py::test_the_packet_carries_the_repo_map_and_the_lessons_after_the_prefix -q`
- **Given** tests/test_foundry_wiring.py
- **When** the spec `test_the_packet_carries_the_repo_map_and_the_lessons_after_the_prefix` is executed
- **Then** the map and the lessons sit between the static prefix and the requirement; the counts are reported; nothing to add leaves the packet as it was.

### S11.4 — the daemon climbs the ladder on the escalation rule and stops at its top
- **verifies:** C-11.4
- **pins:** 926d2a74f8abd620
- **run_cmd:** `python -m pytest tests/test_foundry_wiring.py::test_the_daemon_climbs_the_ladder_on_the_escalation_rule_and_stops_at_its_top -q`
- **Given** tests/test_foundry_wiring.py
- **When** the spec `test_the_daemon_climbs_the_ladder_on_the_escalation_rule_and_stops_at_its_top` is executed
- **Then** the next rung after the current one, none at the top, disabled rungs skipped.

### S11.5 — lane endpoints are derived from the executor and the admission reads them
- **verifies:** C-11.5
- **pins:** 80810640d6a18bda
- **run_cmd:** `python -m pytest tests/test_foundry_wiring.py::test_lane_endpoints_are_derived_from_the_executor_and_the_admission_reads_them -q`
- **Given** tests/test_foundry_wiring.py
- **When** the spec `test_lane_endpoints_are_derived_from_the_executor_and_the_admission_reads_them` is executed
- **Then** a pi executor's lane has a metrics or slots endpoint beside its base url; the live state is read through an injected fetcher and is empty when the read fails.

### S11.6 — an iteration that lost green checks is rolled back to the better one
- **verifies:** C-11.6
- **pins:** ed3172f4c3630679
- **run_cmd:** `python -m pytest tests/test_foundry_wiring.py::test_an_iteration_that_lost_green_checks_is_rolled_back_to_the_better_one -q`
- **Given** tests/test_foundry_wiring.py
- **When** the spec `test_an_iteration_that_lost_green_checks_is_rolled_back_to_the_better_one` is executed
- **Then** the green count per iteration is read from its checks; a drop names the better iteration to restore and the regression is recorded; equal or better counts restore nothing; the first iteration never rolls back.

### S11.7 — the daemon with a pool routes by prefix affinity among admitted lanes
- **verifies:** C-11.7
- **pins:** 94301eac5ccdee9c
- **run_cmd:** `python -m pytest tests/test_foundry_daemon.py::test_the_daemon_with_a_pool_routes_by_prefix_affinity_among_admitted_lanes -q`
- **Given** tests/test_foundry_daemon.py
- **When** the spec `test_the_daemon_with_a_pool_routes_by_prefix_affinity_among_admitted_lanes` is executed
- **Then** with `--executors a,b` the dry run names the lane the pool would take; the pure choice takes the warm lane first, then the others in order, only among those admitted; serving a prefix warms that lane.

