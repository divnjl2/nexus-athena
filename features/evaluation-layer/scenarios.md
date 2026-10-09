# Scenarios: Athena Evaluation Foundation

### S1.1 — stable stratified selection
- **verifies:** C-1.1
- **pins:** 39a7c9ac0440f2fc
- **run_cmd:** `python -m pytest tests/test_self_improve_corpus.py::test_stratified_corpus_has_36_real_task_slots_and_separate_holdout -q`
- **Given** a source with 12 repositories and at least three tasks each
- **When** the corpus is selected
- **Then** each repository contributes two development tasks and one holdout task.

### S1.2 — fingerprinted inputs and acceptance
- **verifies:** C-1.2
- **pins:** ec00ab0724938b98
- **run_cmd:** `python -m pytest tests/test_self_improve_corpus.py::test_pinned_corpus_rejects_changed_inputs_and_acceptance -q`
- **Given** a frozen manifest
- **When** an input, base commit or acceptance artifact changes
- **Then** verification fails.

### S1.3 — incomplete source refused
- **verifies:** C-1.3
- **pins:** ffcf53085ecec985
- **run_cmd:** `python -m pytest tests/test_self_improve_corpus.py::test_corpus_fails_closed_on_insufficient_repository_diversity -q`
- **Given** fewer than 12 eligible repositories
- **When** the corpus is selected
- **Then** selection fails.

### S2.1 — run provenance and gate artifact
- **verifies:** C-2.1
- **pins:** 7e00d7d4c26e89cd
- **run_cmd:** `python -m pytest tests/test_self_improve_evidence.py::test_attempt_requires_pinned_provenance_and_matching_gate_artifact -q`
- **Given** a run record with a gate artifact
- **When** either its provenance or artifact changes
- **Then** loading the attempt fails.

### S2.2 — full cost and missing cells
- **verifies:** C-2.2
- **pins:** c5c3fb2d3d0b425b
- **run_cmd:** `python -m pytest tests/test_self_improve_evidence.py::test_report_refuses_missing_arms_and_charges_failed_attempts -q`
- **Given** one failed and one successful attempt
- **When** a matrix is summarized
- **Then** both attempts count toward cost and missing cells are exposed.

### S2.3 — complete three-arm matrix
- **verifies:** C-2.3
- **pins:** a75910948b86c287
- **run_cmd:** `python -m pytest tests/test_self_improve_evidence.py::test_report_is_complete_only_with_all_three_arms_on_every_task -q`
- **Given** the frozen task set
- **When** every task has evidence for every arm
- **Then** the matrix is complete.
