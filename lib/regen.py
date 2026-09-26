"""Regeneration module for module equivalence checking."""
from typing import Any, Callable, Dict, List, Optional, Tuple
import subprocess
import time


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


def diff_report(
    sigs: Dict[str, str],
    old: str,
    new: str,
    runner: Callable[[List[str], str], Tuple[int, str]],
    cwd: str,
    timeout: float
) -> List[Dict[str, Any]]:
    """
    C-8.2 — run the behaviour diff per public typed function.
    Skip untyped or private functions.
    Record counterexamples from the runner output.
    """
    reports = []
    
    for func_name, signature in sigs.items():
        # Skip private functions (start with underscore)
        if func_name.startswith("_"):
            continue
        
        # Skip untyped signatures (no type hints - no -> in signature)
        has_types = "->" in signature
        if not has_types:
            continue
        
        # Build command - use "old.func: new.func" format
        cmd = ["crosshair", "diffbehavior", f"{old}.{func_name}: {new}.{func_name}"]
        cmd.extend(["--per_condition_timeout", str(int(timeout * 1000))])
        cmd.append("--timeout")
        cmd.append(str(int(timeout * 1000)))
        
        # Execute in specified directory
        exit_code, output = runner(cmd, cwd)
        
        # Parse counterexamples from output
        counterexamples = []
        lines = output.split("\n")
        
        given = ""
        old_ret = ""
        new_ret = ""
        
        for line in lines:
            stripped_line = line.strip()
            
            # Line 1: "Given: (...)"
            if stripped_line.startswith("Given:"):
                parts = stripped_line.split("Given: ", 1)
                if len(parts) >= 2:
                    given = parts[1]
            # Parse the return statements - look for lines with the function name
            elif func_name.lower() in stripped_line and ": returns" in stripped_line:
                parts = stripped_line.split(": returns", 1)
                if len(parts) >= 2:
                    prefix = parts[0].rstrip()
                    # The prefix is like "old.func_name" or "new.func_name"
                    # Remove the function name and check what remains
                    prefix_lower = prefix.lower()
                    func_lower = func_name.lower()
                    if func_lower in prefix_lower:
                        # Extract the part before the last occurrence of func_name
                        idx = prefix_lower.rfind(func_lower)
                        before_part = prefix_lower[:idx].strip()
                        if before_part == "old":
                            old_ret = parts[1].strip()
                        elif before_part == "new":
                            new_ret = parts[1].strip()
        
        if given and old_ret and new_ret:
            counterexamples.append({
                "given": given,
                "old": f"returns {old_ret}",
                "new": f"returns {new_ret}"
            })
        
        reports.append({
            "function": func_name,
            "counterexamples": counterexamples
        })
    
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
