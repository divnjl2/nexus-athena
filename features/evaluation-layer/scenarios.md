# Scenarios: Athena Evaluation Foundation

### S1.4 — stable Verified selection
- **verifies:** C-1.4
- **pins:** 45cd81e0c8b0cfd0
- **run_cmd:** `python -m pytest tests/test_self_improve_corpus.py::test_stratified_corpus_has_40_real_task_slots_and_separate_holdout -q`
- **Given** a source with ten eligible repositories and at least four tasks each
- **When** the corpus is selected
- **Then** each repository contributes three development tasks and one holdout task.

### S1.2 — fingerprinted inputs and acceptance
- **verifies:** C-1.2
- **pins:** ec00ab0724938b98
- **run_cmd:** `python -m pytest tests/test_self_improve_corpus.py::test_pinned_corpus_rejects_changed_inputs_and_acceptance -q`
- **Given** a frozen manifest
- **When** an input, base commit or acceptance artifact changes
- **Then** verification fails.

### S1.5 — incomplete Verified source refused
- **verifies:** C-1.5
- **pins:** 63c9996205014b58
- **run_cmd:** `python -m pytest tests/test_self_improve_corpus.py::test_corpus_fails_closed_on_insufficient_repository_diversity -q`
- **Given** fewer than ten eligible repositories
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

### S2.4 — two-arm baseline before optimizer
- **verifies:** C-2.4
- **pins:** 8d8a52abf9251a2c
- **run_cmd:** `python -m pytest tests/test_self_improve_evidence.py::test_baseline_precedes_optimizer_and_requires_both_original_arms -q`
- **Given** every task was run with ordinary Codex and Codex plus Athena
- **When** baseline and final reports are calculated
- **Then** only the baseline is complete.

### S2.5 — paired difference and failures
- **verifies:** C-2.5
- **pins:** d2cc53f01443a234
- **run_cmd:** `python -m pytest tests/test_self_improve_evidence.py::test_paired_report_counts_discordant_tasks_and_failure_reasons -q`
- **Given** matched tasks with one gain and one regression
- **When** baseline is summarized
- **Then** both discordant directions, an interval and failure causes are shown.

### S2.7 — shrunken Verified corpus refused
- **verifies:** C-2.7
- **pins:** 7988f7797b48a34c
- **run_cmd:** `python -m pytest tests/test_self_improve_evidence.py::test_empty_or_shrunken_manifest_cannot_claim_a_complete_pilot -q`
- **Given** an empty replacement manifest
- **When** completeness is calculated
- **Then** reporting fails.

### S3.1 — baseline planned before optimizer
- **verifies:** C-3.1
- **pins:** 4958de38b73df3b3
- **run_cmd:** `python -m pytest tests/test_self_improve_workspaces.py::test_stage_plans_original_arms_before_optimizer -q`
- **Given** a frozen task set
- **When** baseline or optimizer cells are planned
- **Then** the two stages contain their respective fixed configurations.

### S3.2 — fresh pinned worktree
- **verifies:** C-3.2
- **pins:** c5f6c954fd07503d
- **run_cmd:** `python -m pytest tests/test_self_improve_workspaces.py::test_worktree_is_fresh_and_pinned_to_the_source_commit -q`
- **Given** a task base commit
- **When** two attempts are prepared
- **Then** each has a fresh worktree at that commit.

### S3.3 — safe workspace identifiers
- **verifies:** C-3.3
- **pins:** 6d50d921f1f68d24
- **run_cmd:** `python -m pytest tests/test_self_improve_workspaces.py::test_workspace_paths_reject_untrusted_identifiers -q`
- **Given** an unsafe task identifier
- **When** workspace paths are constructed
- **Then** path creation is refused.

### S3.4 — Codex usage from completed turns
- **verifies:** C-3.4
- **pins:** e4fa23f17e9d7196
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_completed_codex_turns_account_for_cached_and_output_tokens -q`
- **Given** a Codex JSONL trace
- **When** token usage is counted
- **Then** only completed turns contribute and missing usage is refused.

### S3.5 — full candidate patch
- **verifies:** C-3.5
- **pins:** beb162706c41ab87
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_candidate_patch_contains_untracked_files_without_a_gate_verdict -q`
- **Given** tracked and untracked edits
- **When** the candidate is captured
- **Then** both are present in the patch.

