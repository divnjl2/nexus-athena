#host

# Host state and floor checking for dispatch/gate admission.

GB = 1024 ** 3
MB = 1024 ** 2


def parse_floors(text: str) -> dict:
    """Parse floor specifications like 'ram=8G,vram=2G' or 'ram=512M'."""
    result = {}
    import re
    for item in text.split(','):
        item = item.strip()
        match = re.match(r'^([^=]+)=(\d+)([GMgmg])$', item)
        if match:
            key, value, unit = match.groups()
            value = int(value)
            if unit.upper() in ('G', 'g'):
                value *= GB
            elif unit.upper() in ('M', 'm'):
                value *= MB
            result[key.lower()] = value
    return result


class HostState:
    """Host state capturing RAM and GPU resources."""
    def __init__(self, *, read_mem=None, read_gpus=None):
        self._read_mem = read_mem
        self._read_gpus = read_gpus
    
    @property
    def ram_free(self):
        if self._read_mem is None:
            return 0
        if callable(self._read_mem):
            try:
                data = self._read_mem()
                return data.get("free", 0)
            except Exception:
                return 0
        return self._read_mem.get("free", 0)
    
    @property
    def commit_free(self):
        """the commit charge headroom in bytes (Windows: pagefile-backed limit minus charge), None when
        the reader does not know it — measured 28.09: a lane dies of ERROR_COMMITMENT_LIMIT with RAM free"""
        if self._read_mem is None:
            return None
        try:
            data = self._read_mem() if callable(self._read_mem) else self._read_mem
        except Exception:
            return None
        v = (data or {}).get("commit_free")
        return None if v is None else int(v)

    @property
    def gpus(self):
        if self._read_gpus is None:
            return []
        if callable(self._read_gpus):
            try:
                return self._read_gpus()
            except Exception:
                return None
        return list(self._read_gpus) if self._read_gpus else []
    
    def __getitem__(self, key):
        d = dict(self.__dict__)
        d.update({
            "ram_free": self.ram_free,
            "commit_free": self.commit_free,
            "gpus": self.gpus
        })
        return d[key]


def host_state(read_mem=None, read_gpus=None):
    """Create a host state object."""
    return HostState(read_mem=read_mem, read_gpus=read_gpus)


def wake_request(model, router="http://127.0.0.1:8420"):
    """
    Build a wake request dict for the router.
    """
    return {
        "url": f"{router}/v1/chat/completions",
        "body": {
            "model": model,
            "max_tokens": 1,
            "messages": [{"role": "system", "content": ""}]
        }
    }


def wake_wait(check_fn, timeout_s=60.0, now=None, sleep=lambda s: None):
    """
    Wake a lane by polling the health endpoint through router.
    """
    if now is None:
        import time
        now = lambda: time.time()
    
    waited_s = 0.0
    previous_now_value = now()
    
    while True:
        waited_s = now()
        status = check_fn()
        
        if status == 200:
            return {"woken": True, "waited_s": waited_s}
        
        if waited_s > timeout_s:
            return {"woken": False, "waited_s": waited_s, "reason": "parked; timed out after {:.1f}s".format(waited_s)}
        
        sleep(waited_s - previous_now_value)
        previous_now_value = waited_s


def host_admit(st, floors, gpu=None):
    """
    Check if dispatch should proceed based on host resource floors.
    """
    result = {"ok": False, "reason": ""}
    
    ram_free = st.ram_free
    ram_floor = floors.get("ram", 0)
    
    if ram_free < ram_floor:
        result["reason"] = f"parked; ram floor {ram_floor / GB:.1f}G, available {ram_free / GB:.1f}G"
        return result

    # C-5.1: the commit floor — the limit a Windows box actually hits first when three model servers share it
    commit_floor = floors.get("commit", 0)
    if commit_floor:
        commit_free = st.commit_free
        if commit_free is None:
            result["reason"] = f"parked; unknown resource, commit charge unreadable (floor {commit_floor / GB:.1f}G)"
            return result
        if commit_free < commit_floor:
            result["reason"] = f"parked; commit floor {commit_floor / GB:.1f}G, available {commit_free / GB:.1f}G"
            return result
    
    if gpu is not None:
        gpus = st.gpus
        if gpus is None:
            result["reason"] = "parked; unknown resource, nvml unavailable"
            return result
        
        target_gpu = None
        for i, gpu_info in enumerate(gpus):
            if gpu_info.get("index") == gpu:
                target_gpu = gpu_info
                break
        
        if target_gpu is None:
            result["reason"] = f"parked; unknown gpu={gpu}"
            return result
        
        vram_free = target_gpu.get("free", 0)
        vram_floor = floors.get("vram", 0)
        
        if vram_free < vram_floor:
            gpu_name = target_gpu.get("name", f"GPU{gpu}")
            result["reason"] = f"parked; vram on {gpu_name} floor {vram_floor / GB:.1f}G, available {vram_free / GB:.1f}G"
            return result
    
    result["ok"] = True
    result["reason"] = "admitted"
    return result


