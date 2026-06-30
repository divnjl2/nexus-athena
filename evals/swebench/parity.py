"""Implementation parity — local (opencode→local lane) vs claude_code, on the same issues.

Closes the one unproven assumption in EFFICIENCY.md: we measured PLANNING parity; this
measures whether the local model IMPLEMENTS at parity. Each adapter produces a code patch on
the repo@base_commit; we compare to the gold patch.

GATE — two tiers:
  * proxy (runs HERE, deterministic): does the candidate patch apply, touch the gold file(s),
    and overlap the gold hunks? A strong-but-not-perfect implementation signal. No Docker.
  * real FAIL_TO_PASS (wired, gated on Docker + the swebench harness): apply test_patch, run
    the FAIL_TO_PASS tests. Raises NotAvailable here (Docker daemon down on this box).

The deterministic scorer (hunk_ranges / proxy_score) needs no repo and is unit-tested.
"""
from __future__ import annotations

import re
import subprocess

from evals.swebench.score import gold_patch_targets

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_FILE_RE = re.compile(r"^\+\+\+ b/(.+?)\s*$")
_DIFF_RE = re.compile(r"^diff --git a/.+? b/(.+?)\s*$")


class GateNotAvailable(RuntimeError):
    """The real FAIL_TO_PASS gate needs Docker + the swebench harness, absent here."""


def hunk_ranges(patch: str) -> dict[str, list[tuple[int, int]]]:
    """{file -> [(old_start, old_len), ...]} from the diff's @@ headers (old side)."""
    out: dict[str, list[tuple[int, int]]] = {}
    cur: str | None = None
    for line in patch.splitlines():
        d = _DIFF_RE.match(line) or _FILE_RE.match(line)
        if d:
            cur = d.group(1)
            out.setdefault(cur, [])
            continue
        h = _HUNK_RE.match(line)
        if h and cur is not None:
            start = int(h.group(1))
            length = int(h.group(2) or "1")
            out[cur].append((start, length))
    return {f: rs for f, rs in out.items() if rs}


def _overlaps(a: list[tuple[int, int]], b: list[tuple[int, int]]) -> bool:
    for s1, l1 in a:
        for s2, l2 in b:
            if s1 < s2 + max(l2, 1) and s2 < s1 + max(l1, 1):   # half-open interval overlap
                return True
    return False


def proxy_score(candidate_patch: str, gold_patch: str) -> dict:
    """Deterministic implementation-quality proxy comparing a candidate diff to the gold diff.

    file_touch: candidate changes a gold (non-test) file (by basename).
    hunk_overlap: candidate edits overlap the gold edits in a shared file (line ranges).
    score: 0.0 (nothing), 0.5 (right file, wrong place), 1.0 (right file AND overlapping hunks).
    """
    gold_files = {f.rsplit("/", 1)[-1] for f in gold_patch_targets(gold_patch)["files"]}
    # candidate files via hunk_ranges keys — tolerant of a model diff that omits the
    # `diff --git` header and starts straight at `--- a/ … +++ b/` (gold_patch_targets needs
    # the git header; a raw unified diff does not).
    cand_files = {f.rsplit("/", 1)[-1] for f in hunk_ranges(candidate_patch)}
    file_touch = bool(gold_files & cand_files)

    gold_h = {k.rsplit("/", 1)[-1]: v for k, v in hunk_ranges(gold_patch).items()}
    cand_h = {k.rsplit("/", 1)[-1]: v for k, v in hunk_ranges(candidate_patch).items()}
    hunk_overlap = any(_overlaps(cand_h[f], gold_h[f]) for f in (gold_files & cand_files)
                       if f in gold_h and f in cand_h)

    score = 1.0 if (file_touch and hunk_overlap) else (0.5 if file_touch else 0.0)
    return {"file_touch": file_touch, "hunk_overlap": hunk_overlap, "score": score,
            "gold_files": sorted(gold_files), "candidate_files": sorted(cand_files)}


# --- runner (needs a repo checkout + an agent) ---------------------------------

def checkout_repo(instance: dict, workdir: str, *, timeout: int = 600) -> None:
    """Shallow-ish clone of repo@base_commit into workdir (partial clone keeps it light)."""
    import os
    url = f"https://github.com/{instance['repo']}.git"
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", url, workdir],
                   check=True, capture_output=True, text=True, timeout=timeout)
    subprocess.run(["git", "-C", workdir, "checkout", instance["base_commit"]],
                   check=True, capture_output=True, text=True, timeout=timeout)
    assert os.path.isdir(workdir)


def diff_of(workdir: str) -> str:
    return subprocess.run(["git", "-C", workdir, "diff"], capture_output=True, text=True).stdout


def real_gate(instance: dict, candidate_patch: str) -> bool:
    """Real FAIL_TO_PASS — needs Docker + swebench harness. Not runnable on this box."""
    raise GateNotAvailable("real FAIL_TO_PASS needs Docker daemon + swebench harness")


