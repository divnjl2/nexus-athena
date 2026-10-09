"""Freeze and verify a stratified, revision-pinned SWE-bench Lite task set.

The manifest carries fingerprints rather than the hidden acceptance material. A
runner must fetch the pinned revision and verify both fingerprints before a run.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

DATASET = "princeton-nlp/SWE-bench_Lite"
REVISION = "6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2"
SELECTION_SEED = "nexus-athena-vnext-pilot-2026-10-09"
ARMS = ("codex", "codex_athena", "codex_athena_optimizer")


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def inputs(row: dict) -> dict:
    return {"problem_statement": row["problem_statement"],
            "hints_text": row.get("hints_text") or ""}


def acceptance(row: dict) -> dict:
    return {key: row[key] for key in ("FAIL_TO_PASS", "PASS_TO_PASS", "test_patch")}


def select(rows: list[dict]) -> dict:
    """Select three per repo by stable hash; reserve one per repo for holdout."""
    by_repo: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_repo[row["repo"]].append(row)
    if len(by_repo) != 12 or any(len(group) < 3 for group in by_repo.values()):
        raise ValueError("expected 12 repositories with at least three tasks each")
    tasks = []
    for repo, group in sorted(by_repo.items()):
        ranked = sorted(group, key=lambda row: (
            hashlib.sha256((SELECTION_SEED + ":" + row["instance_id"]).encode()).hexdigest(),
            row["instance_id"]))[:3]
        for index, row in enumerate(ranked):
            tasks.append({"id": row["instance_id"], "repo": repo,
                          "base_commit": row["base_commit"],
                          "split": "holdout" if index == 2 else "development",
                          "input_sha256": fingerprint(inputs(row)),
                          "acceptance_sha256": fingerprint(acceptance(row))})
    return {"schema": "athena.self-improve.corpus/1", "dataset": DATASET,
            "revision": REVISION, "seed": SELECTION_SEED,
            "arms": list(ARMS), "tasks": tasks}


def verify(manifest: dict, rows: list[dict]) -> None:
    if manifest != select(rows):
        raise ValueError("corpus differs from the pinned revision or selection rule")


def load_pinned() -> list[dict]:
    from datasets import load_dataset
    return list(load_dataset(DATASET, split="test", revision=REVISION))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "verify"))
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).with_name("manifest.json"))
    args = parser.parse_args()
    rows = load_pinned()
    if args.action == "freeze":
        if args.manifest.exists():
            raise SystemExit("refusing to overwrite a frozen manifest")
        args.manifest.write_text(json.dumps(select(rows), ensure_ascii=False,
                                           indent=2) + "\n", encoding="utf-8")
    else:
        verify(json.loads(args.manifest.read_text(encoding="utf-8")), rows)
    print(f"{args.action}: 36 tasks, 24 development, 12 holdout; revision {REVISION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
