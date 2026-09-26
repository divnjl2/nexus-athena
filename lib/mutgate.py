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


def mutation_verdict(scores, threshold, added):
    """
    C-1.3 — when score below threshold on added lines or survivor on added line: refuse at mutation stage,
    naming clause and first survivor; when under threshold on untouched lines only: advisory.
    
    scores: {clause_id: {score, killed, total, survivors}}
    threshold: float
    added: {filename: [line_nums]} lines that were added by the task
    
    Returns: verdict dict with ok, stage, clause, survivor, advisory
    """
    # Build set of added lines per file
    added_lines = set()
    for fname, lines in added.items():
        for line in lines:
            added_lines.add((fname, line))
    
    # Check if any clause has a survivor on an added line
    failing_clauses = []
    first_survivor = None
    clauses_under_threshold = []
    
    for clause_id, data in scores.items():
        score = data.get("score", 1.0)
        
        # Track clauses under threshold
        if score < threshold:
            clauses_under_threshold.append(clause_id)
        
        # Check if clause has survivors on added lines
        for survivor in data.get("survivors", []):
            path = survivor.get("path", "")
            line = survivor.get("line", 0)
            kind = survivor.get("kind", "")
            
            for (added_fname, added_line) in added_lines:
                if path == added_fname and line == added_line:
                    failing_clauses.append(clause_id)
                    first_survivor = {
                        "path": path,
                        "line": line,
                        "kind": kind
                    }
                    break
    
    # Determine the outcome
    if failing_clauses:
        # There is a survivor on an added line → reject
        return {
            "ok": False,
            "stage": "mutation",
            "clause": failing_clauses[0],
            "survivor": first_survivor,
            "advisory": []
        }
    else:
        # No survivor on an added line; check if under threshold
        if clauses_under_threshold:
            # Under threshold on untouched lines → advisory
            return {
                "ok": True,
                "stage": None,
                "clause": None,
                "survivor": None,
                "advisory": clauses_under_threshold
            }
        else:
            # No survivors on added lines and not under threshold → ok
            return {
                "ok": True,
                "stage": None,
                "clause": None,
                "survivor": None,
                "advisory": []
            }


def sealed_summary(tail):
    """
    C-1.4 — reduce a sealed run to pass/fail per test id; no assertion text, diffs, or tracebacks.
    
    tail: string of tail output containing test results lines and failures
    
    Returns: lines like 'PASS test_id' or 'FAIL test_id', summary, and 'no tests ran' if empty.
    """
    if not tail.strip():
        return "no tests ran"
    
    failed_lines = []
    passed_lines = []
    passed = 0
    failed = 0
    
    for line in tail.splitlines():
        clean_line = line.strip()
        
        # Look for lines with "::" followed by a test name pattern (test_name PASSED/FAILED)
        # Format: tests/file.py::test_name PASSED or tests/file.py::test_name FAILED
        if "::" not in clean_line:
            continue
        
        dcolon = clean_line.rfind("::")
        if dcolon == -1:
            continue
        
        path_part = clean_line[:dcolon]
        after_part = clean_line[dcolon+2:]
        parts = after_part.strip().split()
        
        if len(parts) < 1:
            continue
        
        # Check if this is an actual test result line (has PASSED or ends with FAILED)
        result_word = parts[-1] if len(parts) > 1 else parts[0] if parts[0] in ("PASSED", "FAILED", "XFAIL", "XPASS") else None
        
        if "PASSED" not in parts and (not result_word or result_word not in ("PASSED", "FAILED", "XFAIL", "XPASS", "SKIPPED")):
            continue
        
        # Skip the summary line at the end
        if " in " in clean_line and "=" in clean_line.split("=")[-1]:
            continue
        
        # Build full test id
        test_id = f"{path_part}.py" + ".py" if not path_part.endswith(".py") else path_part
        if not path_part.endswith(".py"):
            test_id = f"{path_part}.py"
        
        if "::test_" in clean_line or "test_" in after_part:
            test_name = after_part.split()[0] if after_part.split() else ""
        else:
            test_name = test_id.split(".")[-1]
        
        # Form the result line
        if result_word == "PASSED":
            passed_lines.append(f"PASS {path_part}::{test_name}")
            passed += 1
        else:
            failed_lines.append(f"FAIL {path_part}::{test_name}")
            failed += 1
    
    result_lines = failed_lines + passed_lines
    result_lines.append(f"{failed} failed, {passed} passed")
    
    return "\n".join(result_lines)