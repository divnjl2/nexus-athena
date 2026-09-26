def sandbox_config(worktree, allow_read=(), lane_ports=(), proxy_range=(60080, 60089)):
    """C-10.1 — the sandbox-runtime settings for one executor: writes only in the worktree, reads on
    the toolchain paths given (the sandbox user is a different account: per-user installs need an
    explicit ACE), no network but loopback to the lane ports. On Windows loopback is permitted only
    inside the proxy port range (measured 26.09), so the ports named here are the executor's relays
    listening in that range."""
    wt = str(worktree).replace("\\", "/")
    reads = [wt] + [str(x).replace("\\", "/") for x in (allow_read or ()) if str(x)]
    seen = []
    for r in reads:
        if r not in seen:
            seen.append(r)
    ports = [int(x) for x in (lane_ports or ())]
    domains = []
    for port in ports:
        domains += [f"127.0.0.1:{port}", f"localhost:{port}"]
    return {
        "network": {"allowedDomains": domains, "deniedDomains": [], "allowLocalBinding": False},
        "filesystem": {"denyRead": [], "allowRead": seen, "allowWrite": [wt], "denyWrite": []},
        "windows": {"proxyPortRange": [int(proxy_range[0]), int(proxy_range[1])]},
    }

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


# --- C-10.3: the fence in the relay -------------------------------------------------------

DENY_COMMANDS = ("curl", "wget", "Invoke-WebRequest", "iwr", "ssh", "scp", "nc ", "ncat", "rm -rf /", "rm -rf ~",
                 "format ", "diskpart", "shutdown", "reg add", "reg delete", "schtasks", "net user", "powershell -enc",
                 "Remove-Item -Recurse", "git push", "pip install", "npm install", "del /s", "rd /s", "rmdir /s")


def _norm(path: str) -> str:
    import posixpath
    p = str(path or "").replace(chr(92), "/")
    return posixpath.normpath(p).lower()


def _inside(path: str, root: str) -> bool:
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r.rstrip("/") + "/")


def fence_call(call: dict, *, worktree: str, deny_read=(), allow_hosts=("127.0.0.1", "localhost")) -> tuple:
    """PURE (C-10.3): (ok, reason) for one tool call. write/edit only inside the worktree (a relative
    path is resolved against it); read never on a denied path; bash never with a deny-listed
    command, except a network tool aimed only at an allowed loopback host."""
    import posixpath
    name = str((call or {}).get("name") or "").lower()
    args = (call or {}).get("arguments") or {}
    if not isinstance(args, dict):
        return True, ""
    path = str(args.get("path") or args.get("file_path") or "")
    if name in ("write", "edit", "read") and path:
        full = path if (":" in path[:3] or path.startswith("/")) else posixpath.join(worktree.replace(chr(92), "/"), path)
        if name in ("write", "edit") and not _inside(full, worktree):
            return False, f"{name} outside the worktree: {path}"
        if name == "read" and any(_inside(full, d) for d in deny_read or ()):
            return False, f"read of a denied path: {path}"
    if name in ("bash", "shell", "run"):
        cmd = str(args.get("command") or args.get("cmd") or "")
        low = cmd.lower()
        for bad in DENY_COMMANDS:
            if bad.lower() in low:
                if bad.lower() in ("curl", "wget", "iwr", "invoke-webrequest") and allow_hosts and all(
                        any(h in tok for h in allow_hosts) for tok in low.split() if "://" in tok):
                    continue
                return False, f"command on the deny list: {bad.strip()}"
    return True, ""


def fence_completion(payload: dict, *, worktree: str, deny_read=(), allow_hosts=("127.0.0.1", "localhost")) -> tuple:
    """PURE (C-10.3): the completion with refused calls removed and a REFUSED line per refusal in the
    content; a choice left with no call ends as `stop`. Returns (payload, refused_count)."""
    import json as _json
    refused = 0
    for choice in (payload or {}).get("choices") or []:
        msg = choice.get("message") or {}
        calls = msg.get("tool_calls") or []
        if not calls:
            continue
        kept, notes = [], []
        for c in calls:
            fn = c.get("function") or {}
            try:
                args = _json.loads(fn.get("arguments") or "{}")
            except ValueError:
                args = {}
            ok, why = fence_call({"name": fn.get("name"), "arguments": args}, worktree=worktree, deny_read=deny_read, allow_hosts=allow_hosts)
            if ok:
                kept.append(c)
            else:
                refused += 1
                notes.append(f"REFUSED {fn.get('name')}: {why}")
        if notes:
            msg["content"] = ((msg.get("content") or "") + chr(10) + chr(10).join(notes)).strip()
        if kept:
            msg["tool_calls"] = kept
        else:
            msg.pop("tool_calls", None)
            choice["finish_reason"] = "stop"
    return payload, refused

