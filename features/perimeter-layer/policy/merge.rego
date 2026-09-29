# Perimeter layer, C-3.2: the merge record under policy, evaluated by conftest (OPA) before fast-forward.
# The input is lib.scan.policy_input(record, changed, stages, last_dispatch):
#   record             the merge record about to be written (schema athena.merge/1)
#   changed            the offer's changed paths against the target
#   stages             the stages the queue has run so far
#   provenance_present whether the task's last dispatch record carries its provenance (C-8.6)
# Every denial names its clause and the word the spec (S3.2) reads it by. Rego v1 (OPA 1.x, conftest 0.70): `if` and `contains` are mandatory.
package main

deny contains msg if {
    input.record.schema != "athena.merge/1"
    msg := sprintf("C-3.2: the record schema is %v, not athena.merge/1", [input.record.schema])
}

deny contains msg if {
    input.provenance_present == false
    msg := "C-3.2: no provenance on the task's last dispatch (C-8.6) — the offer has no recorded origin"
}

deny contains msg if {
    some i
    path := input.changed[i]
    contains(path, "/sealed/")
    msg := sprintf("C-3.2: a sealed acceptance was changed by the offer: %v (C-2.8 — the sealed tier is written only by the frontier)", [path])
}

deny contains msg if {
    not stage_seen("mutation")
    msg := "C-3.2: the mutation stage did not run before policy (C-11.2 — an offer skips it only with --no-mutation, which the record must say)"
}

stage_seen(name) if {
    input.stages[_] == name
}
