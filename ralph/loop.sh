#!/usr/bin/env bash
# Athena Ralph loop — claim ready issue, route to executor, gate, close. §8.
# One issue = one iteration; the executor session is killed each pass (fresh context).
# Routing: label autonomy:high -> OpenHands (sandboxed); else -> Claurst.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_ITER="${MAX_ITER:-200}"

command -v bd >/dev/null || { echo "bd not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "jq not found" >&2; exit 2; }

declare -A FAILED   # issues that already failed their gate this run (livelock guard)

for ((i=0; i<MAX_ITER; i++)); do
  ISSUE="$(bd ready --json --limit 1)" || { echo "bd ready failed" >&2; break; }
  printf '%s' "$ISSUE" | jq -e 'type=="array"' >/dev/null 2>&1 \
    || { echo "bd ready: non-JSON output, aborting" >&2; break; }
  [ "$(printf '%s' "$ISSUE" | jq 'length')" -eq 0 ] && { echo "queue empty — done"; break; }

  ID="$(printf '%s' "$ISSUE" | jq -r '.[0].id')"
  # if the top ready issue already failed its gate, no progress is possible -> stop
  if [ -n "${FAILED[$ID]:-}" ]; then
    echo "WARNING: top ready issue $ID already failed its gate — stopping (needs triage)" >&2
    break
  fi
  AUTON="$(printf '%s' "$ISSUE" | jq -r '.[0].labels[]? | select(.=="autonomy:high")')"

  bd update "$ID" --claim || { echo "claim failed for $ID (race?) — skipping" >&2; continue; }
  if [ -n "$AUTON" ]; then
    "$HERE/run_openhands.sh" "$ID" || echo "executor error on $ID (iter $i)" >&2
  else
    "$HERE/run_claurst.sh" "$ID" || echo "executor error on $ID (iter $i)" >&2
  fi

  if "$HERE/gate.sh" "$ID"; then
    bd close "$ID"; bd sync
  else
    FAILED[$ID]=1
    bd update "$ID" --status open --note "gate failed iter $i" || true
    bd label "$ID" gate-failed 2>/dev/null || true
    echo "WARNING: gate failed for $ID — labeled gate-failed, needs triage" >&2
  fi
  # executor session is killed here -> next pass starts from a clean context
done
