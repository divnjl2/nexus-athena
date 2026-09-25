"""
Athena toolcalls — a tool call that came back as prose, turned into a structured call on the
CLIENT side (v3.12, executor-layer C-6.*).

The inference lanes are the operator's and are not touched (hard rule). So when a local model
answers an executor's tool schema in a shape the server's parser does not accept — measured:
`{"function": "glob", "parameter": {...}}` inside <tool_call>, which vLLM's hermes parser
refuses with KeyError 'name' and hands back as content — the fix lives here: a relay in
front of the gateway reads the completion, finds the call in the text and returns it as a
proper OpenAI `tool_calls` entry. A well-formed response passes through untouched.

Shapes accepted: hermes JSON ({"name","arguments"}), the distillate's ({"function",
"parameter"} and friends), the OpenAI nested shape, and Qwen3 XML
(<function=NAME><parameter=K>V</parameter></function>).

Freeze-line: PURE, stdlib-only. Serving HTTP is the CLI's job (`athena relay`).
"""
from __future__ import annotations

import json
import re
import uuid

NAME_KEYS = ("name", "function", "function_name", "tool", "tool_name", "action")
ARG_KEYS = ("arguments", "parameters", "parameter", "args", "input", "params", "action_input")
_BLOCK = re.compile(r"<tool_call>(.*?)(?:</tool_call>|$)", re.DOTALL)
_XML_FUNC = re.compile(r"<function=([^>\s]+)>(.*?)(?:</function>|$)", re.DOTALL)
_XML_PARAM = re.compile(r"<parameter=([^>\s]+)>(.*?)</parameter>", re.DOTALL)


def _coerce_args(args):
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return {"value": args}
    return args if isinstance(args, dict) else {"value": args}


def normalize_call(obj) -> dict | None:
    """PURE: any observed call shape -> {"name": str, "arguments": dict}, or None."""
    if not isinstance(obj, dict):
        return None
    inner = obj.get("function")
    if isinstance(inner, dict):
        obj = {"name": inner.get("name"),
               "arguments": next((inner[k] for k in ARG_KEYS if k in inner), {})}
    name = next((obj[k] for k in NAME_KEYS if isinstance(obj.get(k), str) and obj[k].strip()), None)
    if not name:
        return None
    args = next((obj[k] for k in ARG_KEYS if k in obj), {})
    return {"name": name.strip(), "arguments": _coerce_args(args)}


def parse_xml_calls(text: str) -> list[dict]:
    """PURE: Qwen3 XML calls -> normalised calls; JSON-looking values parse, the rest stay text."""
    out = []
    for name, body in _XML_FUNC.findall(text):
        args = {}
        for key, value in _XML_PARAM.findall(body):
            value = value.strip()
            try:
                args[key] = json.loads(value)
            except ValueError:
                args[key] = value
        out.append({"name": name.strip(), "arguments": args})
    return out


def _first_json(body: str):
    try:
        return json.loads(body)
    except ValueError:
        pass
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(body[start:end + 1])
    except ValueError:
        return None


def extract_calls(text: str) -> list[dict]:
    """PURE: every tool call in a completion's text, whatever shape it came in (C-6.1)."""
    calls: list[dict] = []
    for m in _BLOCK.finditer(text or ""):
        body = m.group(1).strip()
        if not body:
            continue
        if "<function=" in body:
            calls += parse_xml_calls(body)
            continue
        obj = _first_json(body)
        for item in (obj if isinstance(obj, list) else [obj]):
            call = normalize_call(item)
            if call:
                calls.append(call)
    if not calls and "<function=" in (text or ""):
        calls = parse_xml_calls(text)
    return calls


def content_before_calls(text: str) -> str | None:
    idx = text.find("<tool_call>")
    if idx < 0:
        idx = text.find("<function=")
    kept = (text[:idx] if idx >= 0 else text).strip()
    return kept or None


_HEADLESS = re.compile(r"(\{.*\})\s*</tool_call>", re.DOTALL)


def repair_headless_call(text: str) -> str:
    """PURE (C-6.9): a call closed by `</tool_call>` with no opening tag gets the tag back in
    front of its JSON; anything else is returned as it came. Measured on Ternary Bonsai 4B
    behind llama.cpp b11165 (Qwen3 template, tool_choice auto): the lane's parser consumed
    the opening tag as its grammar trigger, failed the rest, and left it as content."""
    if not isinstance(text, str) or "</tool_call>" not in text or "<tool_call>" in text:
        return text
    m = _HEADLESS.search(text)
    if not m or not normalize_call(_first_json(m.group(1))):
        return text
    return text[:m.start(1)] + "<tool_call>" + text[m.start(1):]


