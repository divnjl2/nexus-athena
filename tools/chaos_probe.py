"""The proof, by class: each probe reproduces a failure that used to take the box down and records what
happens now, as a JSON line in features/perimeter-layer/.athena/chaos.jsonl. Run by hand, never by the
daemon, and never while a dispatch is in flight — two of them kill the lane on purpose.

usage: python tools/chaos_probe.py <probe> [--gpu 1] [--lane omnicoder-9b] [--port 8006] [--router http://127.0.0.1:8420]
probes:
  hog        a process under procgov with a 4 GB commit ceiling allocates 8 GB: it must die, the lane must answer
  zombie     the lane's API process is killed hard: within 60 s no vLLM pid holds the GPU, the router relaunches it
  neighbour  6 GB of VRAM are held by a stranger while the lane restarts: the start must succeed with a lower util
  load429    concurrency above the router's limit: 429s above the limit, never a dead lane
  seed       a request with a seed past int32: the lane must answer, not 500
"""
from __future__ import annotations

import datetime
import json
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "features" / "perimeter-layer" / ".athena" / "chaos.jsonl"
PROCGOV = pathlib.Path(r"C:\ProgramData\athena\bin\procgov.exe")
VLLM_PY = pathlib.Path(r"D:\vllm-win-021\Scripts\python.exe")


def _arg(name: str, default: str) -> str:
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def _get(url: str, timeout: float = 5.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001 — the probe reports, it does not crash
        return 0, str(e)


def _post(url: str, body: dict, timeout: float = 120.0):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def _gpu_pids(gpu: int) -> list:
    p = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,gpu_uuid", "--format=csv,noheader"], capture_output=True, text=True)
    u = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"], capture_output=True, text=True)
    uuid = {int(l.split(",")[0]): l.split(",")[1].strip() for l in u.stdout.splitlines() if "," in l}.get(gpu, "")
    return [int(l.split(",")[0]) for l in p.stdout.splitlines() if "," in l and l.split(",")[1].strip() == uuid]


def _gpu_free_mb(gpu: int) -> int:
    p = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits", "-i", str(gpu)], capture_output=True, text=True)
    try:
        return int(p.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return -1


def _vllm_pids(model_dir_hint: str) -> list:
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { $_.CommandLine -match 'vllm.entrypoints' -and $_.CommandLine -match '" + model_dir_hint + "' } | ForEach-Object { $_.ProcessId }"],
                        capture_output=True, text=True)
    return [int(x) for x in ps.stdout.split() if x.strip().isdigit()]


def _health(port: int) -> int:
    return _get(f"http://127.0.0.1:{port}/health")[0]


def _record(probe: str, verdict: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "probe": probe, **verdict}
    with OUT.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))


def probe_hog(port: int) -> dict:
    before = _health(port)
    code = "import time\nb = bytearray(8 * 1024 ** 3)\ntime.sleep(5)\nprint('survived')\n"
    argv = [str(PROCGOV), "--maxjobmem", "4G", "-r", "--terminate-job-on-exit", "-q", "--", sys.executable, "-c", code]
    t0 = time.time()
    p = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    after = _health(port)
    gen = _post(f"http://127.0.0.1:{port}/v1/chat/completions", {"model": "omnicoder-9b", "max_tokens": 4, "messages": [{"role": "user", "content": "ok"}]})[0]
    return {"ok": p.returncode != 0 and "survived" not in (p.stdout or "") and after == 200 and gen == 200,
            "hog_exit": p.returncode, "hog_out": (p.stdout or p.stderr or "")[-120:], "seconds": round(time.time() - t0, 1),
            "lane_health_before": before, "lane_health_after": after, "lane_generation_after": gen}


