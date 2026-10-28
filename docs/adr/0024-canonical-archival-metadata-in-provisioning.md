# ADR-0024: Canonical archival metadata in trusted provisioning

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
- Status: accepted

## Context
Both selected Matplotlib base-project builds passed, but the public-runtime source
verifier rejected .git_archival.txt. The GitHub archive expands this tracked file's
export-subst placeholders, while the ordinary Git checkout preserves the placeholders.
All other known files matched. This is metadata representation, not an implementation
change or a different selected commit.

## Decision
The trusted provisioning helper may classify that one file as archival metadata only
after checking the public .gitattributes export-subst declaration, the selected base
commit in the archived metadata and the original checkout's $Format:%H$ placeholder.
Retain both representations and their relationship in archival-normalization.json.
Restore the exact frozen public archive bytes, like every other known public file,
before constructing the candidate runtime. Continue rejecting unexplained protected
implementation differences. Admission still rechecks every known file and link.

## Consequences
Create new preparation/image revisions and preserve the failed verifications. No frozen
dataset, source archive, benchmark membership or official harness source is modified.
Git history, executable Git tools, Conda caches and Conda's installed test-files tree remain
outside the public runtime filesystem. Each derived image still needs a real 60-second
installation control before entering the common runtime inventory.
