#!/usr/bin/env bash
# Run OpenHands V1 (software-agent-sdk) headless on ONE bd issue — isolated/autonomous.
# §7/§11: target V1 SandboxService (NOT the V0 `python -m openhands.core.main`).
# Backend-agnostic via LLM_MODEL/LLM_BASE_URL/LLM_API_KEY -> self-hosted cluster (LiteLLM).
# ALWAYS Docker + workdir-only mount + --max-iterations so it can't burn the night.
set -euo pipefail

ID="${1:?usage: run_openhands.sh <issue-id>}"
REPO="${REPO:-$(pwd)}"
MAX_ITER="${OPENHANDS_MAX_ITER:-30}"

command -v bd >/dev/null || { echo "bd not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "jq not found" >&2; exit 2; }
command -v openhands >/dev/null || { echo "openhands (V1 software-agent-sdk) not found" >&2; exit 2; }

TASK="$(bd show "$ID" --json | jq -r '.title + "\n\n" + (.description // "")')"

# headless, isolated: the agent never touches the host; only the workdir is mounted rw
LLM_MODEL="${NEXUS_MODEL:?set NEXUS_MODEL (self-hosted via LiteLLM)}" \
LLM_BASE_URL="${NEXUS_LITELLM:?set NEXUS_LITELLM}" \
LLM_API_KEY="${NEXUS_API_KEY:-sk-noauth}" \
SANDBOX_VOLUMES="${REPO}:/workspace:rw" \
openhands --headless --max-iterations "$MAX_ITER" --task "${TASK}

CONTRACT: work only on this issue; the external gate runs its success_check (your
self-report does not count). New out-of-scope work -> 'bd create ... --label discovered-from:${ID}'.
Do not touch another agent's claim. 'bd sync' before exit."
