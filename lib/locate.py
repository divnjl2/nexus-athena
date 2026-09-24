import os
import json
import re
from collections import Counter


def repo_map(root, budget_chars=10000):
    """Build a repo map of Python files with top-level definitions within character budget."""
    total_chars = 0
    entries = []
    
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip vendored directories
        skip_dirs = {'node_modules', 'venv', '__pycache__', '.git', '__pypackages__'}
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        
        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            
            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, root).replace('\\', '/')
            
            # Parse the file for function and class definitions
            lines = []
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        lines.append(line)
            except:
                continue
            
            # Parse top-level definitions (functions and classes at module level)
            definitions = []
            for line in lines:
                # Skip lines with indentation (nested inside class/function)
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                
                # Check if this line has leading spaces
                if len(line) - len(line.lstrip()) > 0:
                    continue
                
                def_name = None
                # Look for function definitions (only at top-level)
                func_match = re.match(r'^def\s+(\w+)\s*\(', stripped)
                if func_match:
                    def_name = func_match.group(1)
                # Look for class definitions (only at top-level)
                cls_match = re.match(r'^class\s+(\w+)', stripped)
                if cls_match:
                    def_name = cls_match.group(1)
                
                if def_name:
                    definitions.append(def_name)
            
            # Count total lines in file
            total_lines = len(lines)
            
            # Estimate character count for this entry
            entry_content = f"{rel_path} (repr: {', '.join(definitions)}, {total_lines} lines)\n"
            entry_len = len(entry_content)
            
            # Skip if this entry already exceeds budget
            if total_chars + entry_len > budget_chars:
                continue
            
            entries.append(entry_content.rstrip())
            total_chars += len(entry_content.rstrip())
    
    text = ''.join(entries)
    
    # Support implicit module loading
    # If empty, return empty string; otherwise indicate truncation
    if not text.strip():
        return ""
    
    # For tight budgets, the output should end with ...
    if budget_chars <= len(text.rstrip()) + 3:
        while not text.rstrip().endswith("..."):
            text = text.rstrip()[:-3] + "..."
            if len(text.split("...")[0]) < 3:
                break
    
    return text.rstrip()


def merge_votes(votes_list, top=None):
    """Merge votes from multiple samples by count then first mention."""
    if not votes_list:
        return []
    
    # Concatenate all votes and count occurrences
    counter = Counter()
    for vote_set in votes_list:
        if isinstance(vote_set, list):
            counter.update(vote_set)
    
    # Sort by count (descending), then by first mention (ascending)
    # First mention order is preserved by inserting order in iteration
    items = []
    seen = set()
    for i, v in enumerate(votes_list):
        if isinstance(v, list):
            for item in v:
                if item not in seen:
                    seen.add(item)
                    items.append((i, item))
    
    # Get order of first appearance
    first_app_order = {item: idx for idx, item in enumerate(items)}
    
    # Sort: by count descending, then by first appearance ascending
    sorted_items = sorted(counter.items(), key=lambda x: (-x[1], first_app_order.get(x[0], float('inf'))))
    
    result = [item[0] for item in sorted_items]
    
    if top:
        result = result[:top]
    
    return result


def parse_files_reply(reply):
    """Parse a files reply from a localiser, handling various formats."""
    reply = reply.strip()
    
    # Try to parse as JSON array
    try:
        # Remove markdown code blocks if present
        text = reply
        if '```' in reply:
            match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', reply, re.DOTALL)
            if match:
                text = match.group(1)
        
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError:
        pass
    
    # Check for inline JSON array
    json_match = re.search(r'\[.*?\]', reply)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if isinstance(data, list):
                return data
            return []
        except json.JSONDecodeError:
            pass
    
    # Try to parse as a list of strings (bullet points or quoted)
    lines = reply.split('\n')
    result = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove bullet point markers like "- " or "* " or "1. "
        if line.startswith('- '):
            line = line[2:]
        elif line.startswith('* '):
            line = line[2:]
        elif line.startswith('1. '):
            line = line[4:]
        
        # Extract file paths from the line
        if '"' in line:
            # Quoted strings
            match = re.search(r'"([^"]+)"', line)
            if match:
                result.append(match.group(1))
        elif line.lower().endswith('.py'):
            result.append(line)
    
    if result:
        return result
    
    return []
