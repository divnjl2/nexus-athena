"""Perimeter layer, C-5: the substrate — the scheduler the box does not have. Red until lib/host.py exists."""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
GB = 1024 ** 3


def test_the_host_floors_park_a_dispatch_and_name_the_resource():
    """C-5.1 — under the RAM floor or a GPU under the VRAM floor: parked, the reason names the resource
    and both numbers; above both: admitted; a failing reader parks as unknown and says so."""
    from lib.host import host_admit, host_state
    st = host_state(read_mem=lambda: {"free": 3 * GB, "total": 64 * GB},
                    read_gpus=lambda: [{"index": 1, "name": "RTX 3090", "free": 12 * GB, "total": 24 * GB}])
    assert st["ram_free"] == 3 * GB and st["gpus"][0]["free"] == 12 * GB
    parked = host_admit(st, floors={"ram": 8 * GB, "vram": 2 * GB})
    assert parked["ok"] is False and "ram" in parked["reason"].lower() and "3.0" in parked["reason"] and "8.0" in parked["reason"]
    st2 = host_state(read_mem=lambda: {"free": 20 * GB, "total": 64 * GB},
                     read_gpus=lambda: [{"index": 1, "name": "RTX 3090", "free": 1 * GB, "total": 24 * GB}])
    v = host_admit(st2, floors={"ram": 8 * GB, "vram": 2 * GB}, gpu=1)
    assert v["ok"] is False and "vram" in v["reason"].lower() and "3090" in v["reason"] and "1.0" in v["reason"]
    st3 = host_state(read_mem=lambda: {"free": 20 * GB, "total": 64 * GB},
                     read_gpus=lambda: [{"index": 0, "name": "RTX 3060", "free": 1 * GB, "total": 12 * GB},
                                        {"index": 1, "name": "RTX 3090", "free": 10 * GB, "total": 24 * GB}])
    assert host_admit(st3, floors={"ram": 8 * GB, "vram": 2 * GB}, gpu=1)["ok"] is True
    assert host_admit(st3, floors={"ram": 8 * GB, "vram": 2 * GB}, gpu=0)["ok"] is False
    def boom():
        raise OSError("nvml unavailable")
    unknown = host_state(read_mem=lambda: {"free": 20 * GB, "total": 64 * GB}, read_gpus=boom)
    u = host_admit(unknown, floors={"ram": 8 * GB, "vram": 2 * GB}, gpu=1)
    assert u["ok"] is False and "unknown" in u["reason"].lower() and "nvml" in u["reason"].lower()
    # measured 28.09: the lane died of ERROR_COMMITMENT_LIMIT with RAM to spare — the commit floor is its own resource
    low = host_state(read_mem=lambda: {"free": 30 * GB, "total": 64 * GB, "commit_free": 5 * GB},
                     read_gpus=lambda: [{"index": 1, "name": "RTX 3090", "free": 10 * GB, "total": 24 * GB}])
    c = host_admit(low, floors={"ram": 8 * GB, "vram": 2 * GB, "commit": 30 * GB}, gpu=1)
    assert c["ok"] is False and "commit" in c["reason"].lower() and "5.0" in c["reason"] and "30.0" in c["reason"]
    assert host_admit(low, floors={"ram": 8 * GB, "vram": 2 * GB}, gpu=1)["ok"] is True   # no commit floor asked: not applied
    blind = host_state(read_mem=lambda: {"free": 30 * GB, "total": 64 * GB},
                       read_gpus=lambda: [{"index": 1, "name": "RTX 3090", "free": 10 * GB, "total": 24 * GB}])
    b = host_admit(blind, floors={"commit": 30 * GB}, gpu=1)
    assert b["ok"] is False and "unknown" in b["reason"].lower() and "commit" in b["reason"].lower()
    from lib.host import parse_floors
    assert parse_floors("ram=8G,vram=2G") == {"ram": 8 * GB, "vram": 2 * GB}
    assert parse_floors("ram=512M") == {"ram": 512 * 1024 ** 2}


