#!/usr/bin/env bash
# Athena external gate — the AUTHORITATIVE success_check runner (§8, invariant #5).
# The executor's self-report does NOT count; this script decides pass/fail.
#
# SECURITY (security-audit Finding 3): success_check is plan-authored shell, run here
# on the host. It is tier-gated/reviewed QRSPI output — semi-trusted, not arbitrary
# external input. Defenses: run under a timeout + a restricted shell, optionally
# allowlist the command's first token (GATE_ALLOWLIST), and prefer routing risky work
# through the sandboxed OpenHands runtime. Never eval it unquoted into the host shell.
set -euo pipefail

ID="${1:?usage: gate.sh <issue-id>}"
GATE_TIMEOUT="${GATE_TIMEOUT:-300}"

command -v bd >/dev/null || { echo "gate: bd not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "gate: jq not found" >&2; exit 2; }

# success_check is carried in the issue body (description); extract deterministically
DESC="$(bd show "$ID" --json | jq -r '.description // ""')"
CHECK="$(printf '%s\n' "$DESC" | sed -n 's/^success_check:[[:space:]]*//p' | head -1)"
[ -n "$CHECK" ] || { echo "gate: issue $ID has no success_check" >&2; exit 2; }

# optional COARSE allowlist: the command's first token must be permitted. Advisory only
# (a wrapper like `timeout`/`bash` would still pass) — the real defenses are upstream
# tier-review of plans + routing risky work through the sandboxed executor.
if [ -n "${GATE_ALLOWLIST:-}" ]; then
  first="${CHECK%%[[:space:]]*}"
  case " $GATE_ALLOWLIST " in
    *" $first "*) : ;;
    *) echo "gate: '$first' not in GATE_ALLOWLIST" >&2; exit 2 ;;
  esac
fi

echo "gate[$ID]: $CHECK"
# AUTHORITATIVE: the success_check's own exit code is the verdict (set -e propagates it)
timeout "$GATE_TIMEOUT" bash --noprofile --norc -c "$CHECK"
