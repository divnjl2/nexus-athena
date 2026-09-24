# Scenarios: Athena Executor Layer (v3.12)

> Executable specs for `contract.md`. One spec per clause, ids `S<group>.<index>`
> mirroring the clause number. `pins:` is written by `athena contract pin --write`.

---

## C-1 — proved by the dispatch module (lib/dispatch.py)

### S1.1 — a packet is derived from contract, scenarios and plan
- **verifies:** C-1.1
- **pins:** 2371c7363375554f
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_packet_is_derived_from_contract_scenarios_and_plan -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_packet_is_derived_from_contract_scenarios_and_plan` is executed
- **Then** the packet for a task holds the clauses its specs verify, their run commands and the task's files.

### S1.2 — a rendered packet states the done criterion and disowns the report
- **verifies:** C-1.2
- **pins:** 983aca12dc4dcc7d
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_rendered_packet_states_the_done_criterion_and_disowns_the_report -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_rendered_packet_states_the_done_criterion_and_disowns_the_report` is executed
- **Then** the rendered text names every spec command as the criterion and says the executor's own report does not count.

### S1.3 — a task naming an unknown spec gets no packet
- **verifies:** C-1.3
- **pins:** ac46677decdb2cbc
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_task_naming_an_unknown_spec_gets_no_packet -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_task_naming_an_unknown_spec_gets_no_packet` is executed
- **Then** building a packet for a task whose verifies names a missing spec raises a dispatch error.

### S1.4 — an oversized packet is reported, not trimmed
- **verifies:** C-1.4
- **pins:** 835b981461bd23ce
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_an_oversized_packet_is_reported_not_trimmed -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_an_oversized_packet_is_reported_not_trimmed` is executed
- **Then** a packet over the budget carries over_budget with the estimate, and its clauses are intact.

### S1.5 — a spec's own test source travels in the packet
- **verifies:** C-1.5
- **pins:** 6a01fd5af2fc5805
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_specs_own_test_source_travels_in_the_packet -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_specs_own_test_source_travels_in_the_packet` is executed
- **Then** the test function named by a spec's run_cmd is extracted from its module and rendered in the packet under the spec's id.

## C-2 — proved by the dispatch module (lib/dispatch.py)

### S2.1 — the verdict ignores the executor's report
- **verifies:** C-2.1
- **pins:** c855249d81fc3ccb
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_the_verdict_ignores_the_executors_report -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_the_verdict_ignores_the_executors_report` is executed
- **Then** with a claim of success but no diff the verdict is not landed; with a diff and green specs it passes whatever the claim said.

### S2.2 — no change means not landed
- **verifies:** C-2.2
- **pins:** cb9eddee2ee0afa8
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_no_change_means_not_landed -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_no_change_means_not_landed` is executed
- **Then** identical snapshots yield landed=False and passed=False.

### S2.3 — a red spec command makes the attempt red with its tail
- **verifies:** C-2.3
- **pins:** 0810505d0b526139
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_red_spec_command_makes_the_attempt_red_with_its_tail -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_red_spec_command_makes_the_attempt_red_with_its_tail` is executed
- **Then** a failing check yields green=False and the reason carries that command's tail.

### S2.4 — touching a derived or hand-written file flags review
- **verifies:** C-2.4
- **pins:** 91d2c21a232178cb
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_touching_a_derived_or_hand_written_file_flags_review -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_touching_a_derived_or_hand_written_file_flags_review` is executed
- **Then** a change to spec_ledger.json or contract.md sets review_flags naming the file.

### S2.5 — a tool call left as text is named a parser mismatch
- **verifies:** C-2.5
- **pins:** 446c1f953d7fbb9b
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_tool_call_left_as_text_is_named_a_parser_mismatch -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_tool_call_left_as_text_is_named_a_parser_mismatch` is executed
- **Then** a claim holding `<tool_call>` or a `{"function": ...}` object yields a reason that names the tool-parser mismatch.

## C-3 — proved by the executor registry (lib/executors.py)

### S3.1 — the registry resolves known executors and refuses unknown
- **verifies:** C-3.1
- **pins:** 7d549a8ab872c710
- **run_cmd:** `python -m pytest tests/test_executors.py::test_the_registry_resolves_known_executors_and_refuses_unknown -q`
- **Given** tests/test_executors.py
- **When** the spec `test_the_registry_resolves_known_executors_and_refuses_unknown` is executed
- **Then** local-27b, local-9b, openhands and claude resolve; an unknown name raises.

