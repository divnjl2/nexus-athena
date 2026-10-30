# Optional formal evidence

System design and tradeoffs: [ADR-0032](../../docs/adr/0032-formal-evidence-does-not-validate-intent.md).

```console
python athena.py formal manifest.json --cwd path/to/inputs --python path/to/python-with-crosshair --dafny path/to/Dafny.exe -o receipt.json --html review.html
```

HTML contains architecture, interactive tradeoff selection, observed tool results
and an inspectable raw receipt for each job. It opens immediately. Exit 0 means
receipt generation, including UNKNOWN observations; invalid inputs return 2.
Tools are optional and explicitly installed by the operator, never downloaded by
the collector. Execution is local and is not a sandbox.

Manifest schema `athena.formal_evidence/1` has `contract` and a nonempty `tasks`
array. Each task contains unique `id`, live `clause`, current `pin`, `engine`
(`crosshair`/`dafny`), source `target`, `subject_kind` (`model`/`implementation`),
nonempty `scope`, nonempty string `assumptions`, and `inputs` mapping declared
relative POSIX input paths to SHA-256. Contract and target must be included.
The input closure is a declaration, not automatically discovered or attested.

The collector validates all jobs before executing any of them. It retains argv,
exit status, output, timing, explicit environment overrides and executable hash.
Post-run changed inputs or manifest invalidate the observation. Ordinary input
hashing does not detect a malicious change-and-restore race.

## Executed pilot

The first integration target is now **CrossHair on production Python**, starting
with `lib.assurance.combine`. Four postconditions express the evidence truth
table: absent evidence is unknown; simultaneous support and contradiction are
conflict. This is a deliberately small pure kernel, not an assessment of the whole
framework. Dafny remains an optional later path.

```console
python tools/run_crosshair_selfcheck.py OUTPUT --python PATH_TO_PYTHON_WITH_CROSSHAIR
```

The self-check freezes an exact source snapshot and its declared local module
closure. It runs the real function, a table-based valid alternative, three seeded
faults and a missing-contract control. All mutation happens in copies. Expected
results: no counterexample for the baseline/valid alternative, counterexamples for
all seeded faults, UNKNOWN for absent contracts. Raw receipts, source fingerprints
and an auto-opening HTML review are retained in OUTPUT.

The review includes a CrossHair-first explorer: select a seeded fault or valid
alternative, inspect all four boolean input combinations, and compare expected
and actual states. This exhaustive replay is executed separately on the frozen
function and labeled distinctly from the actual CrossHair output. A replay match
does not manufacture a formal search result when contracts are missing.

```console
python tools/run_formal_pilot.py OUTPUT --python PATH_TO_PYTHON --dafny PATH_TO_DAFNY
```

The pilot copies the authored sources from `examples/formal_pilot`, creates a
fingerprinted manifest and runs actual tools. The tested installation uses
CrossHair 0.0.112 and official portable Dafny 4.11.0. The portable archive digest
is `3653f05a111ca21e234709ea7b25ce96083fd6c6f10484256ba54110dbc0654d`.

Expected: correct Python -> NO_COUNTEREXAMPLE, defective Python -> COUNTEREXAMPLE,
no contract -> UNKNOWN; correct Dafny -> VERIFIED_RELATIVE_TO_SPEC, defective
Dafny -> UNPROVEN, weak and vacuous Dafny contracts -> VERIFIED_RELATIVE_TO_SPEC.
Neither the model nor these declared properties are automatically credited to
the user's complete requirement. The pilot is not independent validation.

## Native GSN argument view

The selected argument renderer is [gsn2x](https://github.com/jonasthewolf/gsn2x).

```console
python tools/render_gsn_case.py OUTPUT/receipt.json GSN_OUTPUT --gsn2x PATH_TO_GSN2X
```

This invokes the real native renderer. The output contains `argument.gsn.yaml`
(JSON-compatible YAML), its SVG, source receipt, linked per-case evidence and an
auto-opening HTML zoom view. Global intent and project coverage remain explicit
open goals. Native GSN checks validate structure, not argument truth. See
[ADR-0033](../../docs/adr/0033-gsn2x-renders-arguments-not-verdicts.md).

The executed pilot used gsn2x 4.3.1 for Windows, official executable SHA-256
`2904033553543dc8936aca94dc6738aa7139449d79114b020c0bbf4baa1c33f1`.

## Remaining integration boundary

Formal receipts deliberately remain separate from `assess` until a reviewed
property-to-requirement mapping, full dependency/solver provenance, invalidation
policy and model-to-implementation bridge exist. Tool runtime pinning, structured
outputs, containment and independent classification evaluation remain necessary
for a production service. Existing execution/mutation evidence stays available.