# --- cluster-only implementer (no Anthropic; the local vLLM lane writes the patch) ------

def _tracked_py(workdir: str) -> list[str]:
    out = subprocess.run(["git", "-C", workdir, "ls-files", "*.py"],
                         capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]


def pick_file(instance: dict, workdir: str) -> str | None:
    """Pick the file to edit FROM THE ISSUE (no gold knowledge): rank tracked .py files by
    word-boundary mentions of their basename / module path. Short stems (e.g. `e`) are matched
    only as whole words and only when >=4 chars, so they don't inflate via substring hits."""
    ps = instance["problem_statement"].lower()
    words = set(re.findall(r"[a-z_][a-z0-9_]{2,}", ps))   # tokens in the issue, len>=3
    best, best_score = None, 0
    for path in _tracked_py(workdir):
        base = path.rsplit("/", 1)[-1]                    # fitsrec.py
        stem = base[:-3]                                  # fitsrec
        # dotted module path tokens (astropy/io/fits/fitsrec.py -> io, fits, fitsrec)
        parts = [p for p in path[:-3].split("/") if len(p) >= 4]
        score = ps.count(base) * 5                        # exact "fitsrec.py" mention — strongest
        if len(stem) >= 4 and stem in words:              # whole-word module name
            score += 3
        score += sum(2 for p in parts[-3:] if p in words)  # path components named in the issue
        if score > best_score:
            best, best_score = path, score
    return best


def _extract_diff(text: str) -> str:
    text = re.sub(r"```(?:diff|patch)?", "", text).replace("```", "")
    i = text.find("diff --git")
    if i == -1:
        i = text.find("--- a/")
    return text[i:].strip() if i != -1 else ""