### S3.6 — common input and arm isolation
- **verifies:** C-3.6
- **pins:** a998fa2c6a8dc828
- **run_cmd:** `python -m pytest tests/test_self_improve_pilot.py::test_prompts_expose_only_issue_inputs_and_keep_optimizer_out_of_baselines -q`
- **Given** one issue with private acceptance material
- **When** prompts for all arms are built
- **Then** they receive the same issue while acceptance material stays out.

### S3.7 — frozen promotion before holdout
- **verifies:** C-3.7
- **pins:** 01c015fd6451bc4c
- **run_cmd:** `python -m pytest tests/test_self_improve_pilot.py::test_optimizer_holdout_requires_matching_frozen_instructions_and_evidence -q`
- **Given** an optimizer candidate
- **When** a holdout run is requested
- **Then** matching complete baseline and development reports are required.

### S3.8 — executor errors stay out of task quality scores
- **verifies:** C-3.8
- **pins:** 433a01132aabd821
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_executor_failures_cannot_be_scored_as_empty_agent_patches tests/test_self_improve_pilot.py::test_official_gate_creates_one_valid_immutable_attempt_record -q`
- **Given** a Codex trace with a tool policy, process or turn failure
- **When** a candidate is classified and submitted for grading
- **Then** the attempt is marked as an executor error and cannot enter the official task matrix.

### S3.9 — native Windows sandbox pinned
- **verifies:** C-3.9
- **pins:** 4380d6880bf6a226
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_windows_candidate_pins_the_native_elevated_workspace_sandbox -q`
- **Given** a Windows Codex invocation with user configuration ignored
- **When** the task command is built
- **Then** it explicitly pins the elevated native sandbox with workspace-write.

### S4.2 — unique prediction and run id
- **verifies:** C-4.2
- **pins:** c1b0f1a81cea3f71
- **run_cmd:** `python -m pytest tests/test_self_improve_gate_adapter.py::test_prediction_and_run_id_bind_exact_patch_and_attempt -q`
- **Given** a task patch and attempt
- **When** a prediction and run id are formed
- **Then** changing the patch or attempt changes the run identity.

### S4.3 — unchanged official report bound to patch
- **verifies:** C-4.3
- **pins:** 031ca1911ac30a2e
- **run_cmd:** `python -m pytest tests/test_self_improve_gate_adapter.py::test_gate_envelope_preserves_official_report_and_patch_hash -q`
- **Given** an official harness report
- **When** a gate envelope is written
- **Then** its copy is byte-identical and its patch hash matches.

### S4.4 — altered official evidence refused
- **verifies:** C-4.4
- **pins:** 659da23f2fdec25a
- **run_cmd:** `python -m pytest tests/test_self_improve_evidence.py::test_attempt_rejects_changed_official_report_even_if_gate_envelope_is_intact -q`
- **Given** a previously validated attempt
- **When** the official report changes
- **Then** the attempt no longer validates.

### S4.5 — independent gate before record
- **verifies:** C-4.5
- **pins:** 128ac47a3504b741
- **run_cmd:** `python -m pytest tests/test_self_improve_pilot.py::test_official_gate_creates_one_valid_immutable_attempt_record -q`
- **Given** a candidate patch and pinned source row
- **When** the official gate returns a report
- **Then** one validated attempt record is created and cannot be overwritten.

### S4.6 — pinned local task snapshot
- **verifies:** C-4.6
- **pins:** 68160e61f974a4d3
- **run_cmd:** `python -m pytest tests/test_self_improve_gate_adapter.py::test_harness_reads_a_local_pinned_task_snapshot_and_its_v5_report -q`
- **Given** a pinned task row and the compatible harness
- **When** the independent gate is invoked
- **Then** it reads a local snapshot and the expected version's per-instance report.

### S4.7 — official verdict shapes
- **verifies:** C-4.7
- **pins:** 94199369ad4d69c9
- **run_cmd:** `python -m pytest tests/test_self_improve_gate_adapter.py::test_official_report_shape_is_required -q`
- **Given** an official per-instance report or single-task empty-patch summary
- **When** its verdict is read
- **Then** a task-bound boolean is returned only for a supported shape.

### S4.8 — empty patch is measured
- **verifies:** C-4.7
- **pins:** 94199369ad4d69c9
- **run_cmd:** `python -m pytest tests/test_self_improve_gate_adapter.py::test_empty_patch_is_bound_to_official_v5_results -q`
- **Given** an agent attempt with no patch
- **When** the official v5 harness reports it as empty
- **Then** the task is recorded as unresolved with that report preserved.
