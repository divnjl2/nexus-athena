"""Regeneration module for module equivalence checking."""
from typing import Any, Callable, Dict, List, Optional, Tuple


def regen_packet(module: str, clauses_text: str, specs_text: str, signatures: List[str]) -> str:
    """
    C-8.1 — pack the regeneration packet with clauses, specs, and public signatures only.
    Never include the old body code from the module.
    """
    header = f"# Regeneration packet for {module}\n# Generated from the clauses and specs\n\n"
    
    signatures_block = "# Public signatures\n\n"
    for sig in signatures:
        signatures_block += f"{sig}\n\n"
    
    clauses_section = "\n# Clauses\n\n"
    clauses_section += clauses_text + "\n\n"
    
    specs_section = "\n# Specs\n\n"
    specs_section += specs_text + "\n\n"
    
    packet = header + signatures_block + clauses_section + specs_section + "# End of regeneration packet\n"
    
    return packet


def diff_report(sigs, old: str, new: str, runner, cwd: str, timeout: int = 20):
    """C-8.2 — one `crosshair diffbehavior` per public typed function through the injected
    runner; counterexamples parsed out of its output; private (leading underscore) and
    untyped (no annotations) functions are skipped. Finished by Claude after three lane
    iterations (ADR-0007): the lane's argv put the timeout last and its parser expected
    `name: returns` without the space crosshair prints."""
    import re as _re
    reports = []
    for name, signature in (sigs or {}).items():
        if name.startswith("_") or ("->" not in signature and ":" not in signature.split("(", 1)[-1]):
            continue
        argv = ["crosshair", "diffbehavior", "--per_condition_timeout", str(timeout), f"{old}.{name}", f"{new}.{name}"]
        _code, output = runner(argv, cwd)
        counterexamples = []
        given = old_ret = new_ret = None
        for line in (output or "").splitlines():
            s = line.strip()
            if s.startswith("Given:"):
                if given is not None and old_ret and new_ret:
                    counterexamples.append({"given": given, "old": old_ret, "new": new_ret})
                given, old_ret, new_ret = s[len("Given:"):].strip(), None, None
                continue
            m = _re.match(r"^(\S+)\.(\w+)\s*:\s*(.+)$", s)
            if m and m.group(2) == name:
                if m.group(1) == old:
                    old_ret = m.group(3).strip()
                elif m.group(1) == new:
                    new_ret = m.group(3).strip()
        if given is not None and old_ret and new_ret:
            counterexamples.append({"given": given, "old": old_ret, "new": new_ret})
        reports.append({"function": name, "counterexamples": counterexamples})
    return reports


def equivalence_verdict(specs_green: bool, counterexamples: List[Dict], score_new: Dict, score_old: Dict) -> Tuple[bool, str]:
    """
    C-8.3 — determine equivalence verdict based on three conditions:
    1. specs must be green
    2. no counterexamples allowed
    3. per-clause mutation score for new must not be under original module's
    
    First failing condition is the reason.
    """
    if not specs_green:
        return (False, "specs red")
    
    if counterexamples:
        func_name = counterexamples[0].get("function", "unknown")
        return (False, f"counterexample in {func_name}")
    
    # Check mutation scores per clause
    for clause, old_score in score_old.items():
        new_score = score_new.get(clause, 0.0)
        if new_score < old_score:
            return (False, f"{clause} mutation score {new_score:.02f} under {old_score:.02f}")
    
    return (True, "equivalent")