def _norm_path(text) -> str:
    """lower-case, forward slashes: the inventory's patterns are substrings of the executable path"""
    return str(text or "").replace("\\", "/").lower()


def strangers(procs, inventory) -> list:
    """PURE (C-5.3): the compute processes whose executable matches no allow pattern of their GPU, in the
    order given, each carrying the GPU's name from the inventory; a process without an executable (another
    account's) is a stranger named by its pid. The inventory is gpus.json as a whole or its "gpus" map."""
    gpus = inventory.get("gpus", inventory) if isinstance(inventory, dict) else {}
    out = []
    for proc in procs or []:
        gpu = proc.get("gpu")
        entry = gpus.get(str(gpu)) or gpus.get(gpu) or {}
        if entry.get("watch", True) is False:
            continue          # the display card: every desktop app renders there; not inventoried (review 27.09)
        patterns = [_norm_path(x) for x in (entry.get("allow") or []) if str(x).strip()]
        exe = _norm_path(proc.get("exe"))
        if exe and any(pat in exe for pat in patterns):
            continue
        out.append({**proc, "gpu_name": entry.get("name", f"GPU {gpu}")})
    return out


def stranger_bead_command(slug: str, stranger: dict) -> list:
    """PURE (C-5.3): the bd command that opens a bead for one stranger — GPU, pid and executable in the
    title, the key in a label so the same stranger is never opened twice."""
    gpu = stranger.get("gpu")
    pid = stranger.get("pid")
    exe = stranger.get("exe") or "(no executable visible: another account)"
    name = stranger.get("gpu_name", f"GPU {gpu}")
    title = f"stranger on GPU {gpu} ({name}): pid {pid} {exe}"
    return ["bd", "create", title, "--label", "athena", "--label", f"athena:{slug}:stranger:{gpu}:{pid}", "--priority", "1",
            "-d", f"C-5.3: a compute process outside the allow-list of GPU {gpu}; reported, never killed. exe={exe}"]


def strangers_once(strangers_found, seen: set, *, slug: str = "perimeter-layer") -> list:
    """PURE (C-5.3): one command per stranger not seen before (keyed by GPU and pid); `seen` is updated."""
    commands = []
    for s in strangers_found or []:
        key = f"{s.get('gpu')}:{s.get('pid')}"
        if key in seen:
            continue
        seen.add(key)
        commands.append(stranger_bead_command(slug, s))
    return commands

def governed_argv(argv: list[str], ceiling_gb: int, which: callable) -> dict:
    """
    C-5.4: wrap argv with the process governor when found, otherwise leave ungoverned.
    
    Args:
        argv: the command-line argv list
        ceiling_gb: memory ceiling in GB for --maxjobmem
        which: function that returns the governor path if found, None otherwise
    
    Returns:
        dict with keys: argv, governed, note
    """
    result = {
        "argv": argv.copy(),
        "governed": False,
        "note": ""
    }
    
    # review 29.09: the lane asked `which` for the result dict itself (the spec's fake accepted anything);
    # the governor is looked up by name, procgov.exe on this host
    governor = None
    if which is not None:
        for name in ("procgov", "procgov.exe"):
            governor = which(name)
            if governor:
                break
    
    if governor is not None:
        result["governed"] = True
        result["note"] = ""
        result["argv"] = [
            str(governor),
            f"--maxjobmem={ceiling_gb}G",
            "--terminate-job-on-exit",
            "-r", "-q", "--nogui", "--",
            *result["argv"]
        ]
    else:
        result["governed"] = False
        result["note"] = "ungoverned"
    
    return result
