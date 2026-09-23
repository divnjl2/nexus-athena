"""
Athena archlint — the effect seams are a list; everything else spawns nothing (v3.11).

"Freeze-line: PURE" appeared in docstrings across lib/ and was held by convention. This
turns the convention into a check (ADR-0005, C-5.4): a module outside the allowlist that
imports a process or network module, at any depth, is a finding with file and line. The
repository must pass its own lint (C-5.5); adding a module to the allowlist is a decision
reviewed like code.

Freeze-line: PURE, stdlib-only (the AST module is not an effect).
"""
from __future__ import annotations

import ast

#: Modules that spawn a process or dial out. `os` is not here on purpose: it is everywhere
#: for paths and environment, and `os.system` is caught by the review, not this lint.
EFFECT_MODULES = ("subprocess", "socket", "urllib", "http", "requests", "ssl", "ftplib",
                  "smtplib", "telnetlib")

#: The seams: the only lib modules allowed to spawn or dial out.
EFFECT_ALLOWED = frozenset({
    "lib/spec_runner.py",   # runs the executable specs
    "lib/clause_map.py",    # runs each spec under coverage
    "lib/adapters.py",      # reads the HEAD sha of a repository
    "lib/bd_client.py",     # the only subprocess boundary to `bd`
})


def lint_sources(files: dict, *, allowed: frozenset = EFFECT_ALLOWED) -> tuple[dict, ...]:
    """PURE: {path: source} -> findings {path, line, module}, document order."""
    out: list[dict] = []
    for path in sorted(files):
        norm = str(path).replace("\\", "/")
        if norm in allowed:
            continue
        try:
            tree = ast.parse(files[path])
        except SyntaxError as e:
            out.append({"path": norm, "line": e.lineno or 0, "module": "syntax error"})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in EFFECT_MODULES:
                        out.append({"path": norm, "line": node.lineno, "module": alias.name})
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in EFFECT_MODULES:
                    out.append({"path": norm, "line": node.lineno, "module": node.module})
    return tuple(out)


def render(findings) -> str:
    if not findings:
        return "arch lint: clean (effects only behind the allowlisted seams)"
    return "\n".join(f"  {f['path']}:{f['line']}  imports {f['module']} outside the effect seams"
                     for f in findings)
