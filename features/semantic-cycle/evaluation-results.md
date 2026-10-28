# Semantic cycle evaluation, 2026-10-27

The implementation now connects issue-grounded intent, assertion-support review,
immutable repair feedback, contrastive controls, shared reserved budgets and sealed
independent assessment. Review judgments remain advisory declarations. The experiment
does not justify trusting generated specifications without examining their evidence.

## Fresh primary study

Thirty evaluation cases and five calibration cases were fixed separately and disjoint
from the previous 35 cases. The requested model was gpt-6-astra at medium effort,
using subscription CLI transport in fresh contexts. The request does not attest the
provider's backend model. Each case/arm had fixed limits of 24 outer model requests
and 48 test-tool attempts, with at most two outer repair attempts.

All 90 case/arm outcomes and 139 valid raw candidate versions were sealed before
independent grading. One unavailable public runtime remains in all three denominators.
Selection of the final candidate preceded independent grades.

| Arm | Raw versions: PASS / FAIL / INCOMPLETE | Released finals | Released independently PASS / FAIL |
| --- | --- | --- | --- |
| Direct | 19 / 2 / 7 | 28 | 19 / 2 |
| Athena Trust | 23 / 7 / 7 | 0 | 0 / 0 |
| Semantic cycle | 33 / 11 / 30 | 0 | 0 / 0 |

These are strict TDD/Gold-test agreement states, not absolute correctness against the
public issue. Independently INCOMPLETE released direct candidates are not counted as
good or bad. Zero releases in both Athena arms makes zero bad releases vacuous;
acceptance precision is undefined. Selected independently good finals withheld were
16 for Trust and 9 for semantic cycle under the primary measurement.

The shared journals retained 955 charged outer model requests and 954 test-tool
attempts. Provider-internal retries and spending are not measured. Of 955 transport
records, 952 completed with distinct known thread IDs and three remain STARTED with
unknown thread metadata; these charges were retained, not inferred successful.

## Repair and reviewer evidence

All 24 second-attempt contexts received exactly the public feedback derived from
the previous proposal, review and native audit. Nineteen forward-frozen revisions
preserved requirements; five kept the same test files. Versioning is not evidence
that a semantic defect was repaired. Forty-three review envelopes were retained:
33 included a model call and ten did not. Separate contexts do not attest independent
reviewer errors.

The secondary control study retained all 235 planned entries: 43 reference hypotheses,
125 declared-valid alternatives and 67 declared violations. Two alternatives failed
materialization and remain INCOMPLETE. The other 233 entries and 24 Gold controls
produced 257 execution receipts. No additional model requests were made.

Conditioning each variant on its parent reference passing the Gold control produced:

| Reviewer declaration | Bounded agreement / distinguished | Conflict / not distinguished | INCOMPLETE |
| --- | --- | --- | --- |
| Valid alternative | 49 | 20 | 56 |
| Violation | 33 | 7 | 27 |

The denominator is all 192 variants, correlated within cases. These counts measure
agreement with hidden tests. A valid declaration conflicting with hidden tests is not
automatically invalid under the public issue. A declared violation passing hidden
tests is not automatically valid. The secondary analysis is exploratory, not a new
cohort or a preregistered primary score.

Three inspected examples expose scope boundaries: Astropy's output-header issue was
tested through additional input-reading behavior; pytest's visible exception transport
alternative conflicted with structural compatibility tests; Pylint's Windows src/
scenario was checked through broader current-directory compatibility. These findings
leave public admissibility unresolved rather than reclassifying hidden failures.

## Supplemental measurements

A separately retained dependency repair reran 17 originally incomplete versions using
verified coverage wheels. An explicit identifier-normalization diagnostic then replayed
all 139 versions, with 24 changed identifiers and raw-log bindings. The supplemental
decidable counts were 26/28 direct, 34/37 Trust and 63/74 semantic cycle; selected good
finals withheld were 20 for Trust and 15 for semantic cycle. Releases stayed zero in
both Athena arms. Original primary scores remain unchanged. These post-hoc diagnostics
are not fresh independent evidence of improvement.

## Evidence and completion boundary

The local study root is `athena-review/tdd-bench/semantic-cycle-20261025-01` under the
operator's home directory. Its `review.html` links raw records and scoped HTML reviews.
Canonical evidence includes `design-v2.json`, `study-01/assessment.json`,
`workflow-verification-06`, `completion-evidence-audit-02/result.json`,
`feedback-delivery-audit-02/result.json`, `measurement-supplement-audit-01/result.json`,
`control-probe-02/assessment.json`, `control-parent-diagnostic-01/assessment.json`,
and `control-completion-audit-01/result.json`.

The final control provenance audit verified all 209 frozen execution inputs, all
235 control entries, all 192 variant-parent bindings and all 30 case denominators.
It reports CONTROL_PROVENANCE_PASS and explicitly does not attest semantic truth or
committed-state completion. This document was written after that frozen experiment;
the original execution inventory is historical and must not be described as the
current repository inventory. Publication and committed-state gates remain separate.
