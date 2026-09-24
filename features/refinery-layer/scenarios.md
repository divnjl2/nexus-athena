# Scenarios: Athena Refinery Layer (v3.13)

> Executable specs for `contract.md`. One spec per clause, ids `S<group>.<index>`
> mirroring the clause number. `pins:` is written by `athena contract pin --write`.

---

## C-1 — proved in the verdict (lib/dispatch.py) and the runner (lib/spec_runner.py)

### S1.1 — a check that skipped is red even at exit zero
- **verifies:** C-1.1
- **pins:** b9b446e9e77bef1e
- **run_cmd:** `python -m pytest tests/test_refinery.py::test_a_check_that_skipped_is_red_even_at_exit_zero -q`
- **Given** tests/test_refinery.py
- **When** the spec `test_a_check_that_skipped_is_red_even_at_exit_zero` is executed
- **Then** a check with exit 0 whose tail says "skipped" or "no tests ran" is red with a reason naming the skip; a "passed" tail stays green.

### S1.2 — a skipped node in the runner's report is not passed
- **verifies:** C-1.2
- **pins:** 018588d159400ae1
- **run_cmd:** `python -m pytest tests/test_refinery.py::test_a_skipped_node_in_the_runners_report_is_not_passed -q`
- **Given** tests/test_refinery.py
- **When** the spec `test_a_skipped_node_in_the_runners_report_is_not_passed` is executed
- **Then** a junit testcase carrying `<skipped>` attributes to a SpecResult that is not passed and whose tail names the skip.

### S1.3 — a spec command exiting zero with a skip is not passed
- **verifies:** C-1.3
- **pins:** 11ca9187a2ecf984
- **run_cmd:** `python -m pytest tests/test_refinery.py::test_a_spec_command_exiting_zero_with_a_skip_is_not_passed -q`
- **Given** tests/test_refinery.py
- **When** the spec `test_a_spec_command_exiting_zero_with_a_skip_is_not_passed` is executed
- **Then** run_specs through an executor that returns (0, "1 skipped") records the spec as not passed.

## C-2 — proved by the refinery module (lib/refinery.py)

### S2.1 — an offer is admitted only on a green last record
- **verifies:** C-2.1
- **pins:** b0218466ec3cc2a7
- **run_cmd:** `python -m pytest tests/test_refinery.py::test_an_offer_is_admitted_only_on_a_green_last_record -q`
- **Given** tests/test_refinery.py
- **When** the spec `test_an_offer_is_admitted_only_on_a_green_last_record` is executed
- **Then** admit() says yes for a task whose last record is green and no, with the record's words, for a red last record, an earlier green one, or no record at all.

### S2.2 — a conflicting rebase is aborted and the files named
- **verifies:** C-2.2
- **pins:** a459562b604d05be
- **run_cmd:** `python -m pytest tests/test_refinery.py::test_a_conflicting_rebase_is_aborted_and_the_files_named -q`
- **Given** tests/test_refinery.py
- **When** the spec `test_a_conflicting_rebase_is_aborted_and_the_files_named` is executed
- **Then** on a real temporary repository a rebase that conflicts is aborted, refused and names the file; one that does not conflict lands.

### S2.3 — a failing contract refuses the offer with its first cause
- **verifies:** C-2.3
- **pins:** de7d35a8fcb2aa68
- **run_cmd:** `python -m pytest tests/test_refinery.py::test_a_failing_contract_refuses_the_offer_with_its_first_cause -q`
- **Given** tests/test_refinery.py
- **When** the spec `test_a_failing_contract_refuses_the_offer_with_its_first_cause` is executed
- **Then** over gate-shaped verdicts, first_failure() is empty when every contract holds and names the contract and its first cause otherwise.

### S2.4 — the target is fast-forwarded to the workspace head or refused
- **verifies:** C-2.4
- **pins:** 0bfc035c2906199e
- **run_cmd:** `python -m pytest tests/test_refinery.py::test_the_target_is_fast_forwarded_to_the_workspace_head_or_refused -q`
- **Given** tests/test_refinery.py
- **When** the spec `test_the_target_is_fast_forwarded_to_the_workspace_head_or_refused` is executed
- **Then** on a real temporary repository the target ref moves to the workspace head when it is an ancestor, and the offer is refused with a reason naming the fast-forward when it is not.

### S2.5 — an offer ends in a merge record and a refusal returns the task to bd
- **verifies:** C-2.5
- **pins:** 836ed98aa93cb2af
- **run_cmd:** `python -m pytest tests/test_refinery.py::test_an_offer_ends_in_a_merge_record_and_a_refusal_returns_the_task_to_bd -q`
- **Given** tests/test_refinery.py
- **When** the spec `test_an_offer_ends_in_a_merge_record_and_a_refusal_returns_the_task_to_bd` is executed
- **Then** merge_record() carries task, executor, stage, ok and reason; bd_return_command() reopens the task with the stage and reason appended to its notes.

### S2.6 — metrics report merged green dispatches per executor and refusal stages
- **verifies:** C-2.6
- **pins:** c06e50ea1b697a0a
- **run_cmd:** `python -m pytest tests/test_refinery.py::test_metrics_report_merged_green_dispatches_per_executor_and_refusal_stages -q`
- **Given** tests/test_refinery.py
- **When** the spec `test_metrics_report_merged_green_dispatches_per_executor_and_refusal_stages` is executed
- **Then** merge_metrics() counts per executor the green dispatches, the merged ones and the refusals by stage, and its render names them.
