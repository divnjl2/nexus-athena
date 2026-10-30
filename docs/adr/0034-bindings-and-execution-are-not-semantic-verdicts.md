# ADR-0034: Bindings and execution are not semantic verdicts

- Status: accepted
- Date: 2026-10-29

## Context
CORE described exit zero as establishing a clause and coverage as line ownership.
The scaffold repeated that implication. These statements conflicted with the
separate evidence dimensions in requirement assurance and the boundaries in
ADR-0010, ADR-0032 and ADR-0033.

The outline and exported needs index made a stronger unsupported claim: their
`proved` values came from scenario bindings without receiving execution results.
A binding to a nonexistent command could therefore appear proved.

## Decision
Describe spec success as an observation within its checked scope. Keep execution,
intent fidelity, check adequacy and code correspondence distinct. A clause map is
observed reach attributed through declared bindings; it does not establish causal
necessity, exclusive semantic ownership or implementation correspondence.

Replace `proved` in the needs index with `spec_bound` and change its schema to
`needs.json/2`. Replace outline `proved` and `unproved` fields with `bound` and
`unbound` under `athena.outline/2`. The displayed binding ratio counts live clauses;
bound drafts remain separate. Do not retain misleading proof aliases.

Keep the existing coverage vocabulary `owns_*`, `home`, `shared` and
`half_proved*` as explicitly limited legacy field names. These record execution
reach, relative attribution and unobserved branch arms. Output limitations state
that execution results and semantic assurance are not assessed by these views.

Review the existing direct CORE citation against its actual four-heading
obligation before repinning. New guidance and non-promotion obligations are added
to core-layer. Changed contract-layer obligations use successor identifiers.
Fingerprint changes are not evidence of human approval, semantic validity, or a
new successful run. Evidence that binds changed inputs must be regenerated or
remain stale.

## Validation
A real local coverage run executes a weak assertion against defective doubling
code. The command succeeds and its implementation line is attributed to a clause,
while another input demonstrates the unmet requirement. Supplying only the
retained execution observation leaves the assessment's implementation, adequacy,
specification review and code correspondence dimensions UNKNOWN.

Index and outline controls bind a missing, unexecuted command. They report the
binding without a proof field, and keep absence of a binding distinct. A mixed
status control prevents bound drafts inflating the live binding ratio.

These are finite behavioral controls and source reviews by Codex, not proof of
all requirements or authenticated independent human acceptance.

## Consequences
Consumers of the old outline and needs schemas must migrate the renamed fields
and regenerate current derived exports. Archived results retain their historical
bytes and interpretation. The assurance reducer, formal-result classification
and release authority are unchanged by these terminology and reporting changes.

Judge corpus exports and score reports also disclose the declared baseline and
mechanical-degradation basis of their legacy labels. Score agreement is relative
to those labels; semantic validity remains NOT_ASSESSED. A control with an
actually failing baseline demonstrates that perfect label agreement can still
pass the unchanged numeric thresholds. Archived corpora, grades, prompts and
gate-eligibility calculations remain unchanged.
