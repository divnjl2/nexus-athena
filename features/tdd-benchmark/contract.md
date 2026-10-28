# Contract: TDD benchmark adapter

> Run TDD-Bench-Verified separately from the planner's SWE-bench Lite proxy. Calibration
> with gold tests is infrastructure evidence, never an Athena/model performance result.

## C-1 — Frozen inputs and a blind generator
- **C-1.1** — WHEN a TDD dataset is prepared THE SYSTEM SHALL accept only instance ids in the upstream TDD membership list.
  - source: design
- **C-1.2** — WHEN inputs are exported to a generator THE SYSTEM SHALL expose only instance identity, repository, base revision and issue text.
  - source: design
- **C-1.3** — WHEN a calibration subset is selected THE SYSTEM SHALL freeze a deterministic set of distinct instance ids before evaluation.
  - source: design
- **C-1.4** — WHEN a dataset or membership file is missing or inconsistent THE SYSTEM SHALL refuse to substitute another benchmark or offline fixtures.
  - source: design
- **C-1.5** — WHEN benchmark artifacts are prepared THE SYSTEM SHALL record hashes of the dataset, membership list and harness archive.
  - source: design

## C-2 — An actual external gate
- **C-2.1** — WHEN a harness command is prepared THE SYSTEM SHALL require an explicit Git authorization flag before allowing execution.
  - source: design
- **C-2.2** — WHEN an upstream report is missing or contains test execution errors THE SYSTEM SHALL report INCOMPLETE.
  - source: design
- **C-2.3** — WHEN fail-before/pass-after is evaluated THE SYSTEM SHALL require a failing old-code test with the same test passing after the fix.
  - source: design
- **C-2.4** — WHEN a benchmark summary is emitted THE SYSTEM SHALL retain selected, evaluated, failed and incomplete denominators.
  - source: design
- **C-2.5** — WHEN gold predictions are evaluated THE SYSTEM SHALL label the result as calibration rather than model performance.
  - source: design

## C-3 — Model evaluation entrypoint
- **C-3.1** — WHEN model predictions are submitted THE SYSTEM SHALL validate their JSON or JSONL rows against the frozen cohort and mount only a file inside the benchmark directory.
  - source: design
- **C-3.2** — WHEN evaluation mode is requested from the CLI THE SYSTEM SHALL use the thirty-task evaluation cohort for both execution and reporting while retaining unrun tasks as INCOMPLETE.
  - source: design

## C-4 — Public base-code workspace
- **C-4.1** — WHEN a generator workspace is exported THE SYSTEM SHALL obtain source files at the public base revision without repository history and record the archive and input fingerprints.
  - see: ../../docs/adr/0011-blind-benchmark-workspaces.md@d0e54d792107cba6
  - source: design
- **C-4.2** — WHEN a workspace input contains sealed fields or an unselected instance THE SYSTEM SHALL reject it before contacting the source server.
  - source: design
- **C-4.3** *(superseded-by C-4.7)* — WHEN a source archive contains traversal, links, history, ambiguous paths or multiple roots THE SYSTEM SHALL reject it without leaving a partial generator workspace.
  - source: design
- **C-4.4** — WHEN a generator code tool is launched THE SYSTEM SHALL mount only the verified public workspace read-only and an empty separate output directory, with networking and Docker socket access unavailable.
  - see: ../../docs/adr/0011-blind-benchmark-workspaces.md@d0e54d792107cba6
  - source: design
- **C-4.5** — WHEN the exported issue text changes THE SYSTEM SHALL reject the workspace before preparing a generator sandbox.
  - source: design
- **C-4.7** *(supersedes C-4.3)* — WHEN a source archive contains traversal, escaping or cyclic links, history, ambiguous paths or multiple roots THE SYSTEM SHALL reject it without leaving a partial generator workspace.
  - source: incident
- **C-4.8** — WHEN public source contains contained symlinks or executable files THE SYSTEM SHALL record their filesystem metadata without creating host symlinks and expose links as explicit metadata to the source reader.
  - see: ../../docs/adr/0016-portable-posix-snapshots.md@f113930b783a3a6f
  - source: incident

