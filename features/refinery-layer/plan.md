# Plan: Athena Refinery Layer

## Overview
Close two holes in the judge with the frame: a skipped test is red in the verdict and in the
runner; a green workspace is offered to a merge queue that admits on the record, rebases,
runs every contract and fast-forwards the target, refusing at the first failing stage with
the reason in a record and the task back in bd. Pure functions in `lib/refinery.py` take an
injected `run(argv, cwd) -> (code, output)`; the CLI wires the real git.

## Out of Scope
- A witness for stalled executors: the worker prints its JSON at the end, so silence on
  stdout is not a signal yet; a streaming output format comes first.
- Sandboxing the workspace.
- Merging anything the verdict did not call green.

## Phase 1: A skip is not proof
**Goal:** exit zero with a skipped or absent test is red in every judge.
**Depends on:** none
### Tasks
- [ ] T1.1 Judge a skipped or empty check red in the verdict
  - success_check: `python -m pytest tests/test_refinery.py::test_a_check_that_skipped_is_red_even_at_exit_zero -q`
  - files: `lib/dispatch.py`
  - verifies: S1.1
- [ ] T1.2 Attribute a skipped junit node as not passed
  - success_check: `python -m pytest tests/test_refinery.py::test_a_skipped_node_in_the_runners_report_is_not_passed -q`
  - files: `lib/spec_runner.py`
  - verifies: S1.2
- [ ] T1.3 Record a per-command spec run that skipped as not passed
  - success_check: `python -m pytest tests/test_refinery.py::test_a_spec_command_exiting_zero_with_a_skip_is_not_passed -q`
  - files: `lib/spec_runner.py`
  - verifies: S1.3
### Manual Verification
- A spec decorated with `@pytest.mark.skip` turns its clause red in `athena check`.

## Phase 2: The merge queue
**Goal:** a green workspace reaches the target only through admit, rebase, check, fast-forward.
**Depends on:** none
### Tasks
- [ ] T2.1 Admit an offer on the last record of its task
  - success_check: `python -m pytest tests/test_refinery.py::test_an_offer_is_admitted_only_on_a_green_last_record -q`
  - files: `lib/refinery.py`
  - verifies: S2.1
- [ ] T2.2 Rebase onto the target; abort and name the files on conflict
  - success_check: `python -m pytest tests/test_refinery.py::test_a_conflicting_rebase_is_aborted_and_the_files_named -q`
  - files: `lib/refinery.py`
  - verifies: S2.2
- [ ] T2.3 Refuse on the first failing contract
  - success_check: `python -m pytest tests/test_refinery.py::test_a_failing_contract_refuses_the_offer_with_its_first_cause -q`
  - files: `lib/refinery.py`
  - verifies: S2.3
- [ ] T2.4 Fast-forward the target or refuse
  - success_check: `python -m pytest tests/test_refinery.py::test_the_target_is_fast_forwarded_to_the_workspace_head_or_refused -q`
  - files: `lib/refinery.py`
  - verifies: S2.4
- [ ] T2.5 The merge record and the bd return command
  - success_check: `python -m pytest tests/test_refinery.py::test_an_offer_ends_in_a_merge_record_and_a_refusal_returns_the_task_to_bd -q`
  - files: `lib/refinery.py`
  - verifies: S2.5
- [ ] T2.6 Merge metrics per executor
  - success_check: `python -m pytest tests/test_refinery.py::test_metrics_report_merged_green_dispatches_per_executor_and_refusal_stages -q`
  - files: `lib/refinery.py`
  - verifies: S2.6
- [ ] T2.7 Wire `athena merge` and print the merge section in `athena metrics`
  - success_check: `python -m pytest tests/test_refinery.py -q`
  - files: `athena.py`
  - verifies: S2.1, S2.2, S2.3, S2.4, S2.5, S2.6
### Manual Verification
- `python athena.py merge features/refinery-layer/contract.md --front features/refinery-layer/plan.md --task T2.1 --workspace <worktree> --target master --text` merges a green worktree or says at which stage and why it refused.
