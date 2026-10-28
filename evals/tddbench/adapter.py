"""Frozen TDD-Bench-Verified inputs and conservative external-harness reporting.

The evaluator owns sealed data. A generator receives only public.json and a base-code
workspace, never the harness directory, gold fixes, reference tests or private reports.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import re
import urllib.parse
import urllib.request
import zipfile

DATASET = "princeton-nlp/SWE-bench_Verified"
PUBLIC_FIELDS = ("instance_id", "repo", "base_commit", "problem_statement")
SCHEMA = "athena.tdd_benchmark/1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_verified(destination: str, *, opener=urllib.request.urlopen) -> list[dict]:
    rows = []
    total = None
    for offset in range(0, 500, 100):
        params = urllib.parse.urlencode({"dataset": DATASET, "config": "default", "split": "test",
                                        "offset": offset, "length": 100})
        req = urllib.request.Request("https://datasets-server.huggingface.co/rows?" + params,
                                     headers={"User-Agent": "Athena-TDD-calibration/1"})
        with opener(req, timeout=90) as response:
            page = json.load(response)
        total = page["num_rows_total"]
        rows.extend(item["row"] for item in page["rows"])
    if total != 500 or len(rows) != 500 or len({r["instance_id"] for r in rows}) != 500:
        raise ValueError("Verified dataset changed or download is incomplete; no fixture fallback")
    pathlib.Path(destination).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


def filter_tdd(rows: list[dict], membership: str) -> list[dict]:
    ids = [line.strip() for line in membership.splitlines() if line.strip()]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("missing or duplicate TDD membership ids")
    indexed = {}
    for r in rows:
        if r["instance_id"] in indexed:
            raise ValueError("duplicate dataset id")
        indexed[r["instance_id"]] = r
    missing = set(ids) - indexed.keys()
    if missing:
        raise ValueError("TDD members missing from dataset: " + ", ".join(sorted(missing)))
    result = []
    for iid in sorted(ids):
        row = indexed[iid]
        if any(not row.get(k) for k in (*PUBLIC_FIELDS, "patch", "test_patch", "version")):
            raise ValueError(f"{iid}: missing required benchmark input")
        result.append(row)
    return result


def public_input(row: dict) -> dict:
    return {k: row[k] for k in PUBLIC_FIELDS}


def select(rows: list[dict], n: int, *, seed: int, exclude=()) -> list[dict]:
    if n <= 0:
        raise ValueError("selection size must be positive")
    groups = {}
    for row in sorted(rows, key=lambda r: r["instance_id"]):
        if row["instance_id"] not in exclude:
            groups.setdefault(row["repo"], []).append(row)
    rng = random.Random(seed)
    repos = sorted(groups)
    rng.shuffle(repos)
    for group in groups.values():
        rng.shuffle(group)
    chosen = []
    while repos and len(chosen) < n:
        next_round = []
        for repo in repos:
            if len(chosen) == n:
                break
            chosen.append(groups[repo].pop())
            if groups[repo]:
                next_round.append(repo)
        repos = next_round
    if len(chosen) != n:
        raise ValueError("not enough distinct benchmark instances")
    return chosen


def prepare(dataset: str, membership: str, archive: str, destination: str, *, seed: int = 20261024,
            calibration_n: int = 5, evaluation_n: int = 30) -> dict:
    data_path, ids_path, zip_path = map(pathlib.Path, (dataset, membership, archive))
    raw = data_path.read_bytes()
    ids_raw, zip_raw = ids_path.read_bytes(), zip_path.read_bytes()
    harness_files = {}
    with zipfile.ZipFile(zip_path) as source:
        for item in source.infolist():
            if item.is_dir():
                continue
            path = pathlib.PurePosixPath(item.filename)
            if path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
                raise ValueError("invalid harness archive path")
            harness_files[pathlib.PurePosixPath(*path.parts[1:]).as_posix()] = sha(source.read(item))
    rows = filter_tdd(json.loads(raw), ids_raw.decode("utf-8"))
    calibration = select(rows, calibration_n, seed=seed)
    calibration_ids = [r["instance_id"] for r in calibration]
    evaluation = select(rows, evaluation_n, seed=seed + 1, exclude=set(calibration_ids))
    out = pathlib.Path(destination)
    if (out / "manifest.json").exists():
        raise ValueError("refusing to overwrite a frozen benchmark run; use a new destination")
    (out / "sealed").mkdir(parents=True, exist_ok=True)
    (out / "generator").mkdir(parents=True, exist_ok=True)
    for name, selected in (("calibration", calibration), ("evaluation", evaluation)):
        (out / "sealed" / f"{name}.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "generator" / f"{name}.public.json").write_text(
            json.dumps([public_input(row) for row in selected], ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"schema": SCHEMA, "benchmark": "TDD-Bench-Verified", "parent_dataset": DATASET,
                "seed": seed, "members": len(rows), "selection": "seeded round-robin across repositories",
                "calibration_ids": calibration_ids, "evaluation_ids": [r["instance_id"] for r in evaluation],
                "hashes": {"dataset": sha(raw), "membership": sha(ids_raw), "harness_archive": sha(zip_raw)},
                "harness_files": harness_files,
                "artifacts": {str(p.relative_to(out)).replace("\\", "/"): sha(p.read_bytes())
                              for d in (out / "sealed", out / "generator") for p in sorted(d.glob("*.json"))},
                "calibration_is_model_performance": False}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def harness_command(run_dir: str, harness_dir: str, *, git_authorized: bool, run_id: str,
                    image: str = "athena-tdd-controller:20261024", mode: str = "calibration",
                    predictions: str = "gold", timeout: int = 600) -> list[str]:
    if not git_authorized:
        raise PermissionError("upstream harness invokes Git; separate user authorization is required")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,70}", run_id):
        raise ValueError("invalid run id")
    if mode not in ("calibration", "evaluation") or timeout <= 0:
        raise ValueError("invalid benchmark mode or timeout")
    root = pathlib.Path(run_dir).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    source = pathlib.Path(harness_dir).resolve()
    for name, expected in manifest["harness_files"].items():
        p = source / name
        if not p.resolve().is_relative_to(source) or sha(p.read_bytes()) != expected:
            raise ValueError("harness source differs from frozen archive: " + name)
    for name, expected in manifest["artifacts"].items():
        p = root / name
        if not p.resolve().is_relative_to(root) or sha(p.read_bytes()) != expected:
            raise ValueError("frozen benchmark input changed: " + name)
    if predictions == "gold" and mode != "calibration":
        raise ValueError("gold predictions are calibration, not a model evaluation")
    ids = manifest[f"{mode}_ids"]
    if predictions != "gold":
        predictions = prediction_input(root, predictions, ids)
    return ["docker", "run", "--rm", "--name", "athena-tdd-" + run_id,
            "--mount", f"type=bind,source={pathlib.Path(harness_dir).resolve()},target=/opt/tdd,readonly",
            "--mount", f"type=bind,source={root},target=/bench",
            "--volume", "/var/run/docker.sock:/var/run/docker.sock", image,
            "python", "-m", "tddbench.harness.run_evaluation", "--dataset_name", f"/bench/sealed/{mode}.json",
            "--predictions_path", predictions, "--patch_path", "gold", "--max_workers", "1",
            "--cache_level", "instance", "--clean", "False", "--timeout", str(timeout),
            "--run_id", run_id, "--instance_ids", *ids]


def prediction_input(root: pathlib.Path, name: str, selected: list[str]) -> str:
    """Validate a mounted upstream prediction file without silently dropping rows."""
    path = pathlib.Path(name)
    path = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("predictions must be inside the benchmark directory")
    if path.suffix not in (".json", ".jsonl"):
        raise ValueError("predictions must be JSON or JSONL")
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw) if path.suffix == ".json" else [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not isinstance(data, list) or not data:
        raise ValueError("predictions must be a nonempty list")
    seen = set()
    for row in data:
        if not isinstance(row, dict):
            raise ValueError("invalid prediction row")
        iid = row.get("instance_id")
        if not isinstance(iid, str) or iid not in selected or iid in seen:
            raise ValueError("duplicate or unselected prediction instance")
        if not isinstance(row.get("model_patch"), str):
            raise ValueError("prediction model_patch must be text")
        seen.add(iid)
    # Missing ids remain in the report denominator; an empty patch is a real submission.
    return "/bench/" + path.relative_to(root).as_posix()


def classify(report: dict | None) -> dict:
    if not isinstance(report, dict):
        return {"state": "INCOMPLETE", "reason": "missing upstream instance report"}
    before, after = report.get("test_before_patch"), report.get("test_after_patch")
    if not isinstance(before, dict) or not isinstance(after, dict) or not before or not after:
        return {"state": "INCOMPLETE", "reason": "missing test execution evidence"}
    statuses = list(before.values()) + list(after.values())
    if any(s not in ("PASSED", "FAILED") for s in statuses):
        return {"state": "INCOMPLETE", "reason": "errors, skips or unknown test outcomes"}
    witnesses = sorted(k for k, status in before.items() if status == "FAILED")
    if any(k not in after for k in before):
        return {"state": "INCOMPLETE", "reason": "old-code test absent from after-fix report"}
    state = "PASS" if witnesses and all(s == "PASSED" for s in after.values()) else "FAIL"
    if state == "PASS" and report.get("resolved") is not True:
        state, reason = "INCOMPLETE", "functional transition disagrees with upstream coverage/score"
    else:
        reason = "fail-before/pass-after" if state == "PASS" else "no bug witness or correct fix rejected"
    return {"state": state, "reason": reason, "witnesses": witnesses,
            "upstream_resolved": report.get("resolved"), "upstream_score": report.get("final_score"),
            "upstream_coverage": report.get("cov_score")}


def summarize(run_dir: str, run_id: str, *, mode: str = "calibration") -> dict:
    if mode not in ("calibration", "evaluation") or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,70}", run_id):
        raise ValueError("invalid benchmark mode or run id")
    root = pathlib.Path(run_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    selected = manifest[f"{mode}_ids"]
    reports = {}
    for path in sorted((root / "logs" / "run_evaluation" / run_id).rglob("report.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for iid in selected:
            if iid in data:
                if iid in reports:
                    raise ValueError("multiple reports for " + iid)
                reports[iid] = data[iid]
    rows = [{"instance_id": iid, **classify(reports.get(iid))} for iid in selected]
    counts = {s.lower(): sum(r["state"] == s for r in rows) for s in ("PASS", "FAIL", "INCOMPLETE")}
    state = "INCOMPLETE" if counts["incomplete"] else "FAIL" if counts["fail"] else "PASS"
    return {"schema": SCHEMA, "benchmark": "TDD-Bench-Verified", "mode": mode,
            "is_model_performance": mode != "calibration", "run_id": run_id,
            "selected": len(selected), "evaluated": counts["pass"] + counts["fail"],
            **counts, "state": state, "instances": rows}
