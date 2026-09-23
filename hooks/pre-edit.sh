#!/usr/bin/env bash
# pre-edit.sh — PreToolUse shim for Edit/Write/MultiEdit (features/team-layer C-5.*).
#
# The decision lives in `athena hook pre-edit` (lib/hooks.py): it names the clauses whose
# owned lines the edit touches, across every contract that has a map, and refuses a hand
# edit of a derived artifact (ledger, clause map, exported index) with the command that
# rebuilds it. CONTRACT_CRITERION_BYPASS=1 allows the derived edit and says so.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$here/athena.py" ] || exit 0
exec python "$here/athena.py" hook pre-edit
