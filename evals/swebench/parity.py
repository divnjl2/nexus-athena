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
    cand_files = {f.rsplit("/", 1)[-1] for f in gold_patch_targets(candidate_patch)["files"]}
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


def _reset(workdir: str) -> None:
    subprocess.run(["git", "-C", workdir, "checkout", "."], capture_output=True, text=True)
    subprocess.run(["git", "-C", workdir, "clean", "-fd"], capture_output=True, text=True)


def generate_patch(adapter, instance: dict, workdir: str, *, timeout: int = 1800) -> str:
    """Drive ONE executor adapter (agent-agnostic) in the checked-out repo; return its diff.
    Reuses ralph.adapter so 'which agent' is the only thing that changes."""
    from ralph.adapter import Issue
    issue = Issue(key=instance["instance_id"],
                  title=instance["problem_statement"][:1500],
                  success_check="the FAIL_TO_PASS tests pass")
    _reset(workdir)
    try:
        subprocess.run(adapter.command(issue, workdir), cwd=workdir,
                       capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        pass
    return diff_of(workdir)


def _rmtree_retry(path: str, tries: int = 3) -> None:
    """Windows holds file handles briefly after a git process exits; retry the removal."""
    import shutil
    import time
    for i in range(tries):
        shutil.rmtree(path, ignore_errors=(i < tries - 1))
        if not __import__("os").path.exists(path):
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
