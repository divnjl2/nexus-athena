"""CI: enumerate the human-in-the-loop decision points as a machine-readable manifest so the
orchestrator routes exactly those to a human and automates the rest (R8.3)."""
from __future__ import annotations

import json

HITL_POINTS = (
    {"id": "approve-environment-fix", "requirement": "R8.1",
     "blocks": "apply of an environment/dependency fix to a shared or production environment"},
    {"id": "classify-ambiguous-flaky", "requirement": "R5.2",
     "when": "flaky classification confidence < 0.8"},
    {"id": "move-gate-threshold", "requirement": "R2/R3",
     "when": "any change to a health, coverage, or budget threshold"},
    {"id": "waive-dependency-outage", "requirement": "R2.2",
     "when": "a known external dependency outage is outside the target repo's control"},
)


def manifest() -> dict:
    return {"hitl": [dict(p) for p in HITL_POINTS]}


def write_manifest(path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest(), fh, indent=2)
    return path
