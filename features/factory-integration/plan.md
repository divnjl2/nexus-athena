# Plan: project factory entrypoint

## Overview
Let a frontier agent turn a project intent into clauses, scenarios and small tasks; execute committed tasks on the owner's cluster through a harness and judge the patch independently.

## Out of Scope
- Automatic promotion or merge of an executor patch.
- Automatic editing of a project's CORE.md or AGENTS.md.

## Phase 1: Project entry
**Goal:** prepare a task and run it with preserved proofs.
**Depends on:** none
### Tasks
- [x] T1.1 Record an intent without fake proof
  - success_check: `pytest tests/test_factory_entry.py::test_prepare_records_intent_once_without_claiming_a_pass -q`
  - files: `factory.py`
  - verifies: S1.1
- [x] T1.2 Isolate dispatch in a Git worktree
  - success_check: `pytest tests/test_factory_entry.py::test_run_requires_committed_proofs_and_keeps_project_tree_untouched -q`
  - files: `factory.py`
  - verifies: S1.2
- [x] T1.3 Use the cluster agent role through Pi
  - success_check: `pytest tests/test_factory_entry.py::test_cluster_agent_uses_role_based_gateway_in_pi_harness -q`
  - files: `lib/executors.py`
  - verifies: S1.3
- [x] T1.4 Report readiness without secrets
  - success_check: `pytest tests/test_factory_entry.py::test_doctor_reports_capabilities_without_emitting_a_key -q`
  - files: `factory.py`
  - verifies: S1.4
- [x] T1.5 Reach the LAN gateway through the local harness
  - success_check: `pytest tests/test_factory_entry.py::test_cluster_gateway_bypasses_the_inherited_desktop_proxy -q`
  - files: `factory.py`
  - verifies: S1.5
- [x] T1.6 Resume an interrupted task on its existing base
  - success_check: `pytest tests/test_factory_entry.py::test_run_requires_committed_proofs_and_keeps_project_tree_untouched -q`
  - files: `factory.py`
  - verifies: S1.6
