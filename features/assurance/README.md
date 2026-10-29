# Requirement assurance: what is implemented and why believe it

Athena's product is a per-requirement evidence map. A release gate is an optional
policy consumer of that map. It is not the assessment itself.

The first implementation is an opt-in deterministic report. It does not change
existing gates or silently reinterpret their historical PASS records.

## Five separate questions

| Dimension | Support means, within the declared scope |
|---|---|
| execution | the supplied observation says the check passed on these bytes |
| check_adequacy | supplied controls accept a valid alternative and detect an activated defect |
| implementation | execution and both controls support the same checks, inputs and scope |
| specification | a supplied review judged the requirement coherent in its scope |
| code_correspondence | a supplied review linked behavior to requirement meaning |

Each dimension can be SUPPORTED, CONTRADICTED, CONFLICT or UNKNOWN. A single
counterexample contradicts the corresponding claim; conflicting positive and
negative observations remain visible. Missing or stale evidence is unknown.
Every live clause is included, including those without any evidence. Draft,
withdrawn and superseded clauses are not active obligations.

Counts describe evidence coverage. They are not probability of correctness,
semantic completeness, branch coverage, or a percentage of project completion.
A supported bounded example does not prove the entire requirement. Unspecified
behavior remains unspecified. No inferred requirement is added to the contract.

## Use

```console
python athena.py assess evidence/manifest.json --cwd . -o evidence/report.json --html evidence/review.html
```

The HTML view opens immediately. Exit 0 means the report was generated, including
when all requirements are UNKNOWN. Invalid inputs produce exit 2. This command
does not run Git, commands from evidence, models, or release policies.

The reviewer supplies a JSON manifest with `schema: athena.assurance/1`,
`contract`, nonempty `implementation` paths, and `evidence` array. An empty evidence
array is valid: all active requirements are unknown. Each evidence record has:

- unique `id`, live `clause`, current clause `pin`;
- `kind`: execution, valid_alternative, violation, spec_review or code_review;
- `outcome`: PASS, FAIL or UNKNOWN;
- `scope`, `producer`, `basis`: specific declared boundaries and provenance;
- `inputs`: relative POSIX paths mapped to SHA-256, including the contract and all implementation inputs;
- `checks`: nonempty fingerprinted check paths for execution and control observations;
- `artifact` and `artifact_sha256`: the retained observation;
- `activated: true` for violation controls, supported by the observation artifact.

For controls, PASS means the expected behavior occurred: a valid alternative
passed the check, or the activated defective alternative failed the check.
It does not mean the defective alternative passed. Review FAIL means a specific
problem was found; its explanation belongs in the artifact and basis.

## Trust boundary and next integration

An executed control demonstration is available:

```console
python examples/assurance_demo.py path/to/output
```

It runs real Python subprocesses for a correct implementation, an activated
arithmetic defect, an overly strict check rejecting a valid alternative, and a
vacuous check accepting the defect. A fifth requirement has no observations.
Receipts retain commands, exit codes and an arithmetic activation witness; the
HTML opens immediately. Expected implementation states are respectively
SUPPORTED, CONTRADICTED, UNKNOWN, UNKNOWN, UNKNOWN. This tiny authored oracle
tests the accounting mechanism; it is not independent validation of real projects.

Fingerprints detect stale bytes, not a dishonest reviewer. The initial importer
validates bindings and computes a report from **declared observations**; it does
not authenticate producers, infer independence, inspect the truth of artifacts,
or itself execute controls. A fabricated PASS declaration can still be imported.
Code correspondence is a review judgment, never automatically proven by coverage.

Existing ledgers, spec-trust audits and clause maps should feed this format via
explicit adapters that preserve their actual scope and provenance. Until those
adapters exist, do not describe this report as automatic assessment of the whole
repository. The next evaluation must score requirement-level classifications
against independently curated known implementations, ambiguous requirements,
bad oracles and valid alternatives. Keep false support, false contradiction and
unknown rates separate from any benchmark solution rate.
