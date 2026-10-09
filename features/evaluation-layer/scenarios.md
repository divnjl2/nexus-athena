# Scenarios: Athena Evaluation Foundation

### S5.10 — exact cluster trace bytes
- **verifies:** C-5.10
- **pins:** b695330d29610a40
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_pilot.py::test_cluster_candidate_is_unpriced_and_only_official_gate_accepts_it -q`
- **Given** a cluster candidate whose trace and stderr are preserved
- **When** line endings or diagnostic bytes change without changing parsed events
- **Then** the candidate fails provenance checks before its independent gate.

### S5.11 — cluster time includes official gate
- **verifies:** C-5.11
- **pins:** 644d6dff9f6ca694
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_pilot.py::test_cluster_candidate_is_unpriced_and_only_official_gate_accepts_it -q`
- **Given** a cluster candidate and an official gate verdict
- **When** a graded or partial cluster report is built
- **Then** gate time is bound to the record and partial attempts leave total
  time unknown with only a measured lower bound.

### S5.9 — fail-closed cluster continuation
- **verifies:** C-5.9
- **pins:** 503941c35a58bafa
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_batch.py -q`
- **Given** an interrupted cluster candidate or an unfinished official gate
- **When** the paired development batch resumes
- **Then** it records the partial state and stops before launching another
  model attempt or accepting a result without independent evidence.

### S5.8 — honest cluster report
- **verifies:** C-5.8
- **pins:** 5faf7d8590a9ccff
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_pilot.py::test_cluster_candidate_is_unpriced_and_only_official_gate_accepts_it -q`
- **Given** one graded cluster attempt and one interrupted attempt
- **When** the separate cluster report is built
- **Then** it revalidates the official record, lists the missing and ungraded
  cells, withholds paired inference, and leaves USD cost unknown.

### S5.6 — isolated and unpriced cluster candidate
- **verifies:** C-5.6
- **pins:** 1167f673e3b2da65
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_pilot.py::test_cluster_provider_is_loopback_and_key_stays_out_of_argv tests/test_self_improve_cluster_pilot.py::test_cluster_candidate_is_unpriced_and_only_official_gate_accepts_it -q`
- **Given** a recent passed tool-loop probe and a private bridge key
- **When** a cluster candidate runs in its own worktree
- **Then** its invocation uses only the loopback provider and preserves inputs,
  trace and patch as unverified evidence with no invented dollar price.

### S5.7 — independent cluster gate
- **verifies:** C-5.7
- **pins:** bf140793a31c3d5c
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_pilot.py::test_cluster_candidate_is_unpriced_and_only_official_gate_accepts_it -q`
- **Given** a preserved cluster candidate
- **When** its independent gate is run
- **Then** changed prompt or patch bytes are refused and the official report
  is bound to a cluster-specific record.

### S5.5 — plain text Responses input
- **verifies:** C-5.5
- **pins:** 114d139c0004633d
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_bridge.py::test_bridge_passes_plain_text_responses_input -q`
- **Given** a streamed Responses request with string input
- **When** it crosses the bridge
- **Then** the text and all other fields remain unchanged.

### S5.4 — private bridge pod
- **verifies:** C-5.4
- **pins:** 9d472fb9d496bc92
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_bridge.py::test_pod_manifest_uses_secret_refs_and_no_service_exposure -q`
- **Given** a namespace, upstream URL and pre-existing Secret name
- **When** the bridge pod manifest is rendered
- **Then** the code is mounted from a ConfigMap, both credentials are read from
  Secret keys, and no Service exposes the bridge.

### S5.2 — authenticated loopback stream
- **verifies:** C-5.2
- **pins:** bec492b8fbfe8b17
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_bridge.py::test_bridge_authenticates_and_preserves_sse_bytes -q`
- **Given** separate local client and upstream credentials
- **When** a streamed Codex request crosses the bridge
- **Then** unauthenticated callers are refused and the authenticated SSE bytes
  reach the client using only the upstream credential on the gateway request.

### S5.3 — safe developer role adaptation
- **verifies:** C-5.3
- **pins:** 541aceb5d3ee3b09
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_bridge.py::test_bridge_keeps_instruction_text_and_rejects_late_developer -q`
- **Given** a streamed Responses request with developer instructions
- **When** the bridge adapts it for the selected Qwen route
- **Then** all leading text is preserved, while late or non-text developer
  content is rejected.

### S5.1 — cluster route requires a complete tool loop
- **verifies:** C-5.1
- **pins:** 5279fec8b3cf482d
- **run_cmd:** `python -m pytest tests/test_self_improve_cluster_probe.py -q`
- **Given** a cluster gateway URL and a credential supplied outside the repository
- **When** the route is probed for an agent benchmark
- **Then** only a completed SSE exchange, a function call and its successful
  follow-up qualify the route, without exposing the credential.

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

### S2.9 — account for ungraded attempts
- **verifies:** C-2.9
- **pins:** 4eb3e212f530e040
- **run_cmd:** `python -m pytest tests/test_self_improve_evidence.py::test_report_prices_ungated_attempts_only_from_complete_candidate_evidence tests/test_self_improve_evidence.py::test_report_counts_executor_error_with_completed_usage tests/test_self_improve_baseline_batch.py::test_partial_baseline_artifacts_are_reported_before_resume_stops -q`
- **Given** a priced candidate that never reached an independent gate
- **When** the baseline report is produced or a batch resumes
- **Then** validated usage is charged, incomplete cost is unknown, and the
  attempt remains visible without completing the comparison.

