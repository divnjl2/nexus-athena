"""Load SWE-bench-Lite instances for the intent->plan eval.

Tries the live HF dataset (`princeton-nlp/SWE-bench_Lite`, streaming so we never pull the
whole thing); falls back to the committed offline fixtures under `fixtures/` when the
network is blocked. Deterministic order (HF test split is stable; fixtures sorted by id).
"""
from __future__ import annotations

import glob
import json
import os

_HF_NAME = "princeton-nlp/SWE-bench_Lite"
_FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_KEEP = ("instance_id", "repo", "base_commit", "problem_statement", "patch",
         "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS", "hints_text", "version")


def load_fixtures() -> list[dict]:
    """Offline: the committed fixture instances, sorted by id. Always available."""
    out = []
    for p in sorted(glob.glob(os.path.join(_FIXTURE_DIR, "*.json"))):
        with open(p, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def load_instances(n: int = 5, *, offline: bool = False) -> list[dict]:
    """Return up to `n` instances. offline=True (or HF unreachable) uses fixtures."""
    if offline:
        return load_fixtures()[:n]
    try:
        import itertools
        from datasets import load_dataset
        ds = load_dataset(_HF_NAME, split="test", streaming=True)
        rows = list(itertools.islice(ds, n))
        return [{k: r[k] for k in _KEEP} for r in rows]
    except Exception as e:  # network blocked / datasets missing -> graceful offline
        print(f"[loader] HF unavailable ({type(e).__name__}: {str(e)[:60]}); using fixtures")
        return load_fixtures()[:n]


if __name__ == "__main__":
    import sys
    insts = load_instances(int(sys.argv[1]) if len(sys.argv) > 1 else 2,
                           offline="--offline" in sys.argv)
    for i in insts:
        print(i["instance_id"], "|", i["repo"], "| FAIL_TO_PASS:",
              len(json.loads(i["FAIL_TO_PASS"]) if isinstance(i["FAIL_TO_PASS"], str)
                  else i["FAIL_TO_PASS"]))
