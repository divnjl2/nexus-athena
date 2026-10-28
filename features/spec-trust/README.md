# Spec trust

`athena trust` evaluates the executable spec itself using reviewer-declared valid
alternatives and semantic violations. This complements `spec run`, line coverage and AST
mutation. PASS means the declared challenge set passed; it never means the requirement is
complete or that correctness has a numeric probability.

## Run the engineering pilot

Use a Python environment containing pytest (the project core uses the standard library):

```powershell
python tools/build_spec_trust_pilot.py
python athena.py trust features/spec-trust/pilot/manifest.json --timeout 90 `
    -o features/spec-trust/pilot/evidence.json
python athena.py check features/spec-trust/contract.md --run --purl= `
    --trust features/spec-trust/pilot/manifest.json `
    --trust-evidence features/spec-trust/pilot/evidence.json
```

The empty explicit purl prevents Git auto-discovery (the `--purl=` spelling also works in
Windows PowerShell). The requested trust receipt supplies reverse evidence; this command
does not waive an incomplete leg. This feature does not require Git. A normal production
check can additionally provide its current line map.

The pilot targets twelve clauses in the framework itself. Every clause has an equivalent
expression refactoring and one semantic boundary violation. A separate activation command
must first observe the violation. The bound spec must then reject it via an assertion.
The activation probes must fail on the clean source. The manifest is derived by the builder;
rebuild it after implementation changes and review the resulting variants before accepting
the receipt. The labels are an engineering proposal, not independent human adjudication.

## Reviewer-owned manifest

The schema is `athena.spec_trust/1`. The manifest contains:

* `contract`, `scenarios`: repository-relative source files. Every selected clause is live,
  every spec is bound to it, and both pins must match current normative text.
* `inputs`: explicit files or directories copied into each fresh workspace. Include all
  test helpers, configuration and imported project modules needed by the commands.
* `implementation`: exact Python paths a challenge may replace. Tests, conftest and paths
  outside the declared inputs cannot be overlaid. Symlink inputs are refused.
* `passports`: clause id and pin; intent source; owner decision; input domain; observable
  outcome; oracle source; explicit assumptions, undefined behavior and known gaps; spec ids.
* `variants`: id, rationale, kind (`valid` or `violation`) and a `files` mapping of allowed
  paths to replacement source. A violation also needs its own `activation` command.

Review the expected behavior before running. Do not derive the expected result only from
the implementation being judged. Preserve legitimate output alternatives and explicitly
classify undefined inputs. Owner metadata is a recorded declaration, not an automatic claim
that the owner is correct. An LLM opinion is not an independent oracle.

Each spec command and activation command gets a fresh filesystem copy. The verifier checks
file hashes before and after execution. Activation effects cannot carry over to the spec.
The process environment removes inherited pytest/Python injection options, disables plugin
autoload and uses the verifier's interpreter. Required third-party plugins must be explicitly
requested in a reviewed command. Git operations in any command still require user approval.

## Outcomes

* PASS: all selected baselines passed, both kinds of control were evaluated successfully,
  all violations activated and were caught, every declared valid variant passed, no known
  gap is declared. This statement is scoped to those observations.
* FAIL: an activated violation passed, a valid alternative failed, baseline assertions
  failed, or the command changed protected inputs.
* INCOMPLETE: a control is missing, activation did not succeed, execution had a tool error,
  or known gaps remain. Timeout, missing tests, collection errors and skips are not kills.

pytest commands use JUnit evidence. Only assertion failures are automatic semantic witnesses.
Runtime exceptions and nonzero exits of generic commands are inconclusive without a trusted
adapter. A generic zero exit can witness activation; write a meaningful activation assertion.

## Evidence and the check gate

The receipt includes the manifest hash, hashes of every declared input (including challenge
sources), Python version and interpreter hash, installed package-version inventory hash,
and a hash of the effective environment without recording secret values. `check --trust …
--trust-evidence …` rejects missing, mismatched or stale receipts and receipts for another
contract. It remains an explicit opt-in so existing fast checks keep their cost model.

Store receipts outside `inputs`; a receipt included in its own input digest would immediately
be stale. Re-run after changing a relevant input. Pin and manage dependencies externally:
the package-version inventory is not a hash of every installed dependency's implementation.
Receipts are trusted local artifacts, not signed attestations or a remote verifier service.

## Limits and next evaluation

Activation probes must discriminate: typed assertion failure on the clean baseline,
then success on the proposed violation. A constant-true activation is rejected. Import,
collection, skip and timeout failures do not demonstrate inactivity and remain unknown.
Use a pytest activation test (the engineering pilot now wraps probes this way), not a
generic command's untyped nonzero exit. Baseline-negative and violation-positive results
are recorded separately. This strengthens activation evidence, not the owner's semantic
classification of variants.

The verifier removes volatile `CODEX_TOOL_CALL_ID` tracing metadata from both its actual
execution environment and environment fingerprint. Otherwise unchanged receipts would
become stale between tool invocations. Actual runtime setting changes still invalidate
receipts; this is not a waiver of environment freshness.

Fresh directories and file integrity do not contain arbitrary hostile Python or native code.
For adversarial executors, run this verifier in a separately administered OS/container sandbox
with isolated credentials and resources. Do not advertise filesystem copying as that boundary.
Formal proof and model checking should record their assumptions and domain bounds separately.

The twelve-clause pilot tests the protocol; it does not estimate performance on unseen
production failures. A follow-up independent evaluation should freeze historical bugs and
valid alternatives, compare equal budgets against AST mutation and simple resampling, and
measure false acceptance, false rejection, UNKNOWN cases, cost and spec-evolution regressions.
There is no universal mutation-score threshold that certifies semantic correctness.
