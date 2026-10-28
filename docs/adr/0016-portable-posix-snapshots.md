# ADR-0016: Preserve links and file modes across Windows and Linux

- Status: accepted
- Date: 2026-10-25
- Deciders: implementation within the operator-approved benchmark work
- Cited by: features/tdd-benchmark C-4.8 and C-6.7

## Context
The first preparation of the frozen thirty-task cohort exported only 22 tasks. Eight
Django, Matplotlib and Pylint revisions contained legitimate repository symlinks, which
the exporter rejected. Replacing tasks would change the experiment. Silently dropping
links or flattening them would change observable filesystem behavior.

## Decision
Store contained links as explicit inert host files plus link-target metadata. Record
regular-file modes. The reader returns link identity and its resolved public target,
never placeholder bytes as code. Follow POSIX link components in memory, reject root
escapes (including chained links), cycles, history pointers and symlink-parent entries.
Do not create Windows symlinks or require additional host privileges.

The offline Linux test runner recreates symlinks and file modes in its fresh source copy
before pytest. Candidate overlays cannot replace or traverse source links; edits must
target their regular public implementation files. The source mount remains read-only.

A real container control found /tmp mounted noexec, preventing a 0755 source script from
running. The pytest runtime explicitly mounts temporary storage exec,nosuid,nodev. Other
constraints remain: offline network, non-root uid, read-only root and bounded resources.
The direct sandbox command and pytest runtime are distinct interfaces.

## Consequences
This preserves declared link identity and file modes, not every Git checkout timestamp or
directory-metadata detail. Unsupported archives fail explicitly. Old snapshots without
filesystem metadata remain readable for prior controls; real study preparation uses the
new portable format. Public-source readiness does not establish dependency readiness or
model performance. The original frozen task ids and issue hashes remain unchanged.
