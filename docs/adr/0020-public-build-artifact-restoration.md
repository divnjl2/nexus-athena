# ADR-0020: Public build artifact restoration

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
- Status: accepted

## Context
Fresh execution copies the frozen source archive, which omits generated version modules,
compiled extensions and installation metadata. Merely installing dependencies in an image
does not put these files in the fresh package path. A Linux control now compiles a real
Python C extension from public fixture source and separately generates a data file/link:
the fresh-copy test fails with TOOL_ERROR without the outputs and passes with restoration.

## Decision
Inventory additional runtime files in the inspected public-installed tree, separately
from the known public source. Exclude build/dist/.eggs and bytecode caches. Record relative
path, kind, byte count, executable mode and SHA256, or symlink target. Bind the canonical
inventory digest in the runtime receipt. Legacy receipts without an inventory remain
usable but do not claim restoration of additional outputs.

Before model overlays, restore only those additional files into the fresh workspace.
Reject duplicate paths, public files/directories, parents that are files or symlinks,
root escapes, unsupported inode kinds and manifests over 512 MiB/20000 entries. Recheck
each source output against the bound manifest. Files precede symlinks, and all restored
links must resolve inside the completed workspace. Never overwrite frozen source or an
existing destination. Errors stop the bootstrap before pytest and remain TOOL_ERROR.

## Consequences
Outputs come from trusted public-base provisioning, not gold fixes or model proposals.
This mechanism is not proof that a project's official build succeeded or that its entire
test suite works. Each real project still needs an installation control. Sphinx's HTML
control is rerun through the same path with its seven metadata files restored. Support
for the scientific cohort must be demonstrated on those actual builds, not inferred
from the C-extension control.