## C-5 — Auditable direct generation
- **C-5.1** — WHEN the direct generator reads code THE SYSTEM SHALL supply only the verified public issue and selected source file contents while retaining the complete transcript and candidate fingerprint.
  - see: ../../docs/adr/0012-auditable-direct-generation.md@fbbbe7cd6d24ad74
  - source: design
- **C-5.2** — WHEN a model requests a nonpublic path THE SYSTEM SHALL deny the read and count the attempted turn against the fixed call budget without hidden retries.
  - source: design
- **C-5.3** — WHEN model output is truncated, transport fails or the context budget is exhausted THE SYSTEM SHALL preserve an INCOMPLETE receipt without producing a candidate prediction or exposing exception credentials.
  - see: ../../docs/adr/0012-auditable-direct-generation.md@fbbbe7cd6d24ad74
  - source: design
- **C-5.4** — WHEN a chat-completions endpoint is used THE SYSTEM SHALL require an explicit endpoint and model, record returned usage and obtain authorization only from the named environment variable.
  - source: design
- **C-5.5** — WHEN the generation CLI is invoked without execution requested THE SYSTEM SHALL validate public inputs without contacting a model or creating output artifacts.
  - source: design

## C-6 — Offline execution during generation
- **C-6.1** *(superseded-by C-6.10)* — WHEN a dependency runtime is prepared THE SYSTEM SHALL accept only an inspected environment-only image, pin its immutable identity and bind it to the selected public snapshot.
  - see: ../../docs/adr/0013-public-dependency-runtimes.md@57cf2a163cb756b4
  - source: design
- **C-6.2** *(superseded-by C-6.6)* — WHEN a candidate is run during generation THE SYSTEM SHALL restrict overlays to test files and execute them in a fresh offline copy without exposing evaluator mounts or host commands to the model.
  - source: design
- **C-6.3** — WHEN a candidate test run completes THE SYSTEM SHALL distinguish assertion failure from import, skip, missing-report and runner errors and label the result as diagnostic only.
  - see: ../../docs/adr/0013-public-dependency-runtimes.md@57cf2a163cb756b4
  - source: design
- **C-6.4** — WHEN a candidate test tool times out THE SYSTEM SHALL remove only its named container and retain a timeout diagnostic rather than an assertion witness.
  - source: design
- **C-6.5** — WHEN generation has an offline test tool THE SYSTEM SHALL enforce a separate test-run budget, record the runtime fingerprint and return only tool diagnostics to the model.
  - source: design
- **C-6.6** *(supersedes C-6.2)* — WHEN a candidate is run during generation THE SYSTEM SHALL restrict test overlays to test files and optional implementation proposals to known public Python implementation, executing both in a fresh offline copy without exposing evaluator mounts or host commands.
  - source: design
- **C-6.7** — WHEN public source is copied into the offline Linux runtime THE SYSTEM SHALL restore its declared symlink identities and executable modes before pytest and refuse overlays through source links.
  - see: ../../docs/adr/0016-portable-posix-snapshots.md@f113930b783a3a6f
  - source: incident

## C-7 — Native Athena baseline without hidden solutions
- **C-7.1** — WHEN the Athena generation arm accepts a proposal THE SYSTEM SHALL run the actual contract, scenario, ledger and check modules and retain the scoped native evidence with framework fingerprints.
  - see: ../../docs/adr/0014-native-regression-baselines.md@2ed9793b7e75cf71
  - source: design
- **C-7.2** — WHEN a proposed regression spec needs a passing baseline THE SYSTEM SHALL use only the agent's public reference proposal and export only test changes to the independent evaluator.
  - see: ../../docs/adr/0014-native-regression-baselines.md@2ed9793b7e75cf71
  - source: design
- **C-7.3** — WHEN a native proposal requests execution THE SYSTEM SHALL reject missing references, source escapes and commands outside the bounded pytest interface before execution.
  - source: design
