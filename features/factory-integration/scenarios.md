# Scenarios: project factory entrypoint

## C-1 — From a real project request to verified execution

### S1.1 — Intent remains unproved
- **verifies:** C-1.1
- **pins:** 6c75c152ec7c608b
- **run_cmd:** `pytest tests/test_factory_entry.py::test_prepare_records_intent_once_without_claiming_a_pass -q`
- **Given** a Git project with no feature contract
- **When** its owner submits a task intent
- **Then** the task is saved once and no green specification is invented

### S1.2 — Isolated dispatch
- **verifies:** C-1.2
- **pins:** 85334f1ae4dfab69
- **run_cmd:** `pytest tests/test_factory_entry.py::test_run_requires_committed_proofs_and_keeps_project_tree_untouched -q`
- **Given** a project with committed proof artifacts
- **When** a plan task is dispatched
- **Then** the attempt runs in a separate Git worktree

### S1.3 — Cluster roles
- **verifies:** C-1.3
- **pins:** 7c416e6a5ce30ea7
- **run_cmd:** `pytest tests/test_factory_entry.py::test_cluster_agent_uses_role_based_gateway_in_pi_harness -q`
- **Given** the local Pi harness has the project gateway provider
- **When** Athena selects its cluster agent executor
- **Then** the request names the selected `agent` or `worker` role

### S1.4 — Credential-safe readiness
- **verifies:** C-1.4
- **pins:** 35d1be21c34a6d93
- **run_cmd:** `pytest tests/test_factory_entry.py::test_doctor_reports_capabilities_without_emitting_a_key -q`
- **Given** a local model provider with a credential
- **When** factory readiness is inspected
- **Then** the report contains capabilities and no credential

### S1.5 — Direct LAN route
- **verifies:** C-1.5
- **pins:** e12d84503835c92e
- **run_cmd:** `pytest tests/test_factory_entry.py::test_cluster_gateway_bypasses_the_inherited_desktop_proxy -q`
- **Given** a desktop HTTP proxy and a LAN gateway
- **When** a local harness process starts
- **Then** the LAN host is added to its proxy bypass list

### S1.6 — Resume the task
- **verifies:** C-1.6
- **pins:** 408822b953ebd30b
- **run_cmd:** `pytest tests/test_factory_entry.py::test_run_requires_committed_proofs_and_keeps_project_tree_untouched -q`
- **Given** a registered task worktree from a previous attempt
- **When** the same task is dispatched again on the same project commit
- **Then** its worktree is reused and the original project remains untouched