def test_a_lane_with_no_state_is_woken_through_the_router_before_it_is_parked():
    """C-5.2 — the wake goes to the router with the lane's model and a one-token body; health 200 within
    the timeout is woken; never is parked with the seconds waited."""
    from lib.host import wake_request, wake_wait
    req = wake_request("omnicoder-9b", router="http://127.0.0.1:8420")
    assert req["url"] == "http://127.0.0.1:8420/v1/chat/completions" and req["body"]["model"] == "omnicoder-9b"
    assert req["body"]["max_tokens"] == 1 and req["body"]["messages"]
    clock = iter([0.0, 5.0, 10.0, 15.0, 20.0, 25.0])
    healths = iter([503, 503, 200])
    woken = wake_wait(lambda: next(healths), timeout_s=60.0, now=lambda: next(clock), sleep=lambda s: None)
    assert woken["woken"] is True and woken["waited_s"] >= 10.0
    clock2 = iter([0.0, 30.0, 61.0, 62.0, 63.0])
    parked = wake_wait(lambda: 503, timeout_s=60.0, now=lambda: next(clock2), sleep=lambda s: None)
    assert parked["woken"] is False and parked["waited_s"] >= 60.0 and "parked" in parked["reason"]


def test_strangers_on_a_gpu_are_named_against_its_allow_list_and_reported_once():
    """C-5.3 — an executable matching no allow pattern of the GPU is a stranger; the bd command names
    GPU, pid and executable; the same pid next time yields nothing."""
    import json
    from lib.host import stranger_bead_command, strangers, strangers_once
    inv = json.loads((ROOT / "features" / "perimeter-layer" / "gpus.json").read_text(encoding="utf-8"))
    procs = [{"gpu": 1, "pid": 34396, "exe": r"D:\llama-b11165-cuda\llama-server.exe"},
             {"gpu": 1, "pid": 4544, "exe": r"D:\llama-cuda-b9089\llama-server.exe"},
             {"gpu": 1, "pid": 12900, "exe": r"C:\Users\x\AppData\Local\Programs\Python\Python311\python.exe"},
             {"gpu": 0, "pid": 7552, "exe": r"C:\Users\x\AppData\Local\Programs\Python\Python312\python.exe"}]
    out = strangers(procs, inv)
    assert [(s["gpu"], s["pid"]) for s in out] == [(1, 4544), (1, 12900)]
    cmd = stranger_bead_command("perimeter-layer", out[0])
    assert cmd[:2] == ["bd", "create"] and "4544" in " ".join(cmd) and "llama-cuda-b9089" in " ".join(cmd) and "3090" in " ".join(cmd)
    assert any(x.startswith("athena:perimeter-layer:stranger:") for x in cmd)
    seen: set = set()
    first = strangers_once(out, seen, slug="perimeter-layer")
    assert len(first) == 2 and strangers_once(out, seen, slug="perimeter-layer") == []
    # an unknown pid with no executable (another account) is still a stranger, named by pid
    ghost = strangers([{"gpu": 1, "pid": 23476, "exe": ""}], inv)
    assert ghost and ghost[0]["pid"] == 23476


def test_a_heavy_gate_runs_under_the_governor_when_present_and_says_so():
    """C-5.4 — the governor found: argv prefixed with the commit ceiling and kill-on-close; not found:
    argv unchanged and the note says ungoverned."""
    from lib.host import governed_argv
    argv = ["python", "-m", "cosmic_ray", "exec", "s.toml"]
    g = governed_argv(argv, ceiling_gb=12, which=lambda name: r"C:\ProgramData\athena\bin\procgov.exe")
    assert g["argv"][0].endswith("procgov.exe") and g["argv"][-5:] == argv and g["governed"] is True
    joined = " ".join(g["argv"])
    assert "--maxjobmem" in joined and "12G" in joined and "--terminate-job-on-exit" in joined and "-r" in g["argv"]
    u = governed_argv(argv, ceiling_gb=12, which=lambda name: None)
    assert u["argv"] == argv and u["governed"] is False and "ungoverned" in u["note"]

