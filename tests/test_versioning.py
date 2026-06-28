"""Tests for lib/versioning.py — version pinning for LLM-hop outputs (v3)."""
import json
import pathlib

import pytest

from lib.versioning import (
    hash_file,
    hash_text,
    pin_output,
    design_dir,
    scenario_dir,
    load_version_records,
    VersionRecord,
)


# --- hash helpers ---

def test_hash_text_stable(tmp_path):
    assert hash_text("hello") == hash_text("hello")


def test_hash_text_different_inputs_differ():
    assert hash_text("hello") != hash_text("world")


def test_hash_text_length():
    h = hash_text("x")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_file(tmp_path):
    f = tmp_path / "spec.md"
    f.write_text("# Requirements\nR1: the system shall work", encoding="utf-8")
    h = hash_file(f)
    assert len(h) == 16
    assert hash_file(f) == hash_file(f)  # stable


def test_hash_file_differs_on_content(tmp_path):
    f1 = tmp_path / "a.md"
    f2 = tmp_path / "b.md"
    f1.write_text("aaa", encoding="utf-8")
    f2.write_text("bbb", encoding="utf-8")
    assert hash_file(f1) != hash_file(f2)


# --- pin_output ---

def test_pin_output_returns_version(tmp_path):
    f = tmp_path / "spec.md"
    f.write_text("spec content", encoding="utf-8")
    seams = tmp_path / ".athena" / "seams.jsonl"

    import lib.versioning as vm
    orig = vm._SEAMS_FILE
    vm._SEAMS_FILE = seams
    try:
        ver = pin_output("spec", "run1", f, ts="2026-01-01T00:00:00")
    finally:
        vm._SEAMS_FILE = orig

    assert len(ver) == 16


def test_pin_output_writes_record(tmp_path):
    f = tmp_path / "design.md"
    f.write_text("design content", encoding="utf-8")
    seams = tmp_path / ".athena" / "seams.jsonl"

    import lib.versioning as vm
    orig = vm._SEAMS_FILE
    vm._SEAMS_FILE = seams
    try:
        ver = pin_output("design", "run2", f, input_version="spec_abc", ts="2026-01-01T00:00:00")
        records = load_version_records(seams)
    finally:
        vm._SEAMS_FILE = orig

    assert len(records) == 1
    rec = records[0]
    assert rec.hop == "design"
    assert rec.run_id == "run2"
    assert rec.input_version == "spec_abc"
    assert rec.output_version == ver


def test_pin_output_appends_multiple(tmp_path):
    seams = tmp_path / ".athena" / "seams.jsonl"

    import lib.versioning as vm
    orig = vm._SEAMS_FILE
    vm._SEAMS_FILE = seams
    try:
        for i in range(3):
            f = tmp_path / f"file{i}.md"
            f.write_text(f"content {i}", encoding="utf-8")
            pin_output("spec", f"run{i}", f, ts="2026-01-01T00:00:00")
        records = load_version_records(seams)
    finally:
        vm._SEAMS_FILE = orig

    assert len(records) == 3


def test_version_link_spec_to_design(tmp_path):
    """spec_version <-> design version link is explicit in seams records."""
    seams = tmp_path / ".athena" / "seams.jsonl"
    spec_file = tmp_path / "spec.md"
    design_file = tmp_path / "design.md"
    spec_file.write_text("spec", encoding="utf-8")
    design_file.write_text("design", encoding="utf-8")

    import lib.versioning as vm
    orig = vm._SEAMS_FILE
    vm._SEAMS_FILE = seams
    try:
        spec_ver = pin_output("spec", "r1", spec_file, ts="2026-01-01T00:00:00")
        design_ver = pin_output("design", "r1", design_file,
                                input_version=spec_ver, ts="2026-01-01T00:00:00")
        records = load_version_records(seams)
    finally:
        vm._SEAMS_FILE = orig

    spec_rec = next(r for r in records if r.hop == "spec")
    design_rec = next(r for r in records if r.hop == "design")
    # the link is explicit: design's input_version == spec's output_version
    assert design_rec.input_version == spec_rec.output_version


# --- scenario versioning (v3.1) ---

def test_pin_output_scenario(tmp_path):
    f = tmp_path / "scenarios.md"
    f.write_text("scenario content", encoding="utf-8")
    seams = tmp_path / ".athena" / "seams.jsonl"

    import lib.versioning as vm
    orig = vm._SEAMS_FILE
    vm._SEAMS_FILE = seams
    try:
        sc_ver = pin_output("scenarios", "r1", f,
                            input_version="spec_abc", ts="2026-01-01T00:00:00")
        records = load_version_records(seams)
    finally:
        vm._SEAMS_FILE = orig

    assert records[0].hop == "scenarios"
    assert records[0].input_version == "spec_abc"


# --- path helpers ---

def test_design_dir_structure():
    p = design_dir("spec_abc", "run_xyz")
    assert str(p) == str(pathlib.Path("thoughts/designs/spec_abc/run_xyz"))


def test_scenario_dir_structure():
    p = scenario_dir("spec_abc")
    assert str(p) == str(pathlib.Path("thoughts/scenarios/spec_abc"))


# --- load_version_records ---

def test_load_version_records_missing_file(tmp_path):
    records = load_version_records(tmp_path / "nonexistent.jsonl")
    assert records == []


def test_load_version_records_skips_corrupt_line(tmp_path):
    seams = tmp_path / "seams.jsonl"
    good = json.dumps({
        "hop": "spec", "run_id": "r1", "input_version": "",
        "output_version": "abc", "artifact_path": "spec.md", "ts": "2026-01-01T00:00:00",
    })
    seams.write_text(good + "\n{corrupt json\n" + good + "\n", encoding="utf-8")
    records = load_version_records(seams)
    # corrupt line is skipped; the two good lines are loaded
    assert len(records) == 2


def test_load_version_records_roundtrip(tmp_path):
    seams = tmp_path / "seams.jsonl"
    rec = VersionRecord(
        hop="spec", run_id="r1", input_version="",
        output_version="abc123", artifact_path="spec.md", ts="2026-01-01T00:00:00",
    )
    seams.write_text(json.dumps({
        "hop": rec.hop, "run_id": rec.run_id, "input_version": rec.input_version,
        "output_version": rec.output_version, "artifact_path": rec.artifact_path,
        "ts": rec.ts,
    }) + "\n", encoding="utf-8")
    loaded = load_version_records(seams)
    assert len(loaded) == 1
    assert loaded[0].output_version == "abc123"
