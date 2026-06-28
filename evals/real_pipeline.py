"""Drive the REAL Athena planning pipeline via a headless Claude Code agent.

This is the faithful automation of the manual subagent run: per task it scaffolds a
Spec-Kit workspace and shells `claude -p` (the canonical Spec-Kit executor) to run
`/speckit-specify → /speckit-clarify → CRISP 3_design → scenarios` answer-key-isolated,
returning the functional requirements. The eval then scores recall/coverage against the
task's ground-truth expected.yaml (which the agent is forbidden to read).

Unlike the strawman (direct vLLM hops), this dog-foods the Claude Code PLUGIN — the same
pipeline the framework ships. Each call = a full agent session (~tens of k tokens).
"""
from __future__ import annotations

import json
import os
import re
import subprocess

CLAUDE = os.environ.get("CLAUDE_BIN", "claude")
SPECIFY = os.path.expanduser("~/.local/bin/specify")
ATHENA_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _json_block(text: str):
    """Extract the largest top-level JSON object/array from agent output."""
    text = re.sub(r"```(?:json)?|```", "", text)
    cands, i, n = [], 0, len(text)
    while i < n:
        if text[i] not in "[{":
            i += 1
            continue
        close = "]" if text[i] == "[" else "}"
        depth, in_str, esc, end = 0, False, False, None
        for j in range(i, n):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is not None and text[end] == close:
            cands.append(text[i:end + 1])
            i = end + 1
        else:
            i += 1
    for c in sorted(cands, key=len, reverse=True):
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"no parseable JSON in agent output: {text[:200]!r}")


def _scaffold(workspace: str):
    os.makedirs(workspace, exist_ok=True)
    subprocess.run(
        [SPECIFY, "init", ".", "--here", "--force", "--no-git", "--script", "sh",
         "--integration", "claude"],
        cwd=workspace, capture_output=True, encoding="utf-8", errors="replace", timeout=300)


def _prompt(intent: str, workspace: str) -> str:
    return f"""You are the Spec-Kit planning agent. Execute the REAL GitHub Spec-Kit + CRISP \
planning pipeline on ONE feature, faithfully following the skill templates. Produce a \
genuine, complete spec; do NOT pad or invent beyond what the feature implies.

## Feature intent (the ONLY input)
{intent}

## Workspace (Spec-Kit already initialized here)
{workspace}

## Steps (act as the canonical Claude Code agent)
1. Read `.claude/skills/speckit-specify/SKILL.md` and `.specify/templates/spec-template.md`.
   Execute /speckit-specify: create specs/001-feature/spec.md from the template — User
   Scenarios, **Edge Cases**, **Functional Requirements (FR-NNN, "System MUST ...")**,
   Success Criteria. Think genuinely about what the feature must do AND what can go wrong;
   fill the Edge Cases section properly.
2. Execute /speckit-clarify (read its SKILL.md): non-interactive, so resolve the ambiguous
   areas with reasonable industry-standard defaults, folding them back into spec.md as FRs.
3. Read `{ATHENA_REPO}/commands/crisp/3_design.md` and apply its lens to enrich the spec
   with behavioural requirements (stay in "what", no tech stack).

## Return — your FINAL message MUST be ONLY this JSON (no prose around it):
{{"functional_requirements":[{{"id":"FR-001","text":"System MUST ..."}}],"edge_cases":["..."],"user_story_count":<int>}}

HARD RULE: do NOT read any file named expected.yaml or gate_test.py or anything under an
`evals/` directory — those are a hidden answer key; reading them invalidates the run.
Derive everything from the intent + Spec-Kit templates only."""


def run_real_pipeline(intent: str, workspace: str, *, timeout: int = 900) -> dict:
    """Scaffold + drive claude -p; return parsed {functional_requirements, edge_cases, ...}."""
    _scaffold(workspace)
    proc = subprocess.run(
        [CLAUDE, "-p", _prompt(intent, workspace),
         "--output-format", "json", "--dangerously-skip-permissions"],
        cwd=workspace, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    # claude --output-format json wraps the run; the agent's text is in .result
    raw = proc.stdout
    try:
        envelope = json.loads(raw)
        result_text = envelope.get("result", raw) if isinstance(envelope, dict) else raw
    except json.JSONDecodeError:
        result_text = raw
    parsed = _json_block(result_text)
    if not isinstance(parsed, dict) or "functional_requirements" not in parsed:
        raise ValueError(f"agent did not return the expected JSON shape: {str(parsed)[:200]}")
    return parsed


if __name__ == "__main__":
    import sys
    intent = sys.argv[1] if len(sys.argv) > 1 else "Implement add(a, b) -> int that returns a+b."
    ws = sys.argv[2] if len(sys.argv) > 2 else "/d/tmp/claude/rp_smoke"
    out = run_real_pipeline(intent, ws)
    print(f"FRs: {len(out['functional_requirements'])}, edge_cases: {len(out.get('edge_cases', []))}")
