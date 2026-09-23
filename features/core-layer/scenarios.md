# Scenarios: Athena Core Layer (v3.10)

> Executable specs for `contract.md`. One spec per clause, ids `S<group>.<index>`
> mirroring the clause number. Each `run_cmd` is a real pytest node in this repo.
> `pins:` is written by `athena contract pin --write`.

---

## C-1 — proved by the scaffold and the document references (lib/scaffold.py, lib/docrefs.py)

### S1.1 — a scaffold writes a core when none exists above
- **verifies:** C-1.1
- **pins:** 428732dfeda5522d
- **run_cmd:** `python -m pytest tests/test_core.py::test_a_scaffold_writes_a_core_when_none_exists_above -q`
- **Given** tests/test_core.py
- **When** the spec `test_a_scaffold_writes_a_core_when_none_exists_above` is executed
- **Then** init writes CORE.md next to a feature that has none above it, and cites the one above when it exists.

### S1.2 — the first clause cites the core with its fingerprint
- **verifies:** C-1.2
- **pins:** 58c5455039e3d606
- **run_cmd:** `python -m pytest tests/test_core.py::test_the_first_clause_cites_the_core_with_its_fingerprint -q`
- **Given** tests/test_core.py
- **When** the spec `test_the_first_clause_cites_the_core_with_its_fingerprint` is executed
- **Then** the scaffolded contract carries `see: CORE.md@<fingerprint>` and docrefs reports it ok.

### S1.3 — the core template fits in forty lines
- **verifies:** C-1.3
- **pins:** adf62a872eb08ab1
- **run_cmd:** `python -m pytest tests/test_core.py::test_the_core_template_fits_in_forty_lines -q`
- **Given** tests/test_core.py
- **When** the spec `test_the_core_template_fits_in_forty_lines` is executed
- **Then** the rendered CORE.md has at most forty lines.

### S1.4 — a changed core makes the citing clause suspect
- **verifies:** C-1.4
- **pins:** d5f0703ffc065318
- **run_cmd:** `python -m pytest tests/test_core.py::test_a_changed_core_makes_the_citing_clause_suspect -q`
- **Given** tests/test_core.py
- **When** the spec `test_a_changed_core_makes_the_citing_clause_suspect` is executed
- **Then** after the core text changes, the clause that cited it is listed as suspect.

### S1.5 — a suspect core reference fails the contract leg
- **verifies:** C-1.5
- **pins:** 6236446d9a11aa8b
- **run_cmd:** `python -m pytest tests/test_core.py::test_a_suspect_core_reference_fails_the_contract_leg -q`
- **Given** tests/test_core.py
- **When** the spec `test_a_suspect_core_reference_fails_the_contract_leg` is executed
- **Then** the folded verdict fails on `contract.refs` and names it as the first cause.

## C-2 — proved by the contract parser and the sources report (lib/contract.py, lib/contract_report.py)

### S2.1 — a source attribute is read and kept out of the text
- **verifies:** C-2.1
- **pins:** b064607597aa7917
- **run_cmd:** `python -m pytest tests/test_source_attr.py::test_a_source_attribute_is_read_and_kept_out_of_the_text -q`
- **Given** tests/test_source_attr.py
- **When** the spec `test_a_source_attribute_is_read_and_kept_out_of_the_text` is executed
- **Then** `- source: audit` lands on the clause as an attribute and the normative text is unchanged.

### S2.2 — an unknown source is reported in lint
- **verifies:** C-2.2
- **pins:** ebdf5dfd8604da3b
- **run_cmd:** `python -m pytest tests/test_source_attr.py::test_an_unknown_source_is_reported_in_lint -q`
- **Given** tests/test_source_attr.py
- **When** the spec `test_an_unknown_source_is_reported_in_lint` is executed
- **Then** a source outside the vocabulary is a lint issue naming the clause.

### S2.3 — the source attribute round-trips through render
- **verifies:** C-2.3
- **pins:** b0a0791c74a957e4
- **run_cmd:** `python -m pytest tests/test_source_attr.py::test_the_source_attribute_round_trips_through_render -q`
- **Given** tests/test_source_attr.py
- **When** the spec `test_the_source_attribute_round_trips_through_render` is executed
- **Then** render(parse(x)) keeps the source of every clause.

