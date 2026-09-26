import hashlib


def provenance_for(model_id, packet_text="", thinking="", tools="", athena_version="", runtime_version=None, seed=None):
    """C-11.1 — the provenance block a dispatch records: the model the executor resolves to (through
    the registry, never a name list), the runtime by the lane's provider, the sampling as the thinking
    level and the seed, the digests of the rendered packet and the tool set, the frame's version.
    Fields the frame cannot know stay None and are named by missing_provenance."""
    import hashlib
    from lib.executors import PI_PROVIDERS
    provider, resolved = PI_PROVIDERS.get(model_id, ("", model_id))
    if provider.startswith(("lane3", "lane4")):
        runtime = "llama.cpp"
    elif provider:
        runtime = "vllm"
    else:
        runtime = "claude" if model_id == "claude" else "unknown"
    return {
        "model": {"id": resolved, "weights": None},
        "runtime": {"name": runtime, "version": runtime_version if runtime_version else None},
        "sampling": {"thinking": thinking or "", "seed": seed},
        "packet_sha256": hashlib.sha256((packet_text or "").encode("utf-8")).hexdigest(),
        "tools_sha256": hashlib.sha256((tools or "").encode("utf-8")).hexdigest(),
        "relay_version": athena_version or "",
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
