# Scenarios: Semantic repair cycle

### S1.1 - Derive issue intent before implementation
- **verifies:** C-1.1
- **pins:** 2767d319c0df3dea
- **run_cmd:** `python -m pytest tests/test_tdd_intent.py::test_issue_only_model_context_and_charged_frozen_result tests/test_tdd_intent.py -q`
- **Given** an unchanged public issue and untrusted model declarations
- **When** the issue-only passport is prepared
- **Then** source anchors are checked and unsupported semantics are not attested.

### S1.2 - Cover new assertions and their support
- **verifies:** C-1.2
- **pins:** 9d58fcc748c48bf9
- **run_cmd:** `python -m pytest tests/test_tdd_assertion_support.py::test_unsupported_literal_is_rejected_and_unknown_support_is_incomplete tests/test_tdd_assertion_support.py -q`
- **Given** a frozen intent and a candidate with new assertions
- **When** assertion support is reviewed
- **Then** unsupported, unresolved and missing support cannot release a candidate.

### S1.3 - Preserve and review open issue questions
- **verifies:** C-1.3
- **pins:** 9248a91981f5261a
- **run_cmd:** `python -m pytest tests/test_tdd_issue_questions.py::test_nonblocking_question_requires_specific_public_evidence_without_erasing_history tests/test_tdd_issue_questions.py -q`
- **Given** an issue passport containing unspecified examples or genuine ambiguities
- **When** generation proceeds and fresh review evaluates each question
- **Then** public evidence is checked and missing or unresolved answers cannot release a candidate.

### S2.1 - Repair without replacing history or reusing reviews
- **verifies:** C-2.1
- **pins:** d9eacc727efe23ee
- **run_cmd:** `python -m pytest tests/test_tdd_cycle.py::test_cycle_repairs_with_fresh_review_preserves_history_and_releases_exact_patch tests/test_tdd_cycle.py -q`
- **Given** a rejected candidate and remaining reserved resources
- **When** a revised candidate is proposed
- **Then** attempts remain immutable and changed content receives fresh review.

### S2.2 - Exclude evaluator feedback from repairs
- **verifies:** C-2.2
- **pins:** 31be79d603d980fc
- **run_cmd:** `python -m pytest tests/test_tdd_cycle_privacy.py::test_repair_feedback_excludes_nonpublic_top_level_fields tests/test_tdd_cycle_privacy.py -q`
- **Given** public/native evidence and separately sealed evaluator data
- **When** a repair context is composed
- **Then** evaluator information is absent from model inputs.

### S3.1 - Retain meaningful declared diversity and execution rules
- **verifies:** C-3.1
- **pins:** 3e2118d99e220a23
- **run_cmd:** `python -m pytest tests/test_tdd_semantic_controls.py::test_structurally_unchanged_and_duplicate_controls_cannot_supply_diversity tests/test_tdd_semantic_controls.py -q`
- **Given** declared valid alternatives and a semantic violation
- **When** contrastive controls are inspected and executed
- **Then** structurally unchanged variants do not supply diversity and execution errors remain inconclusive.

### S3.2 - Challenge overstrict oracle assumptions with extracted real-study risks
- **verifies:** C-3.2
- **pins:** 25cc82a6f8105880
- **run_cmd:** `python -m pytest tests/test_semantic_scope_regressions.py::test_semantic_oracles_accept_declared_freedom_and_detect_real_violations -q`
- **Given** minimal reproductions of equivalent mechanisms, warning guidance and unrelated diagnostic files
- **When** actual native spec-trust subprocesses execute corrected and deliberately overstrict oracles
- **Then** corrected oracles accept declared valid alternatives and detect activated violations while overstrict oracles falsely reject the alternatives.

### S3.3 - Keep private helper choices outside a public behavior oracle
- **verifies:** C-3.3
- **pins:** 338eb332a54e4229
- **run_cmd:** `python -m pytest tests/test_semantic_scope_regressions.py::test_public_collection_accepts_a_different_private_helper_boundary -q`
- **Given** a finite inherited-marker fixture with collector-level and helper-level implementations
- **When** native spec-trust commands challenge public and deliberately helper-specific oracles
- **Then** the public oracle accepts both implementations and catches an activated missing inherited marker, while the private oracle falsely rejects the collector-level alternative.

### S4.1 - Preserve a charged budget across crashes and phases
- **verifies:** C-4.1
- **pins:** 5bc391457964c1bf
- **run_cmd:** `python -m pytest tests/test_tdd_lineage.py::test_reservations_block_generation_before_it_spends_review_or_repair tests/test_tdd_lineage.py -q`
- **Given** one case journal and reserved review/repair resources
- **When** calls fail, a process exits abruptly or another writer advances the journal
- **Then** charges persist and protected work cannot be spent by generation.

### S4.2 - Reserve complete audit and repair costs
- **verifies:** C-4.2
- **pins:** cbbc652bb1151993
- **run_cmd:** `python -m pytest tests/test_tdd_lineage.py::test_audit_forecast_reserves_full_bindings_and_repair_instead_of_narrowing tests/test_tdd_lineage.py::test_planner_refuses_missing_or_invalid_scope -q`
- **Given** all commands bound to the live clauses
- **When** current audit and future repair resources are forecast
- **Then** exact complete costs expose shortfalls without narrower scope.

### S4.3 - Report charged attempts and unknown usage honestly
- **verifies:** C-4.3
- **pins:** 27341b552d4e4474
- **run_cmd:** `python -m pytest tests/test_tdd_lineage.py::test_missing_usage_is_not_zero_and_observed_zero_stays_zero tests/test_tdd_lineage.py::test_failures_survive_reopen_and_never_refund_or_leak_messages tests/test_tdd_lineage.py::test_reservations_block_generation_before_it_spends_review_or_repair -q`
- **Given** successful, errored and denied requests with partial usage
- **When** the journal reports its evidence
- **Then** missing usage is explicit and errors neither refund charges nor reveal exception text.

### S5.1 - Freeze fresh study inputs
- **verifies:** C-5.1
- **pins:** 46bdf590461a19f6
- **run_cmd:** `python -m pytest tests/test_tdd_cycle_assessment.py::test_fresh_partitions_and_immutable_execution_are_required_before_inference tests/test_tdd_cycle_assessment.py -q`
- **Given** prior IDs and a candidate dataset
- **When** a new study is frozen
- **Then** partitions are disjoint and execution cannot precede immutable bindings.

### S5.2 - Report every outcome without hidden selection
- **verifies:** C-5.2
- **pins:** 9f4bfec3db8db72d
- **run_cmd:** `python -m pytest tests/test_tdd_cycle_assessment.py::test_sealed_selection_and_missing_grades_never_become_best_of_n_or_success tests/test_tdd_cycle_assessment.py -q`
- **Given** released, rejected and incomplete candidate histories
- **When** independent results are collected after generation
- **Then** full denominators, outcome matrices, repairs and resource histories remain visible.