### S2.10 — time includes the independent gate
- **verifies:** C-2.10
- **pins:** 0de767d8110aaa1f
- **run_cmd:** `python -m pytest tests/test_self_improve_gate_adapter.py::test_harness_reads_a_local_pinned_task_snapshot_and_its_v5_report tests/test_self_improve_evidence.py::test_attempt_rejects_gate_time_omitted_from_total tests/test_self_improve_evidence.py::test_report_prices_ungated_attempts_only_from_complete_candidate_evidence -q`
- **Given** a candidate and an official SWE-bench gate
- **When** their times are reported
- **Then** gate duration is bound to the envelope and included in total time,
  while an unfinished gate leaves total time unknown.

### S2.8 — revalidate every baseline evidence leg
- **verifies:** C-2.8
- **pins:** a5670c08858f679e
- **run_cmd:** `python -m pytest tests/test_self_improve_evidence.py -q`
- **Given** an official gate record with preserved candidate artifacts
- **When** an input, patch, invocation, trace, estimate or dataset changes
- **Then** loading the attempt fails before it can enter a benchmark report.

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

### S3.9 — native Windows sandbox pinned
- **verifies:** C-3.9
- **pins:** 4380d6880bf6a226
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_windows_candidate_pins_the_native_elevated_workspace_sandbox -q`
- **Given** a Windows Codex invocation with user configuration ignored
- **When** the task command is built
- **Then** it explicitly pins the elevated native sandbox with workspace-write.

### S3.10 — bounded context and cache-write price
- **verifies:** C-3.10
- **pins:** 316d3e2e8430bb00
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_completed_codex_turns_account_for_cached_and_output_tokens tests/test_self_improve_codex_driver.py::test_windows_candidate_pins_the_native_elevated_workspace_sandbox -q`
- **Given** a dated price card and completed Codex usage
- **When** a request is configured and priced
- **Then** the context limit and cache-write rate are bound to the estimate.

### S3.11 — generated caches excluded
- **verifies:** C-3.11
- **pins:** 88eed663dadf9010
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_candidate_patch_contains_untracked_files_without_a_gate_verdict -q`
- **Given** source edits and nested generated caches
- **When** a patch is captured
- **Then** source edits remain and generated `.athena` caches are omitted.

### S3.12 — recoverable tool denial
- **verifies:** C-3.12
- **pins:** 9dfb6d99410c7f88
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_executor_failures_cannot_be_scored_as_empty_agent_patches tests/test_self_improve_pilot.py::test_official_gate_creates_one_valid_immutable_attempt_record -q`
- **Given** a completed turn with a patch and one denied tool call
- **When** the candidate is classified
- **Then** the gate may judge it while fatal executor errors remain excluded.

### S3.14 — exact prompt bytes
- **verifies:** C-3.14
- **pins:** a016a6ab4856dfb5
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_candidate_prompt_hash_matches_saved_and_submitted_bytes tests/test_self_improve_evidence.py::test_attempt_rejects_prompt_bytes_that_differ_from_record -q`
- **Given** a multiline candidate prompt on Windows
- **When** the runner sends it or an attempt record is loaded
- **Then** saved, submitted and fingerprinted bytes agree, and newline
  conversion invalidates the attempt.

### S3.15 — streamed trace survives timeout
- **verifies:** C-3.15
- **pins:** 92d2d4df0b3b5d67
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_timed_out_candidate_keeps_streamed_trace_and_fails_closed -q`
- **Given** a Codex process that emits partial trace and diagnostic bytes
- **When** the candidate times out
- **Then** those bytes remain in artifacts and the candidate is an executor error.

### S3.16 — exact baseline trace bytes
- **verifies:** C-3.16
- **pins:** b5ca872906d415e9
- **run_cmd:** `python -m pytest tests/test_self_improve_codex_driver.py::test_candidate_prompt_hash_matches_saved_and_submitted_bytes tests/test_self_improve_evidence.py::test_attempt_rejects_semantically_identical_trace_with_changed_bytes tests/test_self_improve_pilot.py::test_official_gate_creates_one_valid_immutable_attempt_record -q`
- **Given** a candidate trace, stderr and an independent acceptance gate
- **When** trace line endings or diagnostic bytes are changed
- **Then** their saved fingerprints reject the attempt before grading or reporting.

### S3.13 — resume without duplicate attempts
- **verifies:** C-3.13
- **pins:** 3c0cebbdefe1e338
- **run_cmd:** `python -m pytest tests/test_self_improve_baseline_batch.py -q`
- **Given** a partial baseline batch
- **When** the batch resumes
- **Then** proved cells are skipped, complete candidates proceed to the gate,
  and incomplete candidates or gates require review.

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

### S4.9 — Unicode WSL path round trip
- **verifies:** C-4.8
- **pins:** 19a5118f74325fd4
- **run_cmd:** `python -m pytest tests/test_self_improve_gate_adapter.py::test_wsl_path_preserves_non_ascii_workspace_names -q`
- **Given** a Windows task path with Cyrillic components
- **When** the path is mapped into Ubuntu WSL
- **Then** the Linux process can access that exact directory.