def wants_replay(body, path: str) -> bool:
    """PURE (C-6.10): a streaming chat completion that carries tools is the one the relay
    asks for without a stream and replays as chunks; everything else streams through."""
    return (isinstance(body, dict) and bool(body.get("stream")) and bool(body.get("tools"))
            and str(path).endswith("/chat/completions"))


def chat_chunks(payload: dict) -> list:
    """PURE (C-6.10): a complete chat completion rendered as the `chat.completion.chunk` SSE
    frames a streaming client expects: role, content, reasoning, tool_calls with index and
    id, finish_reason, then the usage when there is one, then [DONE]."""
    base = {"id": payload.get("id"), "object": "chat.completion.chunk",
            "created": payload.get("created"), "model": payload.get("model")}

    def frame(choices, **extra):
        return "data: " + json.dumps({**base, "choices": choices, **extra}, ensure_ascii=False) + chr(10) * 2

    frames = []
    for choice in payload.get("choices") or []:
        idx = choice.get("index", 0)
        msg = choice.get("message") or {}
        frames.append(frame([{"index": idx, "delta": {"role": msg.get("role") or "assistant", "content": ""},
                              "finish_reason": None}]))
        if msg.get("reasoning_content"):
            frames.append(frame([{"index": idx, "delta": {"reasoning_content": msg["reasoning_content"]},
                                  "finish_reason": None}]))
        if msg.get("content"):
            frames.append(frame([{"index": idx, "delta": {"content": msg["content"]}, "finish_reason": None}]))
        for k, call in enumerate(msg.get("tool_calls") or []):
            fn = call.get("function") or {}
            frames.append(frame([{"index": idx, "delta": {"tool_calls": [
                {"index": k, "id": call.get("id"), "type": "function",
                 "function": {"name": fn.get("name"), "arguments": fn.get("arguments", "")}}]},
                "finish_reason": None}]))
        frames.append(frame([{"index": idx, "delta": {}, "finish_reason": choice.get("finish_reason") or "stop"}]))
    if payload.get("usage") is not None:
        frames.append(frame([], usage=payload["usage"]))
    frames.append("data: [DONE]" + chr(10) * 2)
    return frames