- **C-7.4** — WHEN native baseline execution fails or exhausts its budget THE SYSTEM SHALL distinguish FAIL from INCOMPLETE and charge all executions to the same per-arm test budget.
  - source: design

## C-8 — Frozen independent review and native trust
- **C-8.1** — WHEN the trust generation arm completes its native baseline THE SYSTEM SHALL freeze the candidate and native artifacts before review without publishing an evaluator prediction.
  - see: ../../docs/adr/0015-frozen-review-and-contrastive-activation.md@f0bfe50bc66f6f6e
  - source: design
- **C-8.2** — WHEN a frozen candidate is reviewed THE SYSTEM SHALL use a separate public-only context and charge the reviewer call to the original total model budget.
  - source: design
- **C-8.3** — WHEN a candidate trust audit runs THE SYSTEM SHALL execute the native spec-trust audit with separately isolated activation and candidate tests, covering every live clause and its bound specs.
  - see: ../../docs/adr/0015-frozen-review-and-contrastive-activation.md@f0bfe50bc66f6f6e
  - source: design
- **C-8.4** — WHEN review evidence is missing, stale, incomplete or beyond the shared budget THE SYSTEM SHALL retain INCOMPLETE and publish no evaluator prediction.
  - source: design
- **C-8.5** — WHEN a spec accepts an activated violation or rejects a declared valid alternative THE SYSTEM SHALL reject it through the native trust policy.
  - source: design
- **C-8.6** — WHEN review or trust commands are invoked without execution requested THE SYSTEM SHALL validate the candidate without model calls, container execution or output creation.
  - source: design

## Additional runtime evidence
- **C-6.8** — WHEN a selected project is tested THE SYSTEM SHALL prioritize its public src, lib and root layouts, require its declared module origin inside the copied source and classify an external origin as TOOL_ERROR regardless of successful JUnit evidence.
  - see: ../../docs/adr/0017-public-source-import-origin.md@1604bf34cb8f5147
  - source: incident
- **C-6.9** — WHEN an inspected execution runtime is available THE SYSTEM SHALL expose its Python version in generation context and retain it in the generation receipt for subsequent independent review.
  - see: ../../docs/adr/0017-public-source-import-origin.md@1604bf34cb8f5147
  - source: incident

## Test-only evaluator submissions
- **C-5.6** — WHEN any generation mode publishes a prediction THE SYSTEM SHALL validate every patch path and hunk against the verified public base, reject non-test or unsupported changes and emit only a canonical test patch without modifying public files.
  - see: ../../docs/adr/0018-test-only-prediction-patches.md@4893cf557283f9ef
  - source: design

## Public-installed project runtimes
- **C-6.10** *(supersedes C-6.1)* — WHEN a dependency runtime is prepared THE SYSTEM SHALL admit only an inspected upstream environment-only image or explicitly typed public-installed derivative, pin its immutable identity and bind it to the selected public snapshot while rejecting raw task images.
  - see: ../../docs/adr/0019-public-installed-runtimes.md@a3fbd5ecb3db0c82
  - source: incident
- **C-6.11** — WHEN a public-installed runtime is admitted THE SYSTEM SHALL require matching instance and snapshot labels, verify the known public source bytes and links inside the image, reject Git history and task setup scripts, and retain complete inspection evidence in a separate runtime schema.
  - see: ../../docs/adr/0019-public-installed-runtimes.md@a3fbd5ecb3db0c82
  - source: incident

## Public installation outputs
- **C-6.12** — WHEN an inspected public-installed runtime supplies generated or compiled outputs THE SYSTEM SHALL fingerprint their separate bounded inventory, recheck bytes and link targets while restoring them before model overlays, and refuse source replacement, link traversal, stale inventories or changed outputs before pytest.
  - see: ../../docs/adr/0020-public-build-artifact-restoration.md@dd0c1fcd768aac48
  - source: incident