def probe_zombie(gpu: int, port: int, lane: str, router: str) -> dict:
    pids = _vllm_pids("omnicoder")
    if not pids:
        return {"ok": False, "reason": "no vllm process for the lane found"}
    free_before = _gpu_free_mb(gpu)
    for pid in pids:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    t0 = time.time()
    left = None
    for _ in range(60):
        time.sleep(1)
        left = [p for p in _gpu_pids(gpu) if p in pids]
        if not left:
            break
    gone_after = round(time.time() - t0, 1)
    free_after = _gpu_free_mb(gpu)
    # the router relaunches on the next request
    _post(f"{router}/v1/chat/completions", {"model": lane, "max_tokens": 1, "messages": [{"role": "user", "content": "ok"}]}, timeout=600)
    back = None
    for i in range(60):
        if _health(port) == 200:
            back = i * 5
            break
        time.sleep(5)
    return {"ok": not left and back is not None, "killed": pids, "zombies_left": left, "gone_after_s": gone_after,
            "gpu_free_mb_before_kill": free_before, "gpu_free_mb_after": free_after, "lane_back_after_s": back}


def probe_neighbour(gpu: int, port: int, lane: str, router: str) -> dict:
    hold = subprocess.Popen([str(VLLM_PY), "-c", f"import torch, time; x = torch.empty(int(6e9), dtype=torch.uint8, device='cuda:{gpu}'); print('holding', flush=True); time.sleep(900)"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(15)
        free_with = _gpu_free_mb(gpu)
        pids = _vllm_pids("omnicoder")
        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        time.sleep(10)
        t0 = time.time()
        _post(f"{router}/v1/chat/completions", {"model": lane, "max_tokens": 1, "messages": [{"role": "user", "content": "ok"}]}, timeout=900)
        back = None
        for i in range(120):
            if _health(port) == 200:
                back = round(time.time() - t0)
                break
            time.sleep(5)
        log = pathlib.Path(r"D:\tmp\lanes\lane-omni.log").read_text(encoding="utf-8", errors="replace")
        tail = log[-20000:]
        util = next((ln for ln in reversed(tail.splitlines()) if "[omni-3090] free=" in ln), "")
        kv = next((ln for ln in reversed(tail.splitlines()) if "GPU KV cache size" in ln), "")
        return {"ok": back is not None and "455,680" in kv, "gpu_free_mb_with_neighbour": free_with, "lane_back_after_s": back,
                "util_line": util[-120:], "kv_line": kv[-80:]}
    finally:
        hold.kill()


def probe_load429(port: int, router: str, lane: str, n: int = 24) -> dict:
    import concurrent.futures as cf
    body = {"model": lane, "max_tokens": 64, "messages": [{"role": "user", "content": "count to twenty slowly, one number per line"}]}
    with cf.ThreadPoolExecutor(max_workers=n) as ex:
        codes = list(ex.map(lambda _: _post(f"{router}/v1/chat/completions", body, timeout=300)[0], range(n)))
    return {"ok": _health(port) == 200 and all(c in (200, 429) for c in codes), "concurrent": n,
            "codes": {str(c): codes.count(c) for c in sorted(set(codes))}, "lane_health_after": _health(port)}


def probe_seed(port: int, lane: str) -> dict:
    code, body = _post(f"http://127.0.0.1:{port}/v1/chat/completions",
                       {"model": lane, "max_tokens": 4, "seed": 2 ** 40, "messages": [{"role": "user", "content": "ok"}]})
    return {"ok": code in (200, 400), "http": code, "body": body[:120]}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("hog", "zombie", "neighbour", "load429", "seed"):
        print(__doc__)
        return 2
    probe = sys.argv[1]
    gpu = int(_arg("--gpu", "1")); port = int(_arg("--port", "8006")); lane = _arg("--lane", "omnicoder-9b"); router = _arg("--router", "http://127.0.0.1:8420")
    fn = {"hog": lambda: probe_hog(port), "zombie": lambda: probe_zombie(gpu, port, lane, router),
          "neighbour": lambda: probe_neighbour(gpu, port, lane, router), "load429": lambda: probe_load429(port, router, lane),
          "seed": lambda: probe_seed(port, lane)}[probe]
    verdict = fn()
    _record(probe, verdict)
    return 0 if verdict.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
