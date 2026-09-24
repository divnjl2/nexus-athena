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


def prepare_request(body: dict, *, thinking: bool = False) -> tuple[dict, bool]:
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
        text = msg.get("content")
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
