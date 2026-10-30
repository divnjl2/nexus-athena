# Scenarios: Optional formal evidence

### S1.1 - Search is bounded
- **verifies:** C-1.1
- **pins:** af5a970dbe9cca6f
- **run_cmd:** `python -m pytest tests/test_formal_evidence.py::test_search_is_not_a_proof -q`
- **Given** successful and empty search outputs
- **When** results are classified
- **Then** no result is promoted to a proof of user intent.

### S1.2 - Verification is relative
- **verifies:** C-1.2
- **pins:** 8521f5fe5dd3e2fe
- **run_cmd:** `python -m pytest tests/test_formal_evidence.py::test_dafny_requires_nonempty_successful_verification -q`
- **Given** nonempty and empty Dafny verification summaries
- **When** results are classified
- **Then** only successful nonempty verification has relative-to-spec status.

### S1.3 - Tool failures are unknown
- **verifies:** C-1.3
- **pins:** f1fb57c84fc5e7f2
- **run_cmd:** `python -m pytest tests/test_formal_evidence.py::test_timeout_and_unknown_output_are_unknown -q`
- **Given** timeouts and unrecognized output
- **When** tools execute
- **Then** assurance remains unknown.

### S1.4 - Changed inputs invalidate results
- **verifies:** C-1.4
- **pins:** 27adfe00708c07f6
- **run_cmd:** `python -m pytest tests/test_formal_evidence.py::test_mutated_inputs_invalidate_tool_result -q`
- **Given** fingerprinted inputs
- **When** execution changes their bytes
- **Then** the successful tool result is invalidated.

### S1.5 - Model is not user intent
- **verifies:** C-1.5
- **pins:** 6e98930501c8a42b
- **run_cmd:** `python -m pytest tests/test_formal_evidence.py::test_view_preserves_model_and_intent_boundaries -q`
- **Given** a verified model
- **When** its receipt is rendered
- **Then** model and intent boundaries remain visible.

### S1.6 - Self-check analyzes production bytes
- **verifies:** C-1.6
- **pins:** 4d643199a720a391
- **run_cmd:** `python -m pytest tests/test_crosshair_selfcheck.py::test_selfcheck_preserves_source_and_seeds_real_state_errors -q`
- **Given** the production evidence-state reducer
- **When** self-check snapshots and seeds control variants
- **Then** the baseline remains byte-identical, valid alternatives agree and each seeded defect changes required behavior.

### S1.7 - Replay and tool search are distinct
- **verifies:** C-1.7
- **pins:** 0892c5854852fe1e
- **run_cmd:** `python -m pytest tests/test_crosshair_selfcheck.py::test_replay_distinguishes_executed_state_table_from_tool_claims -q`
- **Given** a frozen function and actual CrossHair observations
- **When** its four-input replay is displayed
- **Then** expected and actual values remain separate from the tool's search result.

### S1.8 - GSN shows argument gaps
- **verifies:** C-1.8
- **pins:** de2dce3380f02427
- **run_cmd:** `python -m pytest tests/test_gsn_case.py::test_gsn_leaves_global_intent_and_coverage_claims_open -q`
- **Given** an archived tool observation
- **When** its claim, strategy and evidence graph is exported
- **Then** global intent and completeness claims stay open and evidence links remain explicit.
