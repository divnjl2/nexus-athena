import json
import hashlib
"""Lane state parsing and admission logic (C-4.1, C-4.2)."""

import re
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# C-4.1: Parse vLLM /metrics and llama.cpp /slots into one lane state
# ---------------------------------------------------------------------------

def lane_state_from_metrics(metrics_text: str) -> Dict:
    """Parse vLLM's /metrics Prometheus text into a unified lane state dict.

    Expected keys:
        - running    : requests running count
        - waiting    : requests waiting count
        - kv_usage   : KV cache usage as a float (0.0–1.0)
        - prefix_hit_rate : prefix-cache hit rate (hits / queries)

    Garbage input yields an empty dict.
    """
    if not metrics_text or not isinstance(metrics_text, str):
        return {}

    running = waiting = None
    kv_usage = None
    prefix_queries = None
    prefix_hits = None

    for line in metrics_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # --- running / waiting requests ---
        m_running = re.search(r"vllm:num_requests_running\s*\{[^}]*\}\s+(\d+\.\d+)", line)
        if m_running:
            running = float(m_running.group(1))

        m_waiting = re.search(r"vllm:num_requests_waiting\s*\{[^}]*\}\s+(\d+\.\d+)", line)
        if m_waiting:
            waiting = float(m_waiting.group(1))

        # --- KV usage percentage ---
        m_kv = re.search(r"vllm:kv_cache_usage_perc\s*\{[^}]*\}\s+(\d+\.\d+)", line)
        if m_kv:
            kv_usage = float(m_kv.group(1))

        # --- prefix-cache queries & hits ---
        m_pq = re.search(r"vllm:prefix_cache_queries_total\s*\{[^}]*\}\s+(\d+\.\d+)", line)
        if m_pq:
            prefix_queries = float(m_pq.group(1))

        m_ph = re.search(r"vllm:prefix_cache_hits_total\s*\{[^}]*\}\s+(\d+\.\d+)", line)
        if m_ph:
            prefix_hits = float(m_ph.group(1))

    state: Dict = {}
    if running is not None:
        state["running"] = running
    if waiting is not None:
        state["waiting"] = waiting
    if kv_usage is not None:
        state["kv_usage"] = kv_usage
    if prefix_queries is not None and prefix_hits is not None:
        state["prefix_hit_rate"] = prefix_hits / prefix_queries

    # If none of the expected metrics were found, return empty state
    if not state:
        return {}

    return state


def lane_state_from_slots(slots: List) -> Dict:
    """Parse llama.cpp /slots into a unified lane state dict.

    Each slot is a dict with at least ``id`` and ``is_processing``.
    Slots only carry processing status; KV usage and prefix hit rate are unknown.
    """
    running = 0
    for slot in slots or []:
        if isinstance(slot, dict) and slot.get("is_processing") is True:
            running += 1

    return {
        "running": running,
        "waiting": 0,
        "kv_usage": None,
        "prefix_hit_rate": None,
    }


# ---------------------------------------------------------------------------
# C-4.2: Admission by capacity — admit only when lane has headroom
# ---------------------------------------------------------------------------

def admit(lane_state: Dict, limit: int, kv_ceiling: float) -> tuple:
    """Admit a task to a lane only when all three conditions hold:

    1. **Nothing waiting** — ``lane_state["waiting"]`` must be 0.
    2. **KV usage under ceiling** — if ``kv_usage`` is known, it must be
       strictly less than ``kv_ceiling``; an unknown ``kv_usage`` does not block.
    3. **Running count has headroom** — ``running`` must be strictly less
       than ``limit`` (i.e. room for one more task).

    Returns ``(True, "admitted")`` on success or ``(False, reason_string)``
    with a named refusal reason otherwise.
    """
    if not lane_state:
        return (False, "no lane state")

    waiting = lane_state.get("waiting", 0)
    running = lane_state.get("running", 0)
    kv_usage = lane_state.get("kv_usage")

    # Condition 1: nothing waiting
    if waiting > 0:
        return (False, f"{waiting} waiting")

    # Condition 2: KV usage under ceiling (unknown kv_usage does not block)
    if kv_usage is not None and kv_usage > kv_ceiling:
        return (False, f"kv {kv_usage:.2f} over {kv_ceiling}")

    # Condition 3: running count under limit minus one (headroom for new task)
    if running >= limit - 1:
        return (False, f"running {running} of limit {limit}, no headroom")

    return (True, "admitted")


# ---------------------------------------------------------------------------
# C-4.5: Speculation-decoding flag admission — paired verdicts & greedy outputs
# ---------------------------------------------------------------------------


