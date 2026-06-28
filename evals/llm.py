"""Reasoning-aware OpenAI-compatible client for the live win-desktop vLLM lanes.

The served models (qwen35-a3b @:8000, qwen9b-opus @:8001) are reasoning models:
the answer lands in choices[0].message.content AFTER an internal reasoning pass that
also consumes output tokens. So max_tokens must be generous (never cap the thinking),
and we must not treat an empty content + finish_reason=length as "the answer".
"""
from __future__ import annotations

import json
import time
import urllib.request

LANES = {"planner": ("127.0.0.1", 8000, "qwen35-a3b"),   # 35B on 3090 — quality hops
         "worker":  ("127.0.0.1", 8001, "qwen9b-opus")}   # 9B on 3060 — fast code-gen


class LLMError(RuntimeError):
    pass


MAX_TOKENS_CEILING = 16000   # reasoning headroom; lanes serve ~30k+ ctx


def _one_call(host, port, model, messages, max_tokens, temperature, timeout):
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens, "temperature": temperature}).encode()
    req = urllib.request.Request(
        f"http://{host}:{port}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=timeout))
    ch = resp["choices"][0]
    return ch.get("finish_reason"), (ch.get("message") or {}).get("content")


def chat(prompt: str, *, lane: str = "planner", max_tokens: int = 6000,
         temperature: float = 0.0, timeout: int = 600,
         system: str | None = None, strict_finish: bool = True) -> tuple[str, float]:
    """Return (content, elapsed_seconds).

    strict_finish=True (PLANNER / structured JSON): a finish_reason=length means the model
    never emitted its final answer (the <analysis> prose fills content) — treating that as
    the answer scrapes garbage. So escalate max_tokens (x2 up to ceiling) and retry; never
    cap the reasoning. Raise only if even the ceiling truncates.

    strict_finish=False (WORKER / code-gen): truncated output usually still contains a
    complete function (the code precedes the point the budget ran out), and downstream
    code-extraction salvages it. One escalation for headroom, then return content as-is
    rather than fail the whole task — let the gate be the judge.
    """
    host, port, model = LANES[lane]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    t0 = time.time()
    budget = max_tokens
    while True:
        try:
            fr, content = _one_call(host, port, model, messages, budget, temperature, timeout)
        except Exception as e:  # noqa: BLE001 — surface any transport/HTTP error
            raise LLMError(f"{lane} call failed: {e}") from e
        if fr == "length" and budget < MAX_TOKENS_CEILING:
            budget = min(budget * 2, MAX_TOKENS_CEILING)
            continue
        if fr == "length" and strict_finish:
            raise LLMError(
                f"{lane} still truncated at ceiling {budget} — reasoning never "
                f"reached a final answer")
        if not content:
            raise LLMError(f"{lane} returned empty content (finish_reason={fr})")
        return content.strip(), time.time() - t0


if __name__ == "__main__":
    out, dt = chat("Write a one-line Python function add(a,b) that returns a+b. "
                   "Reply with ONLY the code, no fences.", lane="worker", max_tokens=2048)
    print(f"worker {dt:.1f}s ->\n{out}")
