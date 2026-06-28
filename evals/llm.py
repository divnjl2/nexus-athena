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


def chat(prompt: str, *, lane: str = "planner", max_tokens: int = 4096,
         temperature: float = 0.0, timeout: int = 600,
         system: str | None = None) -> tuple[str, float]:
    """Return (content, elapsed_seconds). Raises LLMError on transport/empty/truncated."""
    host, port, model = LANES[lane]
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model, "messages": messages,
        "max_tokens": max_tokens, "temperature": temperature,
    }).encode()
    req = urllib.request.Request(
        f"http://{host}:{port}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=timeout))
    except Exception as e:  # noqa: BLE001 — surface any transport/HTTP error to caller
        raise LLMError(f"{lane} call failed: {e}") from e
    ch = resp["choices"][0]
    content = (ch.get("message") or {}).get("content")
    if not content:
        fr = ch.get("finish_reason")
        if fr == "length":
            raise LLMError(
                f"{lane} ran out of tokens during reasoning (max_tokens={max_tokens}); "
                "raise max_tokens — do not cap the reasoning model")
        raise LLMError(f"{lane} returned empty content (finish_reason={fr})")
    return content.strip(), time.time() - t0


if __name__ == "__main__":
    out, dt = chat("Write a one-line Python function add(a,b) that returns a+b. "
                   "Reply with ONLY the code, no fences.", lane="worker", max_tokens=2048)
    print(f"worker {dt:.1f}s ->\n{out}")
