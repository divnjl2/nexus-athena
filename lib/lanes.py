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
