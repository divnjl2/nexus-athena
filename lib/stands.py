"""
Stands - cassette freshness and reporting.

C-2.2: When a cassette is older than the freshness threshold, report it stale
with its age in days, oldest first; the report is advisory.

C-2.3: Embedded PostgreSQL stand providing a local database for specs.
"""
from __future__ import annotations

import subprocess

import pathlib
import os
import shutil
import socket
import time
from pathlib import Path
from typing import Any, List, Dict
import shutil


def stale_cassettes(
    entries: List[tuple[str, float]],
    now: float,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Check which cassettes are stale (older than `days` threshold).
    
    Args:
        entries: List of (path, timestamp) tuples
        now: Current timestamp
        days: Freshness threshold in days
    
    Returns:
        List of stale cassette reports, sorted by age (oldest first),
        excluding fresh ones. Each report has: path, age_days, advisory
    """
    day_seconds = 86400.0
    threshold_seconds = days * day_seconds
    
    stale = []
    for path, timestamp in entries:
        age_seconds = now - timestamp
        if age_seconds > threshold_seconds:
            age_days = age_seconds / day_seconds
            stale.append({
                "path": str(path),
                "age_days": age_days,
                "advisory": True
            })
    
    # Sort by age_days descending (oldest first)
    stale.sort(key=lambda x: x["age_days"], reverse=True)
    
    return stale


def pg_bin_dir() -> pathlib.Path:
    """where the embedded PostgreSQL binaries are: ATHENA_PG_BIN, the ASCII copy under ProgramData, or the
    package's own install (which fails initdb under a non-ASCII profile path, measured 27.09)"""
    for cand in (os.environ.get("ATHENA_PG_BIN", ""), r"C:\ProgramData\athena\pg\bin"):
        if cand and pathlib.Path(cand).is_dir():
            return pathlib.Path(cand)
    try:
        import embedded_postgres  # noqa: F401
        return pathlib.Path(embedded_postgres.__file__).parent / "pginstall" / "bin"
    except ImportError:
        return pathlib.Path(r"C:\ProgramData\athena\pg\bin")


def free_port_in_range(start: int = 60084, end: int = 60089) -> int:
    """C-2.3: a free loopback port inside the range the sandbox's fence permits (ATHENA_STAND_PORTS)"""
    rng = os.environ.get("ATHENA_STAND_PORTS", "")
    if rng and "-" in rng:
        a, b = rng.split("-", 1)
        if a.strip().isdigit() and b.strip().isdigit():
            start, end = int(a), int(b)
    for port in range(start, end + 1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            s.close()
    raise RuntimeError(f"no free port in {start}-{end}")


def _kill_on_close_job():
    """a Windows job object whose processes die when its last handle closes — this process's death takes
    the stand's postgres with it; None where the API is unavailable"""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        job = k.CreateJobObjectW(None, None)
        if not job:
            return None
        class _Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]
        class _IoCounters(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class _Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", _Basic), ("IoInfo", _IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        info = _Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000   # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):   # JobObjectExtendedLimitInformation
            k.CloseHandle(job)
            return None
        return job
    except Exception:  # noqa: BLE001 — the stand still works, only without the safety net
        return None


def _assign_to_job(job, pid: int) -> bool:
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1F0FFF, False, int(pid))
        ok = bool(k.AssignProcessToJobObject(job, h)) if h else False
        if h:
            k.CloseHandle(h)
        return ok
    except Exception:  # noqa: BLE001
        return False


def _close_handle(job) -> None:
    try:
        import ctypes
        ctypes.windll.kernel32.CloseHandle(job)
    except Exception:  # noqa: BLE001
        pass


class PostgresStand:
    """C-2.3: one PostgreSQL per spec from the embedded binaries — a fresh data directory, a port in the
    permitted range, trust auth for `postgres`, UTF-8 with the C locale; stopped and removed on exit."""

    def __init__(self, base_dir, *, port: int | None = None, bin_dir=None):
        self._bin = pathlib.Path(bin_dir) if bin_dir else pg_bin_dir()
        self.port = port or free_port_in_range()
        self.pgdata = pathlib.Path(base_dir) / f"pg-{self.port}"
        self.log = pathlib.Path(base_dir) / f"pg-{self.port}.log"
        self.uri = f"postgresql://postgres@127.0.0.1:{self.port}/postgres"
        self._env = {**os.environ, "PGCLIENTENCODING": "UTF8"}

    def _run(self, exe: str, *args: str, timeout: int = 120) -> tuple:
        p = subprocess.run([str(self._bin / exe), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=self._env, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def __enter__(self):
        if self.pgdata.exists():
            shutil.rmtree(self.pgdata, ignore_errors=True)
        code, out = self._run("initdb.exe", "-D", str(self.pgdata), "-U", "postgres", "-A", "trust", "-E", "UTF8", "--locale=C")
        if code != 0:
            raise RuntimeError("initdb failed: " + out[-400:])
        # postgres.exe is our own child inside a job object that dies with this process (kill-on-close):
        # measured 27.09, twenty orphaned postgres.exe under the sandbox account from a stand that
        # started through pg_ctl and was never stopped when its spec died
        self._job = _kill_on_close_job()
        self._proc = subprocess.Popen([str(self._bin / "postgres.exe"), "-D", str(self.pgdata), "-p", str(self.port), "-h", "127.0.0.1"],
                                      stdout=open(self.log, "ab"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=self._env)
        if self._job is not None:
            _assign_to_job(self._job, self._proc.pid)
        deadline = time.time() + 120
        while time.time() < deadline:
            code, _ = self._run("pg_isready.exe", "-h", "127.0.0.1", "-p", str(self.port), timeout=15)
            if code == 0:
                return self
            if self._proc.poll() is not None:
                break
            time.sleep(0.5)
        self.__exit__(None, None, None)
        raise RuntimeError("postgres did not become ready on port %d; see %s" % (self.port, self.log))

    def sql(self, query: str) -> str:
        """run SQL through psql; the plain, tuples-only output comes back as text"""
        code, out = self._run("psql.exe", "-h", "127.0.0.1", "-p", str(self.port), "-U", "postgres", "-d", "postgres",
                              "-v", "ON_ERROR_STOP=1", "-t", "-A", "-c", query)
        if code != 0:
            raise RuntimeError("psql failed: " + out[-400:])
        return out

    def __exit__(self, exc_type, exc, tb):
        proc = getattr(self, "_proc", None)
        if proc is not None and proc.poll() is None:
            self._run("pg_ctl.exe", "-D", str(self.pgdata), "-m", "fast", "-w", "stop", timeout=120)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
        job = getattr(self, "_job", None)
        if job is not None:
            _close_handle(job)
        for _ in range(20):
            try:
                shutil.rmtree(self.pgdata)
                break
            except OSError:
                time.sleep(0.5)
        return False


def postgres_stand(base_dir, *, port: int | None = None) -> PostgresStand:
    """C-2.3: `with postgres_stand(tmp_path) as pg:` — pg.uri, pg.port, pg.pgdata, pg.sql(...)"""
    return PostgresStand(base_dir, port=port)


def repro_packet(
    rec: Dict[str, Any],
    *,
    task: str,
    test_path: str,
) -> str:
    """C-2.4: Build a reproduction packet from a red verdict.
    
    Packs the failing command, its tail and changed files into a packet
    that asks for a test passing on present behaviour first and its inversion second,
    never for the fix.
    
    Args:
        rec: Record dict with task, executor, green, changed_files, red_full, reason
        task: Task name (e.g., "T2.1")
        test_path: Path to the reproduction test file
    
    Returns:
        A string containing the packet description
    """
    cmd = rec["red_full"][0]["cmd"]
    tail = rec["red_full"][0]["tail"]
    changed = rec["changed_files"]
    
    parts = [
        f"[Reproduction Packet for {task}]",
        f"Failing command: {cmd}",
        f"Error tail: {tail}",
        f"Changed files: {', '.join(changed)}",
        f"Test path: {test_path}",
        "",
        "Wanted: test passes on the present behaviour first, then fails when inverted.",
        "",
        "Warning: do not edit the module under test itself.",
        "Never the fix - only the test in " + test_path + ".",
        "",
        "Notes:",
        "  - Do not change the implementation",
        "  - Only add a test that verifies the current behavior",
        "  - Submit revert of the fix before this packet",
        "  - Only then open the inverter test",
    ]
    
    return "\n".join(parts)


def repro_admit(
    green: int,
    red: int,
) -> Dict[str, Any]:
    """C-2.5: Check if a reproduction is admitted.
    
    A reproduction is admitted only when:
    - The 'as-written' test passes (green=0) - passes on present behaviour
    - The 'inverted' test fails (red != 0) - fails when inverted
    
    Args:
        green: Exit code of the test on present behaviour (0 = pass)
        red: Exit code of the inverted test (non-zero = fail)
    
    Returns:
        Dict with:
        - ok: bool for admission status
        - exits: list of [green, red]
        - reason: explanation string
    """
    if green == 0 and red != 0:
        # As-written passes, inverted fails: admitted!
        return {
            "ok": True,
            "exits": [green, red],
            "reason": "admitted: both halves behave as expected.\n  - passes on the present behaviour (exit 0)\n  - fails when inverted (exit non-zero)"
        }
    elif green == 0 and red == 0:
        # Both pass - inverted should have failed
        return {
            "ok": False,
            "exits": [green, red],
            "reason": "invert failed or no 'present behaviour'"
        }
    elif green == 1 and red == 1:
        # Both fail - should have passed
        return {
            "ok": False,
            "exits": [green, red],
            "reason": "as written failed on present behaviour"
        }
    elif green == 1 and red == 0:
        # As-written fails, inverted passes - backwards
        return {
            "ok": False,
            "exits": [green, red],
            "reason": "backwards: (1, 0) - inverted passed instead"
        }
    else:
        return {
            "ok": False,
            "exits": [green, red],
            "reason": "unexpected exit codes"
        }
