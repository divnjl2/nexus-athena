import ast


def normalize_source(source):
    """Normalize source by removing all whitespace and comments; unparsable stays as-is."""
    # First, check if the source is valid Python
    try:
        ast.parse(source)
    except:
        # Unparsable source stays as-is
        return source
    
    # Remove comments first, then normalize whitespace
    lines = source.split('\n')
    normalized = []
    for line in lines:
        # Find and remove # comments (simple approach for this test case)
        hash_pos = line.find('#')
        if hash_pos >= 0:
            line = line[:hash_pos]
        normalized.append(line)
    
    # Now normalize whitespace
    cleaned = '\n'.join(normalized)
    return ''.join(cleaned.split())


def cluster_attempts(attempts):
    """Cluster attempts by (normalized source, which checks passed)."""
    clusters = {}
    
    for idx, attempt in enumerate(attempts):
        if not attempt.get('landed', False):
            continue
        
        source_map = attempt.get('sources', {})
        checks = attempt.get('checks', [])
        source = ''
        
        for src in source_map.values():
            source = normalize_source(src)
            break
        
        # Get tuple of passed check commands
        checks_passed = tuple(c['cmd'] for c in checks if c['exit'] == 0)
        key = (source, checks_passed)
        
        if key not in clusters:
            clusters[key] = {'members': [], 'green': False, 'representative': None}
        
        cluster = clusters[key]
        cluster['members'].append(idx)
        
        if attempt.get('green', False):
            cluster['green'] = True
        
        # Representative is the member with lowest duration_ms
        if cluster['representative'] is None:
            cluster['representative'] = idx
        elif attempt['duration_ms'] < attempts[cluster['representative']]['duration_ms']:
            cluster['representative'] = idx
    
    # Convert to list of dicts with size
    result = []
    for key, cluster in clusters.items():
        result.append({
            'key': key,
            'members': list(cluster['members']),  # convert to list, order preserved
            'green': cluster['green'],
            'representative': cluster['representative']
        })
    
    return result


def select_attempt(attempts):
    """Select the best attempt based on cluster rules."""
    if not attempts:
        return {'index': None}
    
    clusters = cluster_attempts(attempts)
    
    if not clusters:
        return {'index': None}
    
    # Count number of passed checks per cluster
    check_counts = {}
    for cluster in clusters:
        key = cluster['key']
        check_counts[key] = len(cluster['key'][1])
    
    # Count green clusters
    green_count = sum(1 for c in clusters if c['green'])
    
    # Determine the winning cluster
    if green_count > 0:
        # Among green clusters, the largest wins
        green_clusters = [c for c in clusters if c['green']]
        best = max(green_clusters, key=lambda c: len(c['members']))
    else:
        # No green clusters: largest wins, then most passed checks as tiebreaker
        best = max(clusters, key=lambda c: (check_counts[c['key']], len(c['members'])))
    
    best_size = len(best['members'])
    
    # Get one representative per cluster (the cluster member with lowest duration_ms)
    all_representatives = []
    for cluster in clusters:
        rep_idx = cluster['representative']
        all_representatives.append({'index': rep_idx})
    
    return {
        'index': best['representative'],
        'cluster_size': best_size,
        'representatives': all_representatives,
        'green_clusters': green_count
    }
