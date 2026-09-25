"""
v3.16 the foundry — mutation as a gate (C-1) and drafted specs admitted, not trusted (C-2).
"""


def changed_targets(diff, clause_map):
    """
    C-1.1 — changed lines become per-clause targets through the map, test files are not
    targets, a line two clauses own goes to both, and unowned changed lines are reported.
    
    diff: {filename: [line_nums]}
    clause_map: {clause_id: {filename: [line_nums]}} (or {'clauses': {clause_id: ...}})
    
    Returns: (targets, unowned)
      targets: {clause_id: {filename: [line_nums]}}
      unowned: {filename: [line_nums]}
    """
    # Handle wrapper - dialect map has {'clauses': {clause_id: ...}}
    actual_map = clause_map.get("clauses", clause_map)
    
    # If diff is empty, return immediately
    if not diff:
        return {}, {}
    
    targets = {}
    unowned = {}
    
    # Check which non-test file lines are owned
    def is_test_file(name):
        return name.startswith("tests/") or name == "test_" or name.endswith("_test.py")
    
    # Check which non-test file lines are owned
    line_ownership = {}
    
    for filename, changed_lines in diff.items():
        if is_test_file(filename):
            continue
        
        line_ownership[filename] = {}
        for line in changed_lines:
            is_owned = False
            for owned in actual_map.values():
                if filename in owned and line in owned[filename]:
                    is_owned = True
                    break
            line_ownership[filename][line] = is_owned
    
    # Compute unowned - lines that are changed but not owned
    for filename, changed_lines in diff.items():
        if is_test_file(filename):
            continue
        
        for line in changed_lines:
            if not line_ownership.get(filename, {}).get(line, False):
                unowned.setdefault(filename, []).append(line)
    
    # Build targets - only include lines that are owned by clauses
    for clause_id, owned_lines in actual_map.items():
        if clause_id not in targets:
            targets[clause_id] = {}
        
        for filename, owned_line_nums in owned_lines.items():
            if is_test_file(filename):
                continue
            
            if filename not in diff:
                continue
            
            changed_in_file = set(diff[filename]) & set(owned_line_nums)
            if changed_in_file:
                targets[clause_id][filename] = sorted(list(changed_in_file))
    
    return targets, unowned


def clause_scores(results, targets):
    """
    C-1.2 — score = killed / total per clause over its target lines; survivors carry path,
    line and kind; a clause with no mutants has no score, not zero.
    
    results: [{path, line, kind, killed}]
    targets: {clause_id: {path: [lines]}}
    
    Returns: {clause_id: {score, killed, total, survivors}}
    """
    scores = {}
    
    # Group results by (path, line)
    line_results = {}
    for result in results:
        key = (result["path"], result["line"])
        if key not in line_results:
            line_results[key] = []
        line_results[key].append(result)
    
    # For each clause
    for clause_id, clause_lines in targets.items():
        # Build set of all (path, line) pairs in this clause's targets
        target_lines = set()
        for path, lines in clause_lines.items():
            for line in lines:
                target_lines.add((path, line))
        
        total = 0
        killed = 0
        survivors = []
        
        # Count all mutants for lines in this clause's target set
        for (path, line), mut_list in line_results.items():
            if (path, line) not in target_lines:
                continue
            for mutant in mut_list:
                total += 1
                if mutant["killed"]:
                    killed += 1
        
        # Find survivors
        for (path, line), mut_list in line_results.items():
            if (path, line) not in target_lines:
                continue
            for mutant in mut_list:
                if not mutant["killed"]:
                    survivors.append({
                        "path": mutant["path"],
                        "line": mutant["line"],
                        "kind": mutant["kind"]
                    })
        
        if total == 0:
            continue
        
        score = killed / total
        
        scores[clause_id] = {
            "score": score,
            "killed": killed,
            "total": total,
            "survivors": survivors
        }
    
    return scores
