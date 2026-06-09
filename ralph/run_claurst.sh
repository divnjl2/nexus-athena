#!/usr/bin/env bash
# Run Claurst on ONE bd issue — lightweight one-shot (no container overhead) for small work.
set -euo pipefail

ID="${1:?usage: run_claurst.sh <issue-id>}"
REPO="${REPO:-$(pwd)}"

command -v bd >/dev/null || { echo "bd not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "jq not found" >&2; exit 2; }
command -v claurst >/dev/null || { echo "claurst not found" >&2; exit 2; }

TASK="$(bd show "$ID" --json | jq -r '.title + "\n\n" + (.description // "")')"

( cd "$REPO" && claurst run --task "${TASK}

CONTRACT: implement this issue only; the external gate runs its success_check.
New out-of-scope work -> 'bd create ... --label discovered-from:${ID}'." )
