# ADR-0021: UTF-8 filesystem locale in public runtime processes

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
- Status: accepted

## Context
Django-12858 contains a public file whose name includes U+2297. The source verifier
crashed under the actual Python 3.6 image: its filesystem encoding was ASCII despite
the snapshot preserving the filename. Earlier Python 3.6 controls used ASCII filenames
and therefore did not cover this failure.

## Decision
Launch public runtime inspection and offline code-tool containers with LANG=C.UTF-8
and LC_ALL=C.UTF-8. Newly prepared runtime receipts record the actual interpreter
filesystem encoding and reject non-UTF-8 results; loading a receipt that explicitly
reports another encoding also fails. Legacy receipts without that field remain readable,
but actual execution still receives the fixed locale. Trusted public source provisioning
uses the same locale before filesystem verification/export and inside derived images.

## Consequences
Retain the original INCOMPLETE source-verification attempt. The paired real Python 3.6
control fails writing a U+2297 filename with the C locale and passes the same roundtrip
with C.UTF-8. The frozen source and task cohort are unchanged. Preparation under the old
method is preserved; its cohort worker stops as METHOD_CHANGED, and a separate run must
record new controls under the new framework fingerprints.
