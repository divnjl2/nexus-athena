# ADR-0022: Stage verified public source inside the installed runtime

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
- Status: accepted

## Context
After fixing Django's Python 3.6 locale, its first real control still exhausted the
180-second engineering timeout copying 6213 files through a Windows Docker bind mount.
The test itself had not started. Increasing the per-arm test budget would confound the
comparison and hide preparation overhead.

## Decision
A public-installed runtime already contains the known public base, verified at admission
and pinned by immutable image id and snapshot hash. Stage its declared source files from
that image into the fresh /tmp/work directory. Recheck every regular file hash and link
target during staging. Copy no undeclared image files at this step; additional installation
outputs still follow the separate bounded artifact inventory. Apply POSIX metadata and
then model overlays in the existing order. Environment-only runtimes retain the input
mount copy path. The verified public input mount remains available in both cases.

## Consequences
Choose the source mode from the bound runtime receipt, ignoring any model-provided mode.
This preserves selected source identity, fresh isolation and the same test timeout while
removing per-file host-sharing overhead. Keep the earlier timed-out control as INCOMPLETE;
the new source-staging method requires its own framework fingerprints and live control.
