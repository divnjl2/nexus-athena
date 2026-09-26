"""Oracle helper functions for importing clauses, benchmarking, and forbidden commands."""
import configparser
import re
from typing import Optional


def importlinter_config(clauses: list, root_package: str) -> tuple[str, str]:
    """
    Render an importlinter contract from clauses and the command that checks it.
    
    - "shall not import" becomes a forbidden import rule
    - "layers" becomes a layers ordering rule
    """
    config = configparser.ConfigParser()
    
    # Add the main importlinter section
    config["importlinter"] = {}
    config["importlinter"]["root_package"] = root_package
    
    for clause in clauses:
        cid = clause["id"]
        text = clause["text"]
        
        # C-9.1: "shall not import" constraint
        if cid == "C-9.1":
            # Extract "THE {pkg} package shall not import {forbidden}"
            # e.g., "THE lib.oracles package shall not import lib.daemon."
            forbidden_match = re.search(r"THE\s+(\S+)\s+package\s+shall\s+not\s+import\s+(\S+)", text, re.IGNORECASE)
            if forbidden_match:
                config[f"importlinter:contract:{cid}"] = {}
                config[f"importlinter:contract:{cid}"]["type"] = "forbidden"
                orig_mod = forbidden_match.group(1)
                for_mod = forbidden_match.group(2)
                config[f"importlinter:contract:{cid}"]["source_modules"] = orig_mod
                config[f"importlinter:contract:{cid}"]["forbidden_modules"] = for_mod
        
        # C-9.2: layers constraint
        elif cid == "C-9.2":
            config[f"importlinter:contract:{cid}"] = {}
            config[f"importlinter:contract:{cid}"]["type"] = "layers"
            
            # Extract layers: "athena, lib.refinery, lib.dispatch"
            layers_match = re.search(r"layers\s+(.+?)\s+in", text, re.IGNORECASE)
            if layers_match:
                raw_layers = layers_match.group(1)
                # Split by comma and strip whitespace
                layers_list = [l.strip() for l in raw_layers.split(",") if l.strip()]
                # Clean each layer name
                clean_layers = []
                for layer in layers_list:
                    cleaned = re.sub(r"[^a-z0-9_.\s\-]", "", layer)
                    if cleaned:
                        clean_layers.append(cleaned)
                config[f"importlinter:contract:{cid}"]["layers"] = " ".join(clean_layers[:10])
        
        # C-9.3: ignored for import linter
        else:
            pass
    
    # Convert to string format like: [section]\nkey = value
    result_lines = []
    for section in config.sections():
        result_lines.append("[" + section + "]")
        for key, value in config[section].items():
            result_lines.append(key + " = " + str(value))
    return "\n".join(result_lines), "lint-imports --config importlinter.ini -q"


def benchmark_command(clause: dict, baseline: str) -> str:
    """
    Render a benchmark command for a clause with a time budget.
    
    - "within N% of its baseline" becomes a compare-fail benchmark command
    - Clause without a budget returns empty string
    """
    cid = clause.get("id", "")
    # Sanitize ID: replace hyphens and dots with underscores
    cid = re.sub(r"[^A-Z0-9_]", "_", cid)
    text = clause.get("text", "")
    
    # Extract the budget percentage (e.g., "20%")
    budget_match = re.search(r"within\s+(\d+)%\s+of\s+its\s+baseline", text, re.IGNORECASE)
    
    if not budget_match:
        return ""
    
    budget_pct = budget_match.group(1)
    return f"python -m pytest -m bench_{cid} --benchmark-compare={baseline} --benchmark-compare-fail=median:{budget_pct}% --benchmark-min-rounds=5 -q"


def forbidden_command(cmd: list) -> Optional[str]:
    """
    Check if a command would update a snapshot baseline.
    
    Returns error message if update flags detected, None otherwise.
    """
    snapshot_flags = ["--snapshot-update", "--force-regen"]
    benchmark_flags = ["--benchmark-save"]
    
    for flag in snapshot_flags:
        # Check for exact match or flag with value (e.g., --benchmark-save=x)
        if flag in cmd or any(c.startswith(flag) for c in cmd):
            return f"updates the snapshot baseline: {flag}"
    
    for flag in benchmark_flags:
        if flag in cmd or any(c.startswith(flag) for c in cmd):
            return f"updates the benchmark baseline: {flag}"
    
    return None