### S2.4 — the sources report lists clauses under their source
- **verifies:** C-2.4
- **pins:** 0d85ac8c93f337eb
- **run_cmd:** `python -m pytest tests/test_source_attr.py::test_the_sources_report_lists_clauses_under_their_source -q`
- **Given** tests/test_source_attr.py
- **When** the spec `test_the_sources_report_lists_clauses_under_their_source` is executed
- **Then** every clause appears under its source, in document order.

### S2.5 — a clause without a source is counted as unstated
- **verifies:** C-2.5
- **pins:** 8423d00a8c16ea77
- **run_cmd:** `python -m pytest tests/test_source_attr.py::test_a_clause_without_a_source_is_counted_as_unstated -q`
- **Given** tests/test_source_attr.py
- **When** the spec `test_a_clause_without_a_source_is_counted_as_unstated` is executed
- **Then** a clause with no source is listed as unstated and under no source.

## C-3 — proved by the lessons module (lib/lessons.py)

### S3.1 — lessons are the clauses born from a failure signal
- **verifies:** C-3.1
- **pins:** c5bbfb79ba241cc2
- **run_cmd:** `python -m pytest tests/test_lessons.py::test_lessons_are_the_clauses_born_from_a_failure_signal -q`
- **Given** tests/test_lessons.py
- **When** the spec `test_lessons_are_the_clauses_born_from_a_failure_signal` is executed
- **Then** clauses sourced from review, audit, incident, ledger or mutation are lessons; design and withdrawn ones are not.

### S3.2 — a superseded lesson is carried to its live successors
- **verifies:** C-3.2
- **pins:** 2142c82a5b883e00
- **run_cmd:** `python -m pytest tests/test_lessons.py::test_a_superseded_lesson_is_carried_to_its_live_successors -q`
- **Given** tests/test_lessons.py
- **When** the spec `test_a_superseded_lesson_is_carried_to_its_live_successors` is executed
- **Then** a superseded lesson resolves forward and its live successors are what gets rerun.

### S3.3 — a rerun runs only the specs of lesson clauses
- **verifies:** C-3.3
- **pins:** 7fb13a68a5a696da
- **run_cmd:** `python -m pytest tests/test_lessons.py::test_a_rerun_runs_only_the_specs_of_lesson_clauses -q`
- **Given** tests/test_lessons.py
- **When** the spec `test_a_rerun_runs_only_the_specs_of_lesson_clauses` is executed
- **Then** the spec set of a rerun is exactly the specs bound to live lesson clauses.

### S3.4 — a red lesson spec reports the lesson as forgotten
- **verifies:** C-3.4
- **pins:** d5eef07710c684d8
- **run_cmd:** `python -m pytest tests/test_lessons.py::test_a_red_lesson_spec_reports_the_lesson_as_forgotten -q`
- **Given** tests/test_lessons.py
- **When** the spec `test_a_red_lesson_spec_reports_the_lesson_as_forgotten` is executed
- **Then** a lesson with a red spec is reported forgotten and the report does not pass.

### S3.5 — a lesson without a spec is unproved, not passed
- **verifies:** C-3.5
- **pins:** 4b42af77a5b58b50
- **run_cmd:** `python -m pytest tests/test_lessons.py::test_a_lesson_without_a_spec_is_unproved_not_passed -q`
- **Given** tests/test_lessons.py
- **When** the spec `test_a_lesson_without_a_spec_is_unproved_not_passed` is executed
- **Then** a live lesson clause with no spec is reported unproved and the report does not pass.

### S3.6 — a lesson left out on purpose is skipped, not judged
- **verifies:** C-3.6
- **pins:** 0b93b38f4ff4c96c
- **run_cmd:** `python -m pytest tests/test_lessons.py::test_a_lesson_left_out_on_purpose_is_skipped_not_judged -q`
- **Given** tests/test_lessons.py
- **When** the spec `test_a_lesson_left_out_on_purpose_is_skipped_not_judged` is executed
- **Then** a lesson whose every spec the caller excluded is reported skipped; a spec that merely never ran is still forgotten.

## C-4 — proved against the repository itself (CLAUDE.md, docs/history)

