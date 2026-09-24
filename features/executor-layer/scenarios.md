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

### S1.6 — the packet states each spec's current verdict before the executor starts
- **verifies:** C-1.6
- **pins:** 705e21cd500329ac
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_the_packet_states_each_specs_current_verdict_before_the_executor_starts -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_the_packet_states_each_specs_current_verdict_before_the_executor_starts` is executed
- **Then** a red check appears as RED with its tail, a green one as green, and the text says the task is not done while a spec is RED.

### S1.7 — the packet ends with the order to act
- **verifies:** C-1.7
- **pins:** 0632e85afb29e720
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_the_packet_ends_with_the_order_to_act -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_the_packet_ends_with_the_order_to_act` is executed
- **Then** after the inlined files and the status block, the last lines of the packet name the first file to edit and say there is no user to ask.

### S1.8 — a long module is inlined as what the task needs of it
- **verifies:** C-1.8
- **pins:** 5231d7701e035e81
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_long_module_is_inlined_as_what_the_task_needs_of_it -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_long_module_is_inlined_as_what_the_task_needs_of_it` is executed
- **Then** past the threshold the packet carries the header, the imported definitions whole, the other signatures with bodies omitted, and names the imported definitions the module lacks; under it the module goes whole.

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

### S2.6 — a changed file brings the specs of the clauses that own it into the verdict
- **verifies:** C-2.6
- **pins:** e265cd1cfc8abb60
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_a_changed_file_brings_the_specs_of_its_owning_clauses_into_the_verdict -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_a_changed_file_brings_the_specs_of_its_owning_clauses_into_the_verdict` is executed
- **Then** the run commands of every clause owning lines in the changed file are added, across contracts, without repeating the task's own checks.

### S2.7 — editing the spec's own test file is flagged and never green
- **verifies:** C-2.7
- **pins:** af16c665e70340b8
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_editing_the_specs_own_test_file_is_flagged_and_never_green -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_editing_the_specs_own_test_file_is_flagged_and_never_green` is executed
- **Then** a change to the test module of the task's spec sets review_flags, green=False and a reason, even when every check exited 0.

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

### S3.5 — OpenHands gets an implementer's prompt, not an explorer's
- **verifies:** C-3.5
- **pins:** b4f9bbf4e2741ed3
- **run_cmd:** `python -m pytest tests/test_executors.py::test_openhands_gets_an_implementers_prompt_not_an_explorers -q`
- **Given** tests/test_executors.py
- **When** the spec `test_openhands_gets_an_implementers_prompt_not_an_explorers` is executed
- **Then** the config carries the implementer prompt by default, forbids exploring and names the done criterion; `prompt="default"` leaves it empty.

### S3.6 — the pi executor runs print mode on the lane with the packet on stdin
- **verifies:** C-3.6
- **pins:** 5c01151cd397fa0a
- **run_cmd:** `python -m pytest tests/test_executors.py::test_the_pi_executor_runs_print_mode_on_the_lane_with_the_packet_on_stdin -q`
- **Given** tests/test_executors.py
- **When** the spec `test_the_pi_executor_runs_print_mode_on_the_lane_with_the_packet_on_stdin` is executed
- **Then** the argv carries -p, JSON mode, the no-session/extensions/skills/context flags, the four tools, the provider and model, the order last; the packet is stdin; pi_result reads text, tokens and errors from the events; availability probes the binary.

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

### S4.4 — dispatch metrics report iterations to green per task
- **verifies:** C-4.4
- **pins:** 135bc2d9121db217
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_dispatch_metrics_report_iterations_to_green_per_task -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_dispatch_metrics_report_iterations_to_green_per_task` is executed
- **Then** the report carries, per task, the attempts and the iteration at which it went green, or none when it never did.

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

