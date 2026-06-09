#!/usr/bin/env bash
# Athena installer — Beads + Claude Code plugin + MCP + executor checks (§7, §11).
#
# Phase 0 ships this as a syntactically-valid, grounded installer. Actual version
# confirmation against current releases is the documented install-time step (§11):
# the pins below were verified 2026-06-09 but MUST be re-checked before a real run,
# because bd / OpenHands schemas drift.
set -euo pipefail

# ---------------------------------------------------------------------------
# Pinned versions (§11 — re-confirm before run; bd_client tests catch schema drift)
# ---------------------------------------------------------------------------
BEADS_REF="${BEADS_REF:-v1.0.4}"              # gastownhall/beads — PINNED tag (re-confirm before run); raw /main/ pipe-to-bash is a hazard
OPENHANDS_TARGET="${OPENHANDS_TARGET:-V1}"    # software-agent-sdk; V0 monolith superseded Nov 2025
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { printf '[athena] %s\n' "$*"; }
warn() { printf '[athena][WARN] %s\n' "$*" >&2; }
die()  { printf '[athena][ERR] %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
# 1. Beads (bd) — durable task-graph on Dolt
# ---------------------------------------------------------------------------
install_beads() {
  if have bd; then
    log "bd present: $(bd version 2>/dev/null || echo 'unknown')"
    return 0
  fi
  have curl || die "curl required to install Beads"
  # official installer at a PINNED ref — download THEN execute (never blind-pipe a floating /main/)
  local tmp; tmp="$(mktemp)"
  log "downloading Beads installer @ ${BEADS_REF} ..."
  curl -fsSL "https://raw.githubusercontent.com/gastownhall/beads/${BEADS_REF}/scripts/install.sh" -o "$tmp" \
    || die "could not download beads installer @ ${BEADS_REF}"
  log "running Beads installer (pinned ${BEADS_REF}; source saved at ${tmp} for inspection)"
  bash "$tmp"
  rm -f "$tmp"
  have bd || die "bd not on PATH (alt: npm i -g @beads/bd@${BEADS_REF#v} | brew install beads)"
}

init_beads() {
  if [ -d "${PLUGIN_ROOT}/.beads" ]; then
    log "bd already initialised (.beads present)"
  else
    ( cd "${PLUGIN_ROOT}" && bd init )
  fi
  # smoke the JSON surface the compiler/bd_client depend on (§5, §11)
  bd ready --json >/dev/null 2>&1 || warn "bd ready --json failed — check bd version/schema"
}

# ---------------------------------------------------------------------------
# 2. Claude Code plugin + MCP server registration
# ---------------------------------------------------------------------------
register_plugin() {
  if have claude; then
    log "register plugin via local marketplace:"
    log "  claude plugin marketplace add ${PLUGIN_ROOT}"
    log "  claude plugin install nexus-athena@nexus-athena-local"
  else
    warn "claude CLI not found — add ${PLUGIN_ROOT}/.claude-plugin/marketplace.json manually"
  fi
}

register_mcp() {
  # Athena MCP server (built in Phase 4). Print the wiring for Hermes / Claude.
  log "MCP server (athena) — add to your client config once Phase 4 lands:"
  cat <<JSON
  {
    "mcpServers": {
      "athena": {
        "command": "uv",
        "args": ["run", "python", "-m", "athena_mcp.server"],
        "cwd": "${PLUGIN_ROOT}/mcp/athena_mcp"
      }
    }
  }
JSON
}

# ---------------------------------------------------------------------------
# 3. Executor preflight — OpenHands V1 (primary), Claurst (alt)
# ---------------------------------------------------------------------------
check_openhands() {
  [ "${OPENHANDS_TARGET}" = "V1" ] || warn "OPENHANDS_TARGET=${OPENHANDS_TARGET}: V0 monolith superseded — use V1 (software-agent-sdk)"
  if have openhands; then
    log "openhands present (target ${OPENHANDS_TARGET}, software-agent-sdk)"
  elif { python3 -c "import openhands" || python -c "import openhands"; } >/dev/null 2>&1; then
    log "openhands python package present"
  else
    warn "OpenHands not found — install software-agent-sdk (V1): pip install openhands"
    warn "do NOT use 'python -m openhands.core.main' (V0 monolith, superseded)"
  fi
  have claurst && log "claurst present (alt executor)" || warn "claurst not found (optional)"
}

main() {
  log "plugin root: ${PLUGIN_ROOT}"
  have git    || die "git required"
  { have python3 || have python; } || die "python3 required"
  install_beads
  init_beads
  register_plugin
  register_mcp
  check_openhands
  log "done. Next: build phases 1-7 (see athena-final-opus-plan.md §9)."
}

main "$@"
