# Scenarios: Requirement assurance

### S1.1 - Every obligation remains visible
- **verifies:** C-1.1
- **pins:** d00621db7248e599
- **run_cmd:** `python -m pytest tests/test_assurance.py::test_all_live_requirements_remain_in_denominator -q`
- **Given** a contract with an unobserved obligation
- **When** assessment runs
- **Then** that obligation remains in the denominator as unknown.

### S1.2 - Stale evidence loses support
- **verifies:** C-1.2
- **pins:** 0239946f74ed9c36
- **run_cmd:** `python -m pytest tests/test_assurance.py::test_input_and_artifact_drift_remove_support tests/test_assurance.py::test_contract_drift_and_missing_input_are_unknown -q`
- **Given** evidence bound to exact bytes
- **When** those bytes change or disappear
- **Then** the evidence cannot support the current implementation.

### S1.3 - Green is not meaning
- **verifies:** C-1.3
- **pins:** cc8932c24b3bcc39
- **run_cmd:** `python -m pytest tests/test_assurance.py::test_green_execution_is_not_adequacy tests/test_assurance.py::test_controls_from_different_scope_cannot_support_execution -q`
- **Given** green execution without matching semantic controls
- **When** assessment runs
- **Then** implementation assurance remains unknown.

### S1.4 - Conflicting evidence is visible
- **verifies:** C-1.4
- **pins:** a33b353d88ceb2f6
- **run_cmd:** `python -m pytest tests/test_assurance.py::test_conflicts_are_visible_in_each_dimension tests/test_assurance.py::test_failed_unvalidated_check_does_not_refute_implementation -q`
- **Given** current positive and negative observations
- **When** assessment runs
- **Then** each affected observation dimension reports conflict; implementation is unknown when its controls conflict, and reports conflict when validated checks both pass and fail.

### S1.7 - Executed oracle controls
- **verifies:** C-1.3
- **pins:** cc8932c24b3bcc39
- **run_cmd:** `python -m pytest tests/test_assurance_demo.py::test_executed_controls_distinguish_defects_from_bad_checks -q`
- **Given** actual correct, defective and alternative implementations and sound, strict and vacuous checks
- **When** the demonstration executes checks and an activation witness
- **Then** only the sound controls support or contradict implementation assurance.

### S1.5 - Meaning requires review
- **verifies:** C-1.5
- **pins:** 2999cbd7da3a49c3
- **run_cmd:** `python -m pytest tests/test_assurance.py::test_missing_code_review_is_unknown_even_with_green_tests -q`
- **Given** green execution and semantic controls without code review
- **When** assessment runs
- **Then** code correspondence remains unknown.

### S1.6 - Counts do not imply probability
- **verifies:** C-1.6
- **pins:** 84400973d72b1b84
- **run_cmd:** `python -m pytest tests/test_assurance.py::test_report_is_bounded_and_escapes_authored_content -q`
- **Given** an assurance report
- **When** it is rendered
- **Then** its scope is evidence coverage and authored HTML is escaped.