### S5.6 — fanned attempts keep the first green verdict
- **verifies:** C-5.6
- **pins:** cfe15fba21bf653d
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_fanned_attempts_keep_the_first_green_verdict -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_fanned_attempts_keep_the_first_green_verdict` is executed
- **Then** of several attempts' verdicts the first green one is picked, and the copies are named beside the workspace.

### S5.7 — without a green attempt the least red landing is carried forward
- **verifies:** C-5.7
- **pins:** f889324f9b1b2971
- **run_cmd:** `python -m pytest tests/test_dispatch.py::test_without_a_green_attempt_the_least_red_landing_is_carried_forward -q`
- **Given** tests/test_dispatch.py
- **When** the spec `test_without_a_green_attempt_the_least_red_landing_is_carried_forward` is executed
- **Then** the landed attempt with the fewest red checks is picked, the quicker on a tie, and none when nothing landed.

## C-6 — proved by the tool-call normaliser (lib/toolcalls.py)

### S6.1 — a tool call left as text becomes a structured call
- **verifies:** C-6.1
- **pins:** c69fa60a67b45df9
- **run_cmd:** `python -m pytest tests/test_toolcalls.py::test_a_tool_call_left_as_text_becomes_a_structured_call -q`
- **Given** tests/test_toolcalls.py
- **When** the spec `test_a_tool_call_left_as_text_becomes_a_structured_call` is executed
- **Then** the distillate's, the XML and the OpenAI shapes come back as tool_calls with the leading text kept as content.

### S6.2 — a well-formed completion passes through unchanged
- **verifies:** C-6.2
- **pins:** f8780ec1956e48c3
- **run_cmd:** `python -m pytest tests/test_toolcalls.py::test_a_well_formed_completion_passes_through_unchanged -q`
- **Given** tests/test_toolcalls.py
- **When** the spec `test_a_well_formed_completion_passes_through_unchanged` is executed
- **Then** native tool_calls, plain prose and unparsable tags are returned exactly as received.

### S6.3 — the OpenHands executor can be pointed at the relay
- **verifies:** C-6.3
- **pins:** ef8751c80b154c19
- **run_cmd:** `python -m pytest tests/test_toolcalls.py::test_the_openhands_executor_can_be_pointed_at_the_relay -q`
- **Given** tests/test_toolcalls.py
- **When** the spec `test_the_openhands_executor_can_be_pointed_at_the_relay` is executed
- **Then** the executor config carries the relay url and the gateway constant is untouched.

### S6.4 — a tool-carrying request goes out with thinking off
- **verifies:** C-6.4
- **pins:** 4af3033ba57c2b08
- **run_cmd:** `python -m pytest tests/test_toolcalls.py::test_a_tool_carrying_request_goes_out_with_thinking_off -q`
- **Given** tests/test_toolcalls.py
- **When** the spec `test_a_tool_carrying_request_goes_out_with_thinking_off` is executed
- **Then** a request with tools gains chat_template_kwargs.enable_thinking=false; one that set it already, or has no tools, is left alone.

### S6.5 — a messages response with a textual tool call becomes tool_use blocks
- **verifies:** C-6.5
- **pins:** 2ff53728c00396c9
- **run_cmd:** `python -m pytest tests/test_toolcalls.py::test_a_messages_response_with_a_textual_tool_call_becomes_tool_use_blocks -q`
- **Given** tests/test_toolcalls.py
- **When** the spec `test_a_messages_response_with_a_textual_tool_call_becomes_tool_use_blocks` is executed
- **Then** the text block becomes text + tool_use with stop_reason tool_use, the SSE frames carry the call, prose and real tool_use pass through.

### S6.6 — the relay leaves thinking as the lane has it unless asked
- **verifies:** C-6.6
- **pins:** fa01125cbd4a59ee
- **run_cmd:** `python -m pytest tests/test_toolcalls.py::test_the_relay_leaves_thinking_as_the_lane_has_it_unless_asked -q`
- **Given** tests/test_toolcalls.py
- **When** the spec `test_the_relay_leaves_thinking_as_the_lane_has_it_unless_asked` is executed
- **Then** the relay's default is thinking on; only an explicit off changes a tool-carrying request.
