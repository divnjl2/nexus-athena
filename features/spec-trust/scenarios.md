# Scenarios: Spec trust

### S2.12 - Stable receipts across tool invocations
- **verifies:** C-2.12
- **pins:** 09e9eaf0160ec047
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_receipt_ignores_tool_trace_but_tracks_runtime_settings -q`
- **Given** identical inputs and differing tool-call tracing metadata
- **When** verifier context is fingerprinted
- **Then** the receipt remains current, but changing a runtime setting changes its fingerprint.

### S2.11 - Activation must distinguish the baseline
- **verifies:** C-2.11
- **pins:** 168eadb1d049469e
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_activation_probe_must_discriminate_clean_baseline tests/test_spec_trust.py::test_valid_and_violation_controls_run -q`
- **Given** either a constant-true probe or a real activation predicate
- **When** native audit checks the clean and violating versions
- **Then** the constant probe fails and the real predicate has typed negative and positive evidence.

### S2.10 - the current interpreter executes specs
- **verifies:** C-2.10
- **pins:** 5d472772298bd461
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_spec_runner_uses_the_verifier_interpreter -q`
- **Given** a verifier in a virtual environment
- **When** a command names generic Python or pytest
- **Then** the process boundary chooses the verifier's current interpreter.

### S1.1 - test no decisions have no score
- **verifies:** C-1.1
- **pins:** a7e167ad0ca0595f
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_no_decisions_have_no_score -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S1.2 - test missing mutation evidence is incomplete
- **verifies:** C-1.2
- **pins:** 545aaf78e8c6ae2f
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_missing_mutation_evidence_is_incomplete -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S1.3 - test tool errors are not kills
- **verifies:** C-1.3
- **pins:** cf226d3920ec4d70
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_tool_errors_are_not_kills -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S1.4 - test red baseline cannot kill
- **verifies:** C-1.4
- **pins:** 2ffaeea75f5bc30b
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_red_baseline_cannot_kill -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S1.5 - test per clause scores exclude unknowns
- **verifies:** C-1.5
- **pins:** 6c0bcb79b7a1abca
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_per_clause_scores_exclude_unknowns -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S1.6 - test a shared line kill is not evidence for every clause
- **verifies:** C-1.6
- **pins:** da4a11daebd7e232
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_a_shared_line_kill_is_not_evidence_for_every_clause -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S1.7 - test a capped sweep has only scoped score
- **verifies:** C-1.7
- **pins:** 35277d1e5b647b5a
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_a_capped_sweep_has_only_scoped_score -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S2.1 - test manifest pins are enforced
- **verifies:** C-2.1
- **pins:** 246bfead4a94da91
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_manifest_pins_are_enforced -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S2.2 - test valid and violation controls run
- **verifies:** C-2.2
- **pins:** 579392f4dc8e560c
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_valid_and_violation_controls_run -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S2.3 - test bad oracles fail in both directions
- **verifies:** C-2.3
- **pins:** cb22ebb8eb8e72e0
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_bad_oracles_fail_in_both_directions -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S2.4 - test activation and tool errors are inconclusive
- **verifies:** C-2.4
- **pins:** 271cf658c5993708
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_activation_and_tool_errors_are_inconclusive -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S2.5 - test only implementation overlays are admitted
- **verifies:** C-2.5
- **pins:** 2050055225021744
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_only_implementation_overlays_are_admitted -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S2.6 - test protected input changes reject evidence
- **verifies:** C-2.6
- **pins:** 633fb9dbb635570a
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_protected_input_changes_reject_evidence -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S2.7 - test context covers inputs manifest and environment
- **verifies:** C-2.7
- **pins:** b9926091ffda7391
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_context_covers_inputs_manifest_and_environment -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S2.8 - test missing controls and gaps remain incomplete
- **verifies:** C-2.8
- **pins:** 8b94af4975a83c8c
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_missing_controls_and_gaps_remain_incomplete -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.

### S2.9 - test requested receipt must be current and for this contract
- **verifies:** C-2.9
- **pins:** 986df626ce4d2bc4
- **run_cmd:** `python -m pytest tests/test_spec_trust.py::test_requested_receipt_must_be_current_and_for_this_contract -q`
- **Given** the declared evidence boundaries
- **When** the boundary is exercised
- **Then** the verifier distinguishes observations from absent or invalid evidence.