### S4.1 — the root has an entry document under thirty lines
- **verifies:** C-4.1
- **pins:** 7d5f31bb920e4dff
- **run_cmd:** `python -m pytest tests/test_entry.py::test_the_root_has_an_entry_document_under_thirty_lines -q`
- **Given** tests/test_entry.py
- **When** the spec `test_the_root_has_an_entry_document_under_thirty_lines` is executed
- **Then** CLAUDE.md exists, has at most thirty lines, and names CORE.md, contract.md and `athena check`.

### S4.2 — design history lives under docs/history, not the root
- **verifies:** C-4.2
- **pins:** ed699bb0728095c6
- **run_cmd:** `python -m pytest tests/test_entry.py::test_design_history_lives_under_docs_history_not_the_root -q`
- **Given** tests/test_entry.py
- **When** the spec `test_design_history_lives_under_docs_history_not_the_root` is executed
- **Then** no athena-*plan*.md file sits in the repository root and docs/history holds them.

### S4.3 — every command the entry names is one the CLI accepts
- **verifies:** C-4.3
- **pins:** 951c203b3603a759
- **run_cmd:** `python -m pytest tests/test_entry.py::test_every_command_the_entry_names_is_one_the_cli_accepts -q`
- **Given** tests/test_entry.py
- **When** the spec `test_every_command_the_entry_names_is_one_the_cli_accepts` is executed
- **Then** each `python athena.py <cmd> [<sub>]` in CLAUDE.md resolves to a registered parser.

## C-5 — proved by the gate module and the project settings (lib/gate.py, .claude/settings.json)

### S5.1 — the project settings register the gate as a Stop hook
- **verifies:** C-5.1
- **pins:** 0c6b2cdf977f17bf
- **run_cmd:** `python -m pytest tests/test_gate.py::test_the_project_settings_register_the_gate_as_a_stop_hook -q`
- **Given** tests/test_gate.py
- **When** the spec `test_the_project_settings_register_the_gate_as_a_stop_hook` is executed
- **Then** .claude/settings.json has a Stop hook whose command runs hooks/contract-criterion-gate.sh.

### S5.2 — a contract is recognised by its clauses, not its name
- **verifies:** C-5.2
- **pins:** 892b17ba88203b2c
- **run_cmd:** `python -m pytest tests/test_gate.py::test_a_contract_is_recognised_by_its_clauses_not_its_name -q`
- **Given** tests/test_gate.py
- **When** the spec `test_a_contract_is_recognised_by_its_clauses_not_its_name` is executed
- **Then** a file named contract.md without clause bullets is not a contract; one with them is.

### S5.3 — one failing contract fails the folded gate
- **verifies:** C-5.3
- **pins:** 52ed98e27d5d0ed3
- **run_cmd:** `python -m pytest tests/test_gate.py::test_one_failing_contract_fails_the_folded_gate -q`
- **Given** tests/test_gate.py
- **When** the spec `test_one_failing_contract_fails_the_folded_gate` is executed
- **Then** two passing verdicts and one failing fold to a failing gate that names the failing one.

### S5.4 — no contract means no opinion
- **verifies:** C-5.4
- **pins:** 0c821a65d27b32dc
- **run_cmd:** `python -m pytest tests/test_gate.py::test_no_contract_means_no_opinion -q`
- **Given** tests/test_gate.py
- **When** the spec `test_no_contract_means_no_opinion` is executed
- **Then** an empty scan folds to passed with no decision to block.

### S5.5 — the reason names the contract and its first cause
- **verifies:** C-5.5
- **pins:** d4fa9c6dc4d8aaee
- **run_cmd:** `python -m pytest tests/test_gate.py::test_the_reason_names_the_contract_and_its_first_cause -q`
- **Given** tests/test_gate.py
- **When** the spec `test_the_reason_names_the_contract_and_its_first_cause` is executed
- **Then** the block reason carries the failing contract path and its first cause.

### S5.6 — the bypass variable passes and says so
- **verifies:** C-5.6
- **pins:** f661b742a7058888
- **run_cmd:** `python -m pytest tests/test_gate.py::test_the_bypass_variable_passes_and_says_so -q`
- **Given** tests/test_gate.py
- **When** the spec `test_the_bypass_variable_passes_and_says_so` is executed
- **Then** with the bypass set the gate passes and the report says bypassed.

