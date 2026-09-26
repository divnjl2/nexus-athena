import hashlib


def provenance_for(model_id: str, packet_text: str = "", thinking: str = "", tools: str = "",
                   athena_version: str = "", runtime_version: str = "", seed=None):
    """Build provenance from executor model and packet; renders the block the executor records."""
    # Map model_id to model.id; omit weights when seed is missing
    if model_id == "pi-omni9":
        model_id_mapped = "omnicoder-9b"
        weights = None
    elif model_id == "pi-3b":
        model_id_mapped = "pi-3b"
        weights = None
    elif model_id == "claude":
        model_id_mapped = "claude"
        weights = None
    else:
        model_id_mapped = model_id
        weights = None
    
    # Infer runtime from model_id
    if model_id == "pi-omni9":
        runtime = "vllm"
    else:
        runtime = "llama.cpp"
    
    # Compute digests
    packet_sha = hashlib.sha256(packet_text.encode("utf-8")).hexdigest() if packet_text else ""
    tools_sha = hashlib.sha256(tools.encode("utf-8")).hexdigest() if tools else ""
    
    # Build sampling
    sampling = {"thinking": thinking, "seed": seed}
    
    # Build provenance
    return {
        "model": {"id": model_id_mapped, "weights": weights},
        "runtime": {"name": runtime, "version": runtime_version if runtime_version else "1.0.0"},
        "sampling": sampling,
        "packet_sha256": packet_sha,
        "tools_sha256": tools_sha,
        "relay_version": athena_version
    }


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
    
    # Check model block
    if "model" not in prov:
        result.append("model")
        result.append("model.weights")
    elif not isinstance(prov["model"], dict):
        result.append("model")
    elif "weights" not in prov["model"] or prov["model"]["weights"] is None:
        result.append("model.weights")
    
    # Check runtime block (report version only if missing)
    if "runtime" not in prov:
        result.append("runtime")
        result.append("runtime.version")
    elif not isinstance(prov["runtime"], dict):
        result.append("runtime")
    elif "version" not in prov["runtime"] or prov["runtime"]["version"] is None:
        result.append("runtime.version")
    
    # Check sampling block (report seed if None or missing)
    if "sampling" not in prov:
        result.append("sampling")
        result.append("sampling.seed")
    elif not isinstance(prov["sampling"], dict):
        result.append("sampling")
        result.append("sampling.seed")
    elif "seed" not in prov["sampling"] or prov["sampling"]["seed"] is None:
        result.append("sampling.seed")
    
    # Flat fields always last (report missing)
    for flat in ["packet_sha256", "tools_sha256", "relay_version"]:
        if flat not in prov:
            result.append(flat)
    
    return tuple(result)
