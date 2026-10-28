# ADR-0019: Public-installed runtimes

- Status: accepted
- Date: 2026-10-28
- Date scope: format and rationale review; the original decision predates this review

### Historical authoring notes
- Status: accepted
- Supersedes: ADR-0013's restriction to empty environment-only images

## Context
An environment image supplies dependencies but may omit pytest, editable package metadata
and generated build files. The selected Sphinx source could not run a basic HTML build
with that image. The official base-project build installed the missing dependencies;
it also adjusted setup.py and tox.ini for dependency compatibility. No gold patch or
gold test is applied during that build.

## Decision
A trusted operator may construct a public-installed derivative. Start a fresh final
image from the environment image, copy the installed Python environment from the trusted
base-project build, and supply a filtered public source tree. Do not inherit task-image
layers or copy its Git directories or setup script. Verify protected implementation
against the frozen public snapshot. Restore every known source file from that snapshot,
including setup configuration changed by upstream installation. Record additional build
outputs and dependency repairs separately. This is trusted provisioning, not a model tool.

The runtime command accepts a separate athena.public-runtime tag family. Admission pins
the immutable image id, checks snapshot/instance labels and actually inspects the image:
every known public file/link must match, /testbed must resolve to the public-only source,
no Git directories/files or task setup script may remain, and pytest must import. The
inspector scans the container filesystem except proc/sys/dev without following links.
Retain this as schema 2, with an explicit public-installed kind; schema 1 environment-only
receipts remain compatible. Raw task images remain forbidden.

Candidate execution still copies the public input into /tmp/work and checks import
origin there. The installed public tree is not the model's mutable reference proposal.
Admission does not prove all project tests work. Projects needing compiled/generated
files in the fresh work copy require separately verified artifact restoration before
being called ready. The initial live control covers Sphinx, a pure Python project; it
does not establish support for the rest of the frozen cohort.

## Consequences
The Sphinx control retains the original missing-roman error and a separate roman==3.3
dependency repair. The repaired image builds HTML offline from the selected base. A
deliberately corrupted source image must fail runtime admission despite matching labels.
These are engineering controls, never model scores or evidence of Athena superiority.
