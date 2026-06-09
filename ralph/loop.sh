#!/usr/bin/env bash
# Athena Ralph loop — claim ready issue, route to executor, gate, close. §8.
# One issue = one iteration; the executor session is killed each pass (fresh context).
# Routing: label autonomy:high -> OpenHands (sandboxed); else -> Claurst.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_ITER="${MAX_ITER:-200}"

command -v bd >/dev/null || { echo "bd not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "jq not found" >&2; exit 2; }

for ((i=0; i<MAX_ITER; i++)); do
  ISSUE="$(bd ready --json --limit 1)"
  [ "$(printf '%s' "$ISSUE" | jq 'length')" -eq 0 ] && { echo "queue empty — done"; break; }

  ID="$(printf '%s' "$ISSUE" | jq -r '.[0].id')"
  AUTON="$(printf '%s' "$ISSUE" | jq -r '.[0].labels[]? | select(.=="autonomy:high")')"

  bd update "$ID" --claim
  if [ -n "$AUTON" ]; then
    "$HERE/run_openhands.sh" "$ID" || echo "executor error on $ID (iter $i)"
  else
    "$HERE/run_claurst.sh" "$ID" || echo "executor error on $ID (iter $i)"
  fi

  if "$HERE/gate.sh" "$ID"; then
    bd close "$ID"; bd sync
  else
    bd update "$ID" --status open --note "gate failed iter $i"
  fi
  # executor session is killed here -> next pass starts from a clean context
done
