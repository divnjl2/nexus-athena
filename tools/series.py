"""A measured series through the frame (used for the floor, the brief and the A/B runs of 25.09): does a senior's brief (9B, no tools) let a small executor
land what it could not alone? Same tasks, same worktree recipe as `athena bench`; per task the
brief is written first (athena brief, C-8.4), then the dispatch carries it (--brief).

usage: python brief_floor.py --tasks T2.1,T2.3 --executor pi-4b --brief-executor pi-9b \
           --base <scratch>/bonsai --at 98a3324 --tag bonsai-brief9 [--no-brief]
"""
import argparse
import datetime
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(r"C:\Users\пк\Repos\nexus-athena")
CONTRACT = "features/refinery-layer/contract.md"
PLAN = "features/refinery-layer/plan.md"
PY = sys.executable


def sh(argv, cwd=ROOT, timeout=None):
    p = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--executor", default="pi-4b")
    ap.add_argument("--brief-executor", dest="brief_executor", default="pi-9b")
    ap.add_argument("--brief-thinking", dest="brief_thinking", default="medium")
    ap.add_argument("--base", required=True, help="worktree path prefix; the worktree is <base>-<executor>")
    ap.add_argument("--at", default="98a3324", help="commit the worktree is made from (the refinery tasks are red there)")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--stall", type=int, default=600)
    ap.add_argument("--pi-thinking", dest="pi_thinking", default="low")
    ap.add_argument("--no-brief", dest="no_brief", action="store_true")
    ap.add_argument("--ref", default="", help="reference executor#tag column (default <executor>#gpu)")
    a = ap.parse_args()

    ws = pathlib.Path(f"{a.base}-{a.executor}")
    if not ws.exists():
        code, out = sh(["git", "worktree", "add", "--detach", str(ws), a.at])
        print(f"# worktree {ws} at {a.at}: exit {code}", flush=True)
    here = ROOT / "features/refinery-layer/.athena"
    briefs = here / "briefs"
    log = []
    for task in [t.strip() for t in a.tasks.split(",") if t.strip()]:
        t0 = time.time()
        brief_path = ""
        if not a.no_brief:
            argv = [PY, "athena.py", "brief", CONTRACT, "--front", PLAN, "--task", task, "--executor", a.brief_executor,
                    "--workspace", str(ws), "--no-checkpoint", "--pi-thinking", a.brief_thinking, "--timeout", "900", "--text"]
            code, out = sh(argv)
            bp = briefs / f"{task}.md"
            if code == 0 and bp.exists():
                # keep the brief beside the record under the run's tag, and carry that copy
                kept = briefs / f"{task}.{a.tag}.md"
                kept.write_text(bp.read_text(encoding="utf-8"), encoding="utf-8")
                brief_path = str(kept)
            brief_s = int(time.time() - t0)
            print(f"# brief {task} <- {a.brief_executor}/{a.brief_thinking}: exit {code} in {brief_s}s "
                  f"{'-> ' + brief_path if brief_path else '(nothing usable)'}", flush=True)
            if not brief_path:
                print("  " + "\n  ".join(out.strip().splitlines()[-6:]), flush=True)
        t1 = time.time()
        argv = [PY, "athena.py", "dispatch", CONTRACT, "--front", PLAN, "--task", task, "--executor", a.executor,
                "--workspace", str(ws), "--iterations", str(a.iterations), "--timeout", str(a.timeout),
                "--stall", str(a.stall), "--pi-thinking", a.pi_thinking, "--pi-strict", "--tag", a.tag, "--text"]
        if brief_path:
            argv += ["--brief", brief_path]
        code, out = sh(argv)
        first = out.strip().splitlines()[0] if out.strip() else f"exit {code}"
        print(f"# dispatch {task} -> {a.executor}#{a.tag}: {first}  ({int(time.time() - t1)}s)", flush=True)
        sh(["git", "add", "-A"], cwd=ws)
        sh(["git", "commit", "-q", "-m", f"floor {a.executor}#{a.tag} {task}"], cwd=ws)
        log.append({"task": task, "brief": brief_path, "brief_s": int(t1 - t0), "dispatch_s": int(time.time() - t1), "first": first})
    # the table from the record, this tag against the earlier floor rows
    recs = [json.loads(l) for l in (here / "dispatch.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    def cell(task, ex):
        rows = [r for r in recs if r.get("task") == task and r.get("executor") == ex]
        if not rows:
            return "-"
        g = [r for r in rows if r.get("green")]
        secs = sum(int(r.get("duration_ms", 0)) for r in rows) // 1000
        return f"green@{g[0].get('iteration')} {secs}s" if g else f"red x{len(rows)} {secs}s"
    cols = [a.ref or f"{a.executor}#gpu", f"{a.executor}#{a.tag}"]
    print("\n" + " | ".join(["task  "] + cols))
    for row in log:
        print(" | ".join([row["task"].ljust(6)] + [cell(row["task"], c) for c in cols]) + (f"  brief {row['brief_s']}s" if row["brief"] else ""))
    print(f"# done {datetime.datetime.now():%H:%M}")


if __name__ == "__main__":
    main()