def completion_from_chunks(frames) -> dict:
    """PURE (C-6.10): the completion a sequence of chunk frames describes — the reading side
    of chat_chunks, for the spec and for anyone who needs the whole message back."""
    out: dict = {"object": "chat.completion", "choices": []}
    by_index: dict = {}
    for f in frames:
        line = str(f).strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            body = json.loads(data)
        except ValueError:
            continue
        for k in ("id", "created", "model"):
            if body.get(k) is not None:
                out[k] = body[k]
        if body.get("usage") is not None:
            out["usage"] = body["usage"]
        for ch in body.get("choices") or []:
            idx = ch.get("index", 0)
            slot = by_index.setdefault(idx, {"index": idx, "finish_reason": None,
                                             "message": {"role": "assistant", "content": None, "tool_calls": []}})
            delta = ch.get("delta") or {}
            if delta.get("role"):
                slot["message"]["role"] = delta["role"]
            if delta.get("content"):
                slot["message"]["content"] = (slot["message"]["content"] or "") + delta["content"]
            if delta.get("reasoning_content"):
                slot["message"]["reasoning_content"] = slot["message"].get("reasoning_content", "") + delta["reasoning_content"]
            for tc in delta.get("tool_calls") or []:
                k = int(tc.get("index", 0))
                calls = slot["message"]["tool_calls"]
                while len(calls) <= k:
                    calls.append({"id": None, "type": "function", "function": {"name": "", "arguments": ""}})
                if tc.get("id"):
                    calls[k]["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    calls[k]["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    calls[k]["function"]["arguments"] += fn["arguments"]
            if ch.get("finish_reason"):
                slot["finish_reason"] = ch["finish_reason"]
    for idx in sorted(by_index):
        slot = by_index[idx]
        if not slot["message"]["tool_calls"]:
            del slot["message"]["tool_calls"]
        out["choices"].append(slot)
    return out


def _prepare_thinking(body: dict, *, thinking: bool = False) -> tuple[dict, bool]:
    """PURE: the request side of the relay (C-6.4). A request that carries tools gets
    `chat_template_kwargs.enable_thinking` set to `thinking` (default off) unless the caller
    already set it; a request without tools is left as it is.

    Why: vLLM issue #42021 — Qwen3.5 under `--reasoning-parser qwen3` with thinking ON
    writes its tool calls inside the reasoning in a non-standard shape, and the tool parser
    never sees them; with `enable_thinking=false` the same model returns proper tool_calls.
    That is the request-level workaround the issue names, applied here so the lane's flags
    stay the operator's."""
    if not isinstance(body, dict) or not body.get("tools"):
        return body, False
    kwargs = body.get("chat_template_kwargs")
    if not isinstance(kwargs, dict):
        kwargs = {}
    if "enable_thinking" in kwargs:
        return body, False
    body["chat_template_kwargs"] = {**kwargs, "enable_thinking": bool(thinking)}
    return body, True


def normalize_completion(payload: dict, *, id_factory=None) -> tuple[dict, bool]:
    """PURE: an OpenAI chat-completion response -> (response, changed). A choice whose message
    already carries `tool_calls` passes through (C-6.2); a choice whose text holds a call
    gets structured `tool_calls`, the text before the call kept as content, and
    finish_reason "tool_calls" (C-6.1). Anything unexpected passes through untouched."""
    if not isinstance(payload, dict) or not isinstance(payload.get("choices"), list):
        return payload, False
    id_factory = id_factory or (lambda: "call_" + uuid.uuid4().hex[:24])
    changed = False
    for choice in payload["choices"]:
        msg = choice.get("message") if isinstance(choice, dict) else None
        if not isinstance(msg, dict) or msg.get("tool_calls"):
            continue
        text = repair_headless_call(msg.get("content"))          # C-6.9
        if not isinstance(text, str) or ("<tool_call>" not in text and "<function=" not in text):
            continue
        calls = extract_calls(text)
        if not calls:
            continue
        msg["tool_calls"] = [{"id": id_factory(), "type": "function",
                              "function": {"name": c["name"],
                                           "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                             for c in calls]
        msg["content"] = content_before_calls(text)
        choice["finish_reason"] = "tool_calls"
        changed = True
    return payload, changed


# --- the Anthropic messages path: what Claude Code speaks (C-6.5) ------------------------

def normalize_messages_response(payload: dict, *, id_factory=None) -> tuple[dict, bool]:
    """PURE (C-6.5): an Anthropic messages response -> (response, changed). A text block that
    holds a tool call in the model's own shape becomes a tool_use block (the text before it
    kept), and stop_reason becomes tool_use. A response that already has tool_use, or plain
    prose, passes through. Measured: Qwopus 27B answered `<tool_call><function=Read>...` as
    text and Claude Code, seeing no tool_use, took the turn as finished."""
    if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
        return payload, False
    if any(isinstance(b, dict) and b.get("type") == "tool_use" for b in payload["content"]):
        return payload, False
    id_factory = id_factory or (lambda: "toolu_" + uuid.uuid4().hex[:24])
    blocks: list = []
    changed = False
    for b in payload["content"]:
        text = b.get("text") if isinstance(b, dict) and b.get("type") == "text" else None
        text = repair_headless_call(text)                        # C-6.9
        if not isinstance(text, str) or ("<tool_call>" not in text and "<function=" not in text):
            blocks.append(b)
            continue
        calls = extract_calls(text)
        if not calls:
            blocks.append(b)
            continue
        before = content_before_calls(text)
        if before:
            blocks.append({"type": "text", "text": before})
        for c in calls:
            blocks.append({"type": "tool_use", "id": id_factory(), "name": c["name"],
                           "input": c["arguments"] if isinstance(c["arguments"], dict) else {"value": c["arguments"]}})
        changed = True
    if changed:
        payload["content"] = blocks
        payload["stop_reason"] = "tool_use"
    return payload, changed


def sse_events(payload: dict) -> list:
    """PURE (C-6.5): a complete Anthropic message rendered as the SSE frames a streaming client
    expects: message_start, one start/delta/stop per content block, message_delta with the
    stop reason and usage, message_stop."""
    def frame(event: str, data: dict) -> str:
        return f"event: {event}" + chr(10) + "data: " + json.dumps(data, ensure_ascii=False) + chr(10) + chr(10)
    usage = payload.get("usage") or {}
    head = {k: v for k, v in payload.items() if k not in ("content", "stop_reason", "stop_sequence")}
    head.update({"content": [], "stop_reason": None, "stop_sequence": None,
                 "usage": {"input_tokens": int(usage.get("input_tokens", 0)), "output_tokens": 0}})
    out = [frame("message_start", {"type": "message_start", "message": head})]
    for i, b in enumerate(payload.get("content") or []):
        kind = b.get("type")
        if kind == "tool_use":
            out.append(frame("content_block_start", {"type": "content_block_start", "index": i,
                             "content_block": {"type": "tool_use", "id": b.get("id"), "name": b.get("name"), "input": {}}}))
            out.append(frame("content_block_delta", {"type": "content_block_delta", "index": i,
                             "delta": {"type": "input_json_delta", "partial_json": json.dumps(b.get("input") or {}, ensure_ascii=False)}}))
        elif kind == "thinking":
            out.append(frame("content_block_start", {"type": "content_block_start", "index": i,
                             "content_block": {"type": "thinking", "thinking": ""}}))
            out.append(frame("content_block_delta", {"type": "content_block_delta", "index": i,
                             "delta": {"type": "thinking_delta", "thinking": b.get("thinking", "")}}))
        else:
            out.append(frame("content_block_start", {"type": "content_block_start", "index": i,
                             "content_block": {"type": "text", "text": ""}}))
            out.append(frame("content_block_delta", {"type": "content_block_delta", "index": i,
                             "delta": {"type": "text_delta", "text": b.get("text", "")}}))
        out.append(frame("content_block_stop", {"type": "content_block_stop", "index": i}))
    out.append(frame("message_delta", {"type": "message_delta",
                     "delta": {"stop_reason": payload.get("stop_reason") or "end_turn", "stop_sequence": payload.get("stop_sequence")},
                     "usage": {"output_tokens": int(usage.get("output_tokens", 0))}}))
    out.append(frame("message_stop", {"type": "message_stop"}))
    return out


def strict_tools(body: dict) -> tuple[dict, bool]:
    """PURE (C-6.7): every function tool in a chat-completions request gets `strict: true`,
    so vLLM applies its grammar to the call under tool_choice=auto (its enforce flag
    defaults to on, but only strict tools are pinned). Tools already strict, and requests
    without tools, are left alone."""
    tools = body.get("tools") if isinstance(body, dict) else None
    if not isinstance(tools, list) or not tools:
        return body, False
    changed = False
    out = []
    for tool in tools:
        if isinstance(tool, dict) and tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            fn = tool["function"]
            if fn.get("strict") is not True:
                tool = {**tool, "function": {**fn, "strict": True}}
                changed = True
        out.append(tool)
    if not changed:
        return body, False
    return {**body, "tools": out}, True


def prepare_request(body: dict, *, thinking: bool = False, strict: bool = False) -> tuple[dict, bool]:
    """PURE: the request as the relay forwards it — thinking as asked (C-6.4/C-6.6), tools
    strict when asked (C-6.7)."""
    body, changed = _prepare_thinking(body, thinking=thinking)
    if strict:
        body, c2 = strict_tools(body)
        changed = changed or c2
    return body, changed


# --- the window arithmetic, done once, at the relay (C-6.8) ------------------------------------

OUTPUT_FLOOR = 256


def clamp_output(body: dict, prompt_tokens: int, window: int, *, margin: int = 1024,
                 floor: int = OUTPUT_FLOOR) -> tuple[dict, bool]:
    """PURE: max_tokens / max_completion_tokens brought down to what the window leaves after
    the prompt and a margin (tools and the generation prompt are not always in the count).
    Never raised, never below the floor; a request with no budget field gets one."""
    if not isinstance(body, dict) or not window or prompt_tokens is None:
        return body, False
    allowed = max(floor, int(window) - int(prompt_tokens) - int(margin))
    keys = [k for k in ("max_tokens", "max_completion_tokens") if k in body]
    if not keys:
        return {**body, "max_tokens": allowed}, True
    out = dict(body)
    changed = False
    for k in keys:
        try:
            asked = int(body[k])
        except (TypeError, ValueError):
            continue
        if asked > allowed:
            out[k] = allowed
            changed = True
    return (out, True) if changed else (body, False)