### S5.7 — the nudge budget is spent after two blocks
- **verifies:** C-5.7
- **pins:** b2a09e4c3f04a015
- **run_cmd:** `python -m pytest tests/test_gate.py::test_the_nudge_budget_is_spent_after_two_blocks -q`
- **Given** tests/test_gate.py
- **When** the spec `test_the_nudge_budget_is_spent_after_two_blocks` is executed
- **Then** the third block in one session passes and says the budget is spent.

## C-6 — proved by the batching spec runner (lib/spec_runner.py)

### S6.1 — specs sharing an invocation run in one process
- **verifies:** C-6.1
- **pins:** acf57916eedce3da
- **run_cmd:** `python -m pytest tests/test_spec_batch.py::test_specs_sharing_an_invocation_run_in_one_process -q`
- **Given** tests/test_spec_batch.py
- **When** the spec `test_specs_sharing_an_invocation_run_in_one_process` is executed
- **Then** three specs with the same invocation prefix cause one spawn carrying all three nodes.

### S6.2 — each batched spec gets its own verdict and duration
- **verifies:** C-6.2
- **pins:** 21da30b1a53746a8
- **run_cmd:** `python -m pytest tests/test_spec_batch.py::test_each_batched_spec_gets_its_own_verdict_and_duration -q`
- **Given** tests/test_spec_batch.py
- **When** the spec `test_each_batched_spec_gets_its_own_verdict_and_duration` is executed
- **Then** verdict and duration per spec come from the runner's report, in document order.

### S6.3 — a spec missing from the report is red
- **verifies:** C-6.3
- **pins:** 0fa904128605708e
- **run_cmd:** `python -m pytest tests/test_spec_batch.py::test_a_spec_missing_from_the_report_is_red -q`
- **Given** tests/test_spec_batch.py
- **When** the spec `test_a_spec_missing_from_the_report_is_red` is executed
- **Then** a node the report never mentions is recorded red with a stated reason.

### S6.4 — an isolated clause runs in its own process
- **verifies:** C-6.4
- **pins:** 5303e82d7f692573
- **run_cmd:** `python -m pytest tests/test_spec_batch.py::test_an_isolated_clause_runs_in_its_own_process -q`
- **Given** tests/test_spec_batch.py
- **When** the spec `test_an_isolated_clause_runs_in_its_own_process` is executed
- **Then** a spec whose clause carries `isolated` is spawned alone while the rest share one process.

### S6.5 — early-exit and report options are never batched
- **verifies:** C-6.5
- **pins:** bed3aa4745bb335e
- **run_cmd:** `python -m pytest tests/test_spec_batch.py::test_early_exit_and_report_options_are_never_batched -q`
- **Given** tests/test_spec_batch.py
- **When** the spec `test_early_exit_and_report_options_are_never_batched` is executed
- **Then** an invocation with -x, --maxfail or --junitxml is not batchable.

### S6.6 — an aborted batch is rerun one process per spec
- **verifies:** C-6.6
- **pins:** 02402acd84a4251b
- **run_cmd:** `python -m pytest tests/test_spec_batch.py::test_an_aborted_batch_is_rerun_one_process_per_spec -q`
- **Given** tests/test_spec_batch.py
- **When** the spec `test_an_aborted_batch_is_rerun_one_process_per_spec` is executed
- **Then** a batch whose report holds zero tests is rerun spec by spec and only the bad one is red.

### S6.7 — a batched failure keeps its message
- **verifies:** C-6.7
- **pins:** 7e08e83ea60f6c38
- **run_cmd:** `python -m pytest tests/test_spec_batch.py::test_a_batched_failure_keeps_its_message -q`
- **Given** tests/test_spec_batch.py
- **When** the spec `test_a_batched_failure_keeps_its_message` is executed
- **Then** the failure text from the report lands in the ledger's output tail.

### S6.8 — an injected executor runs each spec alone
- **verifies:** C-6.8
- **pins:** 7c149e86fb907152
- **run_cmd:** `python -m pytest tests/test_spec_batch.py::test_an_injected_executor_runs_each_spec_alone -q`
- **Given** tests/test_spec_batch.py
- **When** the spec `test_an_injected_executor_runs_each_spec_alone` is executed
- **Then** with an executor injected every spec goes through it, one command each, and nothing is spawned.
