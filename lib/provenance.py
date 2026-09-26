def provenance(model_id: str, weights_digest: str, runtime: str, runtime_version: str,
               sampling: dict, seed: int, packet_sha: str, tools_sha: str, relay_version: str) -> dict:
    return {
        "model": {"id": model_id, "weights": weights_digest},
        "runtime": {"name": runtime, "version": runtime_version},
        "sampling": {**sampling, "seed": seed},
        "packet_sha256": packet_sha,
        "tools_sha256": tools_sha,
        "relay_version": relay_version
    }


def statement(rec: dict, subject_digest: str, base_commit: str) -> dict:
    p = rec.get("provenance", {})
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "tree", "digest": {"gitTree": subject_digest}}],
        "predicateType": "athena/verdict/v1",
        "predicate": {
            "buildDefinition": {
                "externalParameters": {"task": rec["task"], "packet_sha256": p["packet_sha256"]},
                "internalParameters": {
                    "model": {"id": p["model"]["id"], "weights": p["model"]["weights"]},
                    "runtime": {"name": p["runtime"]["name"], "version": p["runtime"]["version"]},
                    "sampling": {**p["sampling"], "seed": p["sampling"]["seed"]},
                    "tools_digest": p["tools_sha256"],
                    "packet_digest": p["packet_sha256"]
                },
                "resolvedDependencies": [{"name": "base", "digest": {"gitCommit": base_commit}}]
            },
            "runDetails": {
                "builder": {"id": "athena/" + rec["executor"]},
                "metadata": {
                    "startedOn": rec["ts"],
                    "byproducts": {"green": rec["green"], "duration_ms": rec["duration_ms"]}
                },
                "byproducts": {"green": rec["green"], "duration_ms": rec["duration_ms"]}
            }
        }
    }


def missing_provenance(provided: dict) -> tuple:
    result = []
    
    # Missing provenance block entirely
    if "provenance" not in provided and isinstance(provided, dict):
        return ("model.weights", "runtime.version", "sampling.seed", "model", "runtime", "sampling", "packet_sha256", "tools_sha256", "relay_version")
    if not isinstance(provided["provenance"], dict):
        return ("model.weights", "runtime.version", "sampling.seed", "model", "runtime", "sampling", "packet_sha256", "tools_sha256", "relay_version")
    prov = provided["provenance"]
    
    # Nested fields in provenance block order (block then details)
    if "model" not in prov:
        result.append("model")
        result.append("model.weights")
    elif "weights" not in prov["model"]:
        result.append("model.weights")
    
    if "runtime" not in prov:
        result.append("runtime")
        result.append("runtime.version")
    elif "version" not in prov["runtime"]:
        result.append("runtime.version")
    
    if "sampling" not in prov:
        result.append("sampling")
        result.append("sampling.seed")
    elif "seed" not in prov["sampling"]:
        result.append("sampling.seed")
    
    # Flat fields always last
    for flat in ["packet_sha256", "tools_sha256", "relay_version"]:
        if flat not in prov:
            result.append(flat)
    
    return tuple(result)
