import re
from collections import defaultdict


def test_function_name(code):
    """Extract the test function name from source code. Returns empty string for 
    multiple functions or no test."""
    # Check if code parses
    try:
        compile(code, '<test_candidate>', 'exec')
    except SyntaxError:
        return ""
    
    # Find def statements
    funcs = re.findall(r'^def\s+(\w+)\s*\(', code, re.MULTILINE)
    if len(funcs) != 1:
        return ""
    
    return funcs[0]


def normalize_source(source):
    """Normalize source code for clustering by removing whitespace variations."""
    return re.sub(r'\s+', ' ', source).strip()


def adapt_to_match_clause(source, clause=""):
    """Helper: check if clause in the form C-X.Y appears in source."""
    if not clause or not source:
        return True
    
    parts = clause.split('-')
    if len(parts) >= 2:
        clause_num = parts[1]
        return re.search(r'C-' + re.escape(clause_num), source, re.IGNORECASE) is not None
    return True


def admissible(source, run_result, clause=""):
    """Determine if a candidate test is admissible.
    
    A candidate is admissible when:
    - It parses successfully
    - It defines exactly one test function that names the clause
    - Its run on the current code is red for a failure (not an error, not a skip)
    """
    # Check if code parses
    try:
        compile(source, '<test_candidate>', 'exec')
    except SyntaxError:
        return "parse"
    
    funcs = re.findall(r'^def\s+(\w+)\s*\(', source, re.MULTILINE)
    
    # Must have at least one function
    if len(funcs) < 1:
        return "one test"
    
    # Check exit code - error case
    outcome = run_result.get("exit")
    tail = run_result.get("tail", "")
    
    # Error (exit code 2)
    if outcome == 2:
        return "error"
    
    # ImportError check
    if "ImportError" in tail:
        return "error"
    
    # Skip check
    if "skipped" in tail.lower():
        return "skip"
    
    # Passed - this is not admissible (should fail the test)
    if "passed" in tail.lower():
        return "passes"
    
    # Check if clause provided
    if clause:
        parts = clause.split('-')
        if len(parts) >= 2:
            clause_num = parts[1]
            # Must have exactly one function and clause must be in docstring
            if len(funcs) != 1:
                return "one test"
            
            name = funcs[0]
            # Find docstring - account for optional () after function name
            docstring_pattern = r'^def\s+' + re.escape(name) + r'\s*\(\s*\)*\s*:\s*"""(.*?)"""'
            doc_match = re.search(docstring_pattern, source, re.DOTALL | re.MULTILINE)
            
            if not doc_match or not doc_match.group(1):
                # No docstring - not admissible
                return "one test"
            
            if not re.search(r'C-' + re.escape(clause_num), doc_match.group(1), re.IGNORECASE):
                return "one test"
    
    # Must have exactly one function
    if len(funcs) != 1:
        return "one test"
    
    return ""


def choose_test(candidates, clause=""):
    """Choose the largest cluster's representative from admissible candidates.
    
    Clusters by normalized source. Returns the representative of the largest
    cluster that are admissible (return empty string on admissible()).
    """
    # Filter and categorize candidates
    admissible_results = []
    rejected = []
    
    for cand in candidates:
        source = cand.get("source", "")
        run = cand.get("run", {})
        
        result = admissible(source, run, clause)
        
        cluster_info = {
            "source": source,
            "run": run,
            "normalized": normalize_source(source)
        }
        
        if result == "":
            admissible_results.append(cluster_info)
        else:
            rejected.append(cluster_info)
    
    # Cluster by normalized source
    clusters = defaultdict(list)
    for cand in admissible_results:
        key = cand["normalized"]
        clusters[key].append(cand)
    
    # Find largest cluster
    if not clusters:
        return {"source": "", "cluster_size": 0, "admissible": 0, "rejected": 0, "representatives": []}
    
    largest_cluster = max(clusters.items(), key=lambda x: len(x[1]))
    cluster_key = largest_cluster[0]
    
    representatives = []
    for cluster_source in list(set([cand["source"] for cand in largest_cluster[1]])):
        representatives.append({"source": cluster_source})
    
    return {
        "source": largest_cluster[1][0]["source"],
        "cluster_size": len(largest_cluster[1]),
        "admissible": len(admissible_results),
        "rejected": len(rejected),
        "representatives": representatives
    }