### S3.2 — the local lane command grants only read and edit tools
- **verifies:** C-3.2
- **pins:** ae67c28a0102b672
- **run_cmd:** `python -m pytest tests/test_executors.py::test_the_local_lane_command_grants_only_read_and_edit_tools -q`
- **Given** tests/test_executors.py
- **When** the spec `test_the_local_lane_command_grants_only_read_and_edit_tools` is executed
- **Then** the argv has --tools with Read/Glob/Grep/Edit/Write only, a --max-turns cap and the local gateway in its env.

### S3.3 — the OpenHands run is rooted at the repository with the named model
- **verifies:** C-3.3
- **pins:** ef06c7bf4a5d3e03
- **run_cmd:** `python -m pytest tests/test_executors.py::test_the_openhands_run_is_rooted_at_the_repository_with_the_named_model -q`
- **Given** tests/test_executors.py
- **When** the spec `test_the_openhands_run_is_rooted_at_the_repository_with_the_named_model` is executed
- **Then** the OpenHands config carries the workspace path and the model given, and the local gateway as base url when asked.

### S3.4 — a missing executor is unavailable, not a traceback
- **verifies:** C-3.4
- **pins:** 045e91fa37cf913a
- **run_cmd:** `python -m pytest tests/test_executors.py::test_a_missing_executor_is_unavailable_not_a_traceback -q`
- **Given** tests/test_executors.py
- **When** the spec `test_a_missing_executor_is_unavailable_not_a_traceback` is executed
- **Then** availability is answered from an injected probe; a missing SDK or binary reads as unavailable with a reason.

## C-4 — proved by the dispatch record and the CLI (lib/dispatch.py, athena.py)

### S4.1 — a dispatch appends one record
- **verifies:** C-4.1
- **pins:** d380cd8bf00a64a5
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_dispatch_appends_one_record -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_dispatch_appends_one_record` is executed
- **Then** the record carries executor, task, landed, green, duration_ms and tokens.

### S4.2 — dispatch metrics report landed and green rates per executor
- **verifies:** C-4.2
- **pins:** c44986729cac1f02
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_dispatch_metrics_report_landed_and_green_rates_per_executor -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_dispatch_metrics_report_landed_and_green_rates_per_executor` is executed
- **Then** over recorded attempts the report gives attempts, landed rate and green rate for each executor.

### S4.3 — a packet without an executor is printed and not recorded
- **verifies:** C-4.3
- **pins:** f74bd5482d2aefea
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_packet_without_an_executor_is_printed_and_not_recorded -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_packet_without_an_executor_is_printed_and_not_recorded` is executed
- **Then** `athena dispatch --executor none` prints the packet and leaves the dispatch record untouched.

## C-5 — proved by the iteration loop in the dispatch module (lib/dispatch.py)

### S5.1 — a short iteration writes a checkpoint with files, reds and last words
- **verifies:** C-5.1
- **pins:** a3308008101ea43e
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_short_iteration_writes_a_checkpoint_with_files_reds_and_last_words -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_short_iteration_writes_a_checkpoint_with_files_reds_and_last_words` is executed
- **Then** the checkpoint names the changed files, the red commands with their tails and the executor's last words.

### S5.2 — the next iteration carries the checkpoint and starts fresh
- **verifies:** C-5.2
- **pins:** 644c2f4b0e867a45
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_the_next_iteration_carries_the_checkpoint_and_starts_fresh -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_the_next_iteration_carries_the_checkpoint_and_starts_fresh` is executed
- **Then** the next packet holds the checkpoint section and the untouched clauses, and nothing of the previous conversation.

### S5.3 — a passing iteration stops the loop and records the count
- **verifies:** C-5.3
- **pins:** 27efd5ac5055f0f1
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_passing_iteration_stops_the_loop_and_records_the_count -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_passing_iteration_stops_the_loop_and_records_the_count` is executed
- **Then** with a fail-then-pass attempt the loop stops after two iterations and says so.

### S5.4 — a checkpoint emits the bd notes command
- **verifies:** C-5.4
- **pins:** d525bc4978a64e49
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_checkpoint_emits_the_bd_notes_command -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_checkpoint_emits_the_bd_notes_command` is executed
- **Then** the command is `bd update <task key> --append-notes <checkpoint>`.

### S5.5 — a spent budget keeps the checkpoint and reports red
- **verifies:** C-5.5
- **pins:** acaf8fb97c70da7f
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_spent_budget_keeps_the_checkpoint_and_reports_red -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_spent_budget_keeps_the_checkpoint_and_reports_red` is executed
- **Then** three failing iterations end red with three checkpoints, the last one kept.