## Unicode filesystem paths
- **C-6.13** — WHEN a runtime is inspected or a public code tool executes THE SYSTEM SHALL set an explicit UTF-8 locale and reject newly inspected runtimes that report a non-UTF-8 filesystem encoding so public Unicode filenames remain usable on Python 3.6.
  - see: ../../docs/adr/0021-runtime-unicode-filesystem-locale.md@3f7ae722ac3b126e
  - source: incident

## Image-resident public source staging
- **C-6.14** — WHEN a public-installed runtime executes tests THE SYSTEM SHALL stage only declared source files from its immutable public tree into a fresh workspace, recheck their hashes and link targets before overlays, and select the staging mode from the bound runtime rather than model input.
  - see: ../../docs/adr/0022-stage-verified-public-source-inside-runtime.md@afe504ec3527913c
  - source: incident

## Git-compatible new-file predictions
- **C-5.7** — WHEN a prediction adds a test file THE SYSTEM SHALL emit explicit Git creation mode metadata, normalize legacy missing-mode inputs through the same exporter, and omit creation metadata for ordinary existing-file edits.
  - see: ../../docs/adr/0023-git-new-file-patch-metadata.md@9cf09e7cbfbd20c2
  - source: incident

## Review inputs from real model-study incidents
- **C-8.7** — WHEN preparing independent review THE SYSTEM SHALL encode every validated base and proposed-reference file as a lossless ndiff line array, remove redundant reference copies, preserve candidate intent and test inputs, and enforce the original context budget without truncation.
  - see: ../../docs/adr/0025-bounded-lossless-review-and-input-diagnostics.md@d64a75c9d9071664
  - source: incident
- **C-8.8** — WHEN trust input validation raises an error THE SYSTEM SHALL preserve charged generation and review budgets with a bounded typed explanation while refusing execution of the invalid input and publication of its prediction.
  - see: ../../docs/adr/0025-bounded-lossless-review-and-input-diagnostics.md@d64a75c9d9071664
  - source: incident
- **C-8.9** — WHEN declaring review command constraints or parsing a bounded pytest command THE SYSTEM SHALL state exact clause-to-scenario membership and the existing allowed flags, reject unsupported options with an actionable explanation before execution, and retain native challenges for valid inputs.
  - see: ../../docs/adr/0025-bounded-lossless-review-and-input-diagnostics.md@d64a75c9d9071664
  - source: incident

## Model-visible generation limits
- **C-5.8** *(supersedes C-5.1)* — WHEN the generator requests a completion THE SYSTEM SHALL supply only verified public issue and selected source contents plus trusted execution metadata, disclose remaining generation calls including the current request, reserved review calls, remaining shared test runs and the output-token acceptance limit, retain the complete transcript and candidate fingerprint, and enforce the unchanged budgets including metadata in the context limit.
  - see: ../../docs/adr/0026-model-visible-execution-budgets.md@a3bd990d0397533c
  - source: incident

## Contrastive reviewer instructions
- **C-8.11** — WHEN independent review is prepared THE SYSTEM SHALL disclose remaining shared calls and tests with bound-scenario audit cost estimates, distinguish pending execution from semantic gaps, count metadata against the unchanged context limit, and preserve native rejection and incompleteness rules.
  - see: ../../docs/adr/0029-review-resource-and-phase-disclosure.md@6df2ca187d10a3ef
  - source: incident

- **C-8.10** — WHEN independent review is requested THE SYSTEM SHALL ask for different valid implementation mechanisms and observable representations where the issue permits freedom, require issue-based justification of literals and internal-state assertions, and retain gap and activation rules without attesting semantic diversity.
  - see: ../../docs/adr/0028-contrastive-review-instructions.md@7496304e785577d0
  - source: incident

## Existing named test definitions
- **C-5.9** — WHEN a model overlay would execute or a test patch would export THE SYSTEM SHALL reject removal, modification or shadowing of pre-existing named test function and method AST definitions, allow additive definitions, and refuse altered existing files whose syntax cannot be compared without claiming semantic equivalence of surrounding code.
  - see: ../../docs/adr/0027-preserve-existing-named-tests.md@dc405a0dce95a54b
  - source: incident