def speculation_verdict(paired_runs: List) -> tuple:
    """Admit a speculative-decoding flag only when every task lands the same verdict
    with and without the flag AND temperature-zero greedy outputs are token-identical.

    Each entry in ``paired_runs`` describes one task as a pair:
        ``{"task": "T2.1", "plain": {"green": True, "tokens": [...]}, "spec": {...}}"``

    Returns ``(True, "N tasks agree")`` when all tasks agree on verdicts and tokens.
    Otherwise returns ``(False, reason)`` naming the task and the first divergence.

    Clause C-4.5: the flag is admitted only after the same tasks land the same verdicts
    with and without it and temperature-zero outputs are token-identical, and names the
    first divergence otherwise.
    """
    if not paired_runs:
        return (False, "no paired runs")

    agree_count = 0
    for entry in paired_runs:
        task = entry["task"]
        plain = entry["plain"]
        spec = entry["spec"]

        # --- Verdict comparison ---
        if plain["green"] != spec["green"]:
            if plain["green"]:
                verdict_str = "green without, red with"
            else:
                verdict_str = "red without, green with"
            return (False, f"{task}: verdict {verdict_str}")

        # --- Token (greedy output) comparison ---
        plain_tokens = plain["tokens"]
        spec_tokens = spec["tokens"]
        min_len = min(len(plain_tokens), len(spec_tokens))

        # Scan common prefix for first token divergence (0-indexed position)
        for i in range(min_len):
            if plain_tokens[i] != spec_tokens[i]:
                return (False, f"{task}: outputs diverge at token {i}")

        # Length mismatch → divergence at the token position where the shorter
        # sequence ends (1-indexed)
        if len(plain_tokens) != len(spec_tokens):
            return (False, f"{task}: outputs diverge at token {min_len}")

        agree_count += 1

    return (True, f"{agree_count} tasks agree")


# --- C-4.3: prefix affinity ------------------------------------------------------------

def prefix_key(packet_text: str, chars: int = 1500) -> str:
    """PURE (C-4.3): the key of a packet's static prefix — the first `chars` characters, which
    pi keeps byte-stable between turns (traced 24.09); tasks sharing it share the lane's cache."""
    return hashlib.sha1((packet_text or "")[:chars].encode("utf-8", "replace")).hexdigest()[:16]


def served(warm: dict, key: str, lane: str, *, now: float) -> dict:
    """PURE (C-4.3): the warmth table after `lane` served prefix `key` at `now`."""
    out = dict(warm or {})
    out[key] = (lane, float(now))
    return out


def choose_lane(key: str, lanes, warm: dict, *, now: float, warm_s: float = 600.0) -> str:
    """PURE (C-4.3): the lane that last served this prefix while it is still warm, else the
    first lane offered."""
    lanes = list(lanes or [])
    if not lanes:
        return ""
    hit = (warm or {}).get(key)
    if hit:
        lane, ts = hit
        if lane in lanes and float(now) - float(ts) <= float(warm_s):
            return lane
    return lanes[0]


# --- C-4.4: cooldown ---------------------------------------------------------------------

def cooling(events, *, now: float, period_s: float = 120.0, errors: int = 2) -> tuple:
    """PURE (C-4.4): (cooling, reason). `events` are (ts, http_status) in order; the last
    `errors` events all 5xx start a cooldown of `period_s` from the last of them; any non-5xx
    in between resets the count."""
    events = list(events or [])
    if len(events) < errors:
        return False, ""
    tail = events[-errors:]
    if not all(int(status) >= 500 for _, status in tail):
        return False, ""
    until = float(tail[-1][0]) + float(period_s)
    if float(now) >= until:
        return False, ""
    return True, f"{errors} server errors, cooling until {until:g}s"


# ---------------------------------------------------------------------------
# C-11.5: Lane endpoint derivation and live-state admission reading
# ---------------------------------------------------------------------------

LANE_ENDPOINT_MAP = {
    "pi-omni9": "metrics",
    "pi-3b": "slots",
}


def lane_endpoint(executor, base_url):
    """C-11.5 — derive a lane's metrics or slots endpoint from the executor's base url.

    Parameters:
        executor: the pi executor identifier (e.g. "pi-omni9", "pi-3b").
        base_url: the executor's base URL (may carry a /v1 version suffix).

    Returns:
        a tuple (endpoint_type, endpoint_url). Non-lane executors or empty base_url
        yield ("", "").
    """
    if not base_url or executor not in LANE_ENDPOINT_MAP:
        return ("", "")
    endpoint_type = LANE_ENDPOINT_MAP[executor]
    # Strip trailing /v1 version suffix before appending the endpoint path
    base = base_url.rstrip("/")
    while base.endswith("/v1"):
        base = base[:-3]
    endpoint_url = base + f"/{endpoint_type}"
    return (endpoint_type, endpoint_url)


def live_state(executor, base_url, fetch=None):
    """C-11.5 — read that lane's live state from its metrics or slots endpoint,
    derived from the executor's base url, and fall back to an empty state when the read fails.

    Parameters:
        executor: the pi executor identifier.
        base_url: the executor's base URL.
        fetch: an injected fetcher function(url) -> raw_data; if None, return empty state.

    Returns:
        a dict with keys running, waiting, kv_usage, prefix_hit_rate.
    """
    endpoint_type, endpoint_url = lane_endpoint(executor, base_url)

    if not endpoint_type:
        return {}

    if fetch is None:
        return {}

    try:
        raw = fetch(endpoint_url)
    except Exception:
        return {}

    if endpoint_type == "metrics":
        return lane_state_from_metrics(raw)
    elif endpoint_type == "slots":
        slots = json.loads(raw)
        return lane_state_from_slots(slots)

    return {}