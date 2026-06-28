"""
Athena versioning — version seams for LLM-hop outputs (v3).

Each LLM hop (spec, design, scenarios) pins its output hash so the chain
spec_version <-> design_version <-> graph_version is explicit in .athena/seams.jsonl.

On deterministic hops (compile), only the input hash is recorded.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
from dataclasses import dataclass

_SEAMS_FILE = pathlib.Path(".athena/seams.jsonl")


@dataclass
class VersionRecord:
    hop: str            # "spec" | "design" | "scenarios" | "compile"
    run_id: str
    input_version: str  # empty string for root hop (spec)
    output_version: str
    artifact_path: str
    ts: str             # ISO-8601 UTC, injected by caller (no Date.now equiv here)


def hash_file(path: str | pathlib.Path) -> str:
    """Return first 16 hex chars of SHA-256 of file bytes."""
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()[:16]


def hash_text(text: str) -> str:
    """Return first 16 hex chars of SHA-256 of UTF-8 encoded text."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def pin_output(
    hop: str,
    run_id: str,
    output_path: str | pathlib.Path,
    *,
    input_version: str = "",
    ts: str = "",
) -> str:
    """Hash the LLM-hop output artifact, append a VersionRecord, return output_version.

    Caller must supply ts (ISO-8601 UTC string) to keep this function pure/testable.
    """
    output_version = hash_file(output_path)
    rec = VersionRecord(
        hop=hop,
        run_id=run_id,
        input_version=input_version,
        output_version=output_version,
        artifact_path=str(output_path),
        ts=ts,
    )
    _SEAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _SEAMS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dataclasses.asdict(rec)) + "\n")
    return output_version


def design_dir(spec_version: str, run_id: str) -> pathlib.Path:
    """Canonical location for design.md — pinned to (spec_version, run_id)."""
    return pathlib.Path("thoughts") / "designs" / spec_version / run_id


def scenario_dir(spec_version: str) -> pathlib.Path:
    """Canonical location for scenario artifacts — pinned to spec_version."""
    return pathlib.Path("thoughts") / "scenarios" / spec_version


def load_version_records(seams_file: pathlib.Path | None = None) -> list[VersionRecord]:
    """Read all VersionRecords from seams.jsonl (empty list if file absent)."""
    path = seams_file or _SEAMS_FILE
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            records.append(VersionRecord(**d))
        except (json.JSONDecodeError, TypeError, KeyError):
            # Corrupt/truncated line (process killed mid-write) — skip, don't crash.
            pass
    return records
