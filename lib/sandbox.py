def sandbox_config(worktree, allow_read, lane_ports):
    """
    Create sandbox configuration with filesystem and network restrictions.
    
    Args:
        worktree: Path to the worktree directory (allow write access)
        allow_read: List of paths allowed for read access
        lane_ports: List of network ports allowed (lane ports)
    
    Returns:
        dict: Sandbox configuration with filesystem and network settings
    """
    import json
    
    # Filesystem: allow write to worktree only, allow read to toolchain + worktree
    allow_read_with_worktree = set(allow_read) | {worktree}
    
    cfg = {
        "filesystem": {
            "allowWrite": [worktree],
            "allowRead": list(allow_read_with_worktree)
        },
        "network": {
            "allowedDomains": [],
            "allowLocalPorts": lane_ports
        }
    }
    
    return cfg


def sandbox_argv(argv, config_path):
    """
    Wrap command arguments in sandbox runtime prefix.
    
    Args:
        argv: List of command arguments
        config_path: Path to sandbox configuration file
    
    Returns:
        list: Command arguments prefixed with sandbox runtime
    """
    return ["srt", "--settings", config_path, "--"] + argv


def sandbox_decision(available, flag):
    """
    Decide whether to run sandboxed based on availability and user flag.
    
    Args:
        available: bool indicating if sandbox is available
        flag: User-provided flag ("required", "on", "off")
    
    Returns:
        tuple: (run, has_sandbox, message)
    """
    # "off" means never use sandbox
    if flag == "off":
        return (True, False, "sandbox off")
    
    # "required" means: if available, sandbox; if not, don't run
    if flag == "required":
        if available:
            return (True, True, "sandboxed")
        else:
            return (False, False, "sandbox required but unavailable")
    
    # "on" means: if available, sandbox; if not, run unsandboxed
    if flag == "on":
        if available:
            return (True, True, "sandboxed")
        else:
            return (True, False, "sandbox unavailable, running unsandboxed")
    
    # Default fallback (shouldn't happen based on test cases)
    return (True, False, "sandbox off")
