"""Perimeter layer, the CLI wiring: athena repro, bench --series, athena drift. Red until wired."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _athena(*args, cwd=None):
    return subprocess.run([sys.executable, str(ROOT / "athena.py"), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(cwd or ROOT), timeout=300)


def test_athena_repro_dispatches_the_reproduction_and_prints_the_admission():
    """C-2.6 — with --executor none the command prints the packet it would send, naming the red
    record's failing command; with --judge-exits the admission line of C-2.5 is printed."""
    with tempfile.TemporaryDirectory() as td:
        feat = pathlib.Path(td) / "features" / "demo"
        (feat / ".athena").mkdir(parents=True)
        (feat / "contract.md").write_text("# Contract: Demo\n\n## C-1 — a\n\n- **C-1.1** — WHEN a THE SYSTEM SHALL b.\n  - source: design\n", encoding="utf-8")
        (feat / "scenarios.md").write_text("# Scenarios: Demo\n\n### S1.1 — a\n- **verifies:** C-1.1\n- **run_cmd:** `python -m pytest tests/test_demo.py::test_a -q`\n", encoding="utf-8")
        (feat / "plan.md").write_text("# Plan: Demo\n\n**Contract:** features/demo/contract.md\n**Scenarios:** features/demo/scenarios.md\n\n### Tasks\n- [ ] T1.1 A\n  - success_check: `python -m pytest tests/test_demo.py::test_a -q`\n  - files: `lib/demo.py`\n  - verifies: S1.1\n", encoding="utf-8")
        rec = {"task": "T1.1", "executor": "pi-omni9", "green": False, "passed": False, "changed_files": ["lib/demo.py"],
               "red_full": [{"cmd": "python -m pytest tests/test_demo.py::test_a -q", "exit": 1, "tail": "E   assert 2 == 3\nFAILED tests/test_demo.py::test_a"}],
               "reason": "python -m pytest tests/test_demo.py::test_a -q exit 1", "ts": "2026-09-27T00:00:00+00:00"}
        (feat / ".athena" / "dispatch.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
        p = _athena("repro", str(feat / "contract.md"), "--front", str(feat / "plan.md"), "--task", "T1.1", "--record", "-1",
                    "--executor", "none", "--text", cwd=td)
        assert p.returncode == 0, p.stdout + p.stderr
        assert "tests/test_demo.py::test_a" in p.stdout and "assert 2 == 3" in p.stdout
        assert p.stdout.lower().index("passes on the present behaviour") < p.stdout.lower().index("invert")
        judged = _athena("repro", str(feat / "contract.md"), "--front", str(feat / "plan.md"), "--task", "T1.1", "--record", "-1",
                         "--executor", "none", "--judge-exits", "0,1", "--text", cwd=td)
        assert judged.returncode == 0 and "admitted" in judged.stdout.lower() and "0" in judged.stdout and "1" in judged.stdout
        refused = _athena("repro", str(feat / "contract.md"), "--front", str(feat / "plan.md"), "--task", "T1.1", "--record", "-1",
                          "--executor", "none", "--judge-exits", "1,1", "--text", cwd=td)
        assert refused.returncode == 1 and "refused" in refused.stdout.lower()


def test_bench_series_and_athena_drift_print_the_drops_with_their_commands():
    """C-4.5 — athena drift over a prepared series prints one line per executor with the verdict
    and, for a drop, the bd command; athena bench names --series."""
    with tempfile.TemporaryDirectory() as td:
        series = pathlib.Path(td) / "bench_series.jsonl"
        rows = []
        for i, r in enumerate([0.8] * 6 + [0.4] * 4):
            rows.append({"ts": f"2026-09-{20 + i:02d}T00:00:00", "executor": "pi-omni9", "model": "omnicoder-9b", "runtime": "vllm 0.21.0",
                         "set_digest": "d1", "tasks": 10, "green": int(r * 10), "rate": r})
        for i in range(8):
            rows.append({"ts": f"2026-09-{20 + i:02d}T00:00:00", "executor": "pi-3b", "model": "nanbeige-3b", "runtime": "llama.cpp",
                         "set_digest": "d1", "tasks": 10, "green": 9, "rate": 0.9})
        series.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        p = _athena("drift", str(ROOT / "features" / "perimeter-layer" / "contract.md"), "--series", str(series), "--slug", "perimeter-layer", "--text")
        assert p.returncode == 0, p.stdout + p.stderr
        lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
        assert any("pi-omni9" in ln and "drop" in ln for ln in lines) and any("pi-3b" in ln and "ok" in ln for ln in lines)
        assert "bd create" in p.stdout and "omnicoder-9b" in p.stdout
    h = _athena("bench", "-h")
    assert "--series" in h.stdout


def test_the_daemon_applies_the_floors_and_the_wake_and_the_merge_governs_the_mutation_stage():
    """C-5.5 — the dry daemon with floors and an injected host state parks with the resource when under
    a floor and ticks when above; the flags for the wake, the inventory and the governor exist."""
    import json
    import tempfile
    GB = 1024 ** 3
    with tempfile.TemporaryDirectory() as td:
        low = pathlib.Path(td) / "low.json"
        low.write_text(json.dumps({"ram_free": 3 * GB, "ram_total": 64 * GB, "gpus": [{"index": 1, "name": "RTX 3090", "free": 12 * GB, "total": 24 * GB}]}), encoding="utf-8")
        high = pathlib.Path(td) / "high.json"
        high.write_text(json.dumps({"ram_free": 30 * GB, "ram_total": 64 * GB, "gpus": [{"index": 1, "name": "RTX 3090", "free": 12 * GB, "total": 24 * GB}]}), encoding="utf-8")
        ready = pathlib.Path(td) / "ready.json"
        ready.write_text(json.dumps([{"id": "athena:demo:T2.1", "priority": 1, "created_at": "2026-09-27T10:00:00Z"}]), encoding="utf-8")
        base = ["daemon", str(ROOT / "features" / "refinery-layer" / "contract.md"), "--front", str(ROOT / "features" / "refinery-layer" / "plan.md"),
                "--slug", "demo", "--ready-json", str(ready), "--dry-run", "--text", "--host-floors", "ram=8G,vram=2G"]
        p = _athena(*base, "--host-json", str(low))
        assert p.returncode == 0, p.stdout + p.stderr
        assert "park" in p.stdout.lower() and "ram" in p.stdout.lower() and "3.0" in p.stdout
        q = _athena(*base, "--host-json", str(high))
        assert q.returncode == 0 and "daemon: T2.1" in q.stdout
    h = _athena("daemon", "-h")
    assert "--wake" in h.stdout and "--gpu-allowlist" in h.stdout and "--host-floors" in h.stdout
    m = _athena("merge", "-h")
    assert "--governor-gb" in m.stdout

