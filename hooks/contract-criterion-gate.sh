#!/usr/bin/env bash
# contract-criterion-gate.sh — Stop-hook shim: the three questions as the criterion of done.
#
# Everything decidable lives in `athena gate` (lib/gate.py, features/core-layer C-5.*) so it
# is testable and the same on every platform: find every contract under the session's cwd by
# its CLAUSES (not its file name), judge each with the cheap lane (committed ledger, no spec
# run, no clause map), fold the verdicts, block with a reason that names the contract and its
# first cause. Two nudges per session, then it lets go and says so.
#
# Bypass: CONTRACT_CRITERION_BYPASS=1 as an inline prefix, on the operator's word.
# Registered in .claude/settings.json (Stop) — that registration is itself clause C-5.1.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$here/athena.py" ] || exit 0
exec python "$here/athena.py" gate --hook