def _issue_tokens(problem_statement: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", problem_statement.lower())]


def _relevant_window(content: str, tokens: list[str], *, span: int = 320) -> tuple[int, str]:
    """Return (1-based start line, numbered slice) of the ~span-line window of the file richest
    in issue tokens — so a 52KB file is focused to the buggy region, not blindly truncated.
    Line numbers are shown so the model can emit correct `@@` ranges."""
    lines = content.splitlines()
    if len(lines) <= span:
        start = 0
    else:
        tok = set(tokens)
        # score each line by token hits, then find the best contiguous span by prefix sums
        hits = [sum(1 for w in re.findall(r"[a-z_][a-z0-9_]{3,}", ln.lower()) if w in tok) for ln in lines]
        pref = [0]
        for h in hits:
            pref.append(pref[-1] + h)
        best, start = -1, 0
        for s in range(0, len(lines) - span + 1):
            window = pref[s + span] - pref[s]
            if window > best:
                best, start = window, s
    slice_lines = lines[start:start + span]
    numbered = "\n".join(f"{start + 1 + i}: {ln}" for i, ln in enumerate(slice_lines))
    return start + 1, numbered


def local_implement(instance: dict, workdir: str, *, lane: str = "worker",
                    timeout: int = 900) -> dict:
    """Cluster-only: a local lane writes a unified diff that fixes the issue. Picks the target
    file + the relevant window FROM THE ISSUE, emits a git diff. Returns {file, patch} —
    proxy_score works on the diff text, no apply needed. Defaults to the WORKER lane (9B,
    fast code-gen) — the 35B reasoning planner lane is too slow for diff generation (it timed
    out at 1100s on this prompt)."""
    import os
    from evals.llm import chat, LLMError
    path = pick_file(instance, workdir)
    if not path:
        return {"file": None, "patch": ""}
    try:
        content = open(os.path.join(workdir, path), encoding="utf-8", errors="replace").read()
    except OSError:
        return {"file": path, "patch": ""}
    start, window = _relevant_window(content, _issue_tokens(instance["problem_statement"]))
    prompt = (
        f"Fix the bug below by editing `{path}`. Output ONLY a unified git diff — headers "
        f"`--- a/{path}` / `+++ b/{path}`, and `@@ -<line>,<count> +<line>,<count> @@` hunks "
        f"whose line numbers match the numbered source (the prefix `N: ` is the real line "
        f"number — do NOT include it in the diff body). No prose.\n\n"
        f"## Issue\n{instance['problem_statement'][:2000]}\n\n"
        f"## `{path}` (lines {start}+)\n{window}\n")
    try:
        out, _ = chat(prompt, lane=lane, max_tokens=3000, strict_finish=False, timeout=timeout)
    except LLMError:
        return {"file": path, "patch": ""}
    return {"file": path, "patch": _extract_diff(out)}


def run_parity_local(instance: dict, workdir: str, *, keep: bool = False) -> dict:
    """Cluster-only parity: local 35B implements; proxy-score vs gold. No Anthropic."""
    import os
    if os.path.exists(workdir):
        _rmtree_retry(workdir)
    checkout_repo(instance, workdir)
    try:
        impl = local_implement(instance, workdir)
        score = proxy_score(impl["patch"], instance["patch"])
    finally:
        if not keep:
            _rmtree_retry(workdir)
    return {"instance_id": instance["instance_id"], "agent": "local_9b",
            "picked_file": impl["file"], "empty": not impl["patch"].strip(), **score}


def _reset(workdir: str) -> None:
    subprocess.run(["git", "-C", workdir, "checkout", "."], capture_output=True, text=True)
    subprocess.run(["git", "-C", workdir, "clean", "-fd"], capture_output=True, text=True)


def generate_patch(adapter, instance: dict, workdir: str, *, timeout: int = 1800) -> str:
    """Drive ONE executor adapter (agent-agnostic) in the checked-out repo; return its diff.
    Reuses ralph.adapter so 'which agent' is the only thing that changes."""
    import shutil
    from ralph.adapter import Issue
    issue = Issue(key=instance["instance_id"],
                  title=instance["problem_statement"][:1500],
                  success_check="the FAIL_TO_PASS tests pass")
    _reset(workdir)
    argv = list(adapter.command(issue, workdir))
    # npm-installed agent CLIs (claude/opencode) are .cmd shims on Windows — resolve so
    # subprocess can find them (the same WinError 2 the bd client hit).
    argv[0] = shutil.which(argv[0]) or argv[0]
    try:
        subprocess.run(argv, cwd=workdir, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass   # agent absent / timed out -> empty diff, scored as no-op (not a crash)
    return diff_of(workdir)


def _on_rm_error(func, path, _exc):
    """git pack files are read-only on Windows — clear the bit and retry the unlink."""
    import os
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _rmtree_retry(path: str, tries: int = 3) -> None:
    """Windows holds file handles briefly after a git process exits; retry the removal,
    clearing read-only bits (git packs) on the final pass."""
    import os
    import shutil
    import time
    for i in range(tries):
        if i < tries - 1:
            shutil.rmtree(path, ignore_errors=True)
        else:
            shutil.rmtree(path, onerror=_on_rm_error)
        if not os.path.exists(path):
            return
        time.sleep(1.0)


def run_parity(instance: dict, adapters: list, workdir: str, *, timeout: int = 1800,
               keep: bool = False) -> dict:
    """Checkout once, run each adapter to a patch, proxy-score each vs the gold patch.
    Cleans the (heavy) checkout afterwards unless keep=True — disk is finite."""
    import os
    if os.path.exists(workdir):
        _rmtree_retry(workdir)
    checkout_repo(instance, workdir)
    gold = instance["patch"]
    results = {}
    try:
        for ad in adapters:
            patch = generate_patch(ad, instance, workdir, timeout=timeout)
            results[ad.name] = {"empty": not patch.strip(), **proxy_score(patch, gold)}
    finally:
        if not keep:
            _rmtree_retry(workdir)
    return {"instance_id": instance["instance_id"], "by_agent": results}


# NOTE: this block MUST stay at the END of the file — under `python -m` the module body runs
# top-to-bottom, so every function the batch calls (run_parity_local, _rmtree_retry,
# local_implement, …) must already be defined above it.
if __name__ == "__main__":
    import json
    import os
    import sys
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from evals.swebench.loader import load_instances

    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 5
    workers = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--workers=")), "2"))
    base = r"D:\tmp\claude\parity_batch"

    def _one(inst):
        try:
            return run_parity_local(inst, os.path.join(base, inst["instance_id"]))
        except Exception as e:  # checkout/clone failures must not kill the batch
            return {"instance_id": inst["instance_id"], "error": f"{type(e).__name__}: {str(e)[:80]}"}

    insts = load_instances(n)
    results, scores = [], []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for fut in as_completed({ex.submit(_one, i): i for i in insts}):
            r = fut.result()
            results.append(r)
            if "error" in r:
                tag = f"ERROR {r['error'][:40]}"
            else:
                scores.append(r["score"])
                tag = f"score={r['score']} file={r.get('picked_file', '?').rsplit('/', 1)[-1]}"
            print(f"[{len(results)}/{len(insts)}] {r['instance_id']}: {tag}", flush=True)
    mean = sum(scores) / len(scores) if scores else 0.0
    out = {"agent": "local_9b_cluster", "n": len(results), "scored": len(scores),
           "mean_proxy_score": round(mean, 3),
           "file_touch_rate": round(sum(1 for r in results if r.get("file_touch")) / len(results), 3),
           "results": results}
    rdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "parity_cluster.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\nCLUSTER-ONLY implementation proxy: mean={mean:.3f} over {len(scores)} scored "
          f"(file_touch+hunk_overlap -> 1.0); saved results/parity_cluster.json", flush=True)
