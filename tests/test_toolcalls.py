"""v3.12 the gateway relay — a tool call that came back as prose becomes a structured call on
the client side; the lanes are not touched.

Each test is the executable spec of one C-6.* clause in features/executor-layer/contract.md.
"""
from __future__ import annotations

import json

from lib.executors import LOCAL_GATEWAY, openhands_config
from lib.toolcalls import extract_calls, normalize_completion

HERMES = '<tool_call>\n{"name": "Read", "arguments": {"file_path": "lib/hooks.py"}}\n</tool_call>'
DISTILLATE = '<tool_call>\n{"function": "glob", "parameter": {"pattern": "**/*", "path": "/"}}\n</tool_call>'
XML = ('<tool_call>\n<function=file_editor>\n<parameter=command>view</parameter>\n'
       '<parameter=path>lib/hooks.py</parameter>\n</function>\n</tool_call>')
OPENAI_SHAPE = 'sure\n<tool_call>{"function": {"name": "grep", "arguments": "{\\"pattern\\": \\"owners_for\\"}"}}</tool_call>'
GARBAGE = '<tool_call>\n{"function_results}\n</function_results>\n</tool_call>'


def _completion(text, tool_calls=None):
    msg = {"role": "assistant", "content": text}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {"id": "x", "object": "chat.completion",
            "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}]}


def test_a_tool_call_left_as_text_becomes_a_structured_call():
    """C-6.1 — the shapes the lane's parser refused (measured) come back as tool_calls, the
    text before the call kept as content, finish_reason tool_calls."""
    assert extract_calls(DISTILLATE) == [{"name": "glob", "arguments": {"pattern": "**/*", "path": "/"}}]
    assert extract_calls(XML) == [{"name": "file_editor", "arguments": {"command": "view", "path": "lib/hooks.py"}}]
    assert extract_calls(HERMES)[0]["name"] == "Read"
    out, changed = normalize_completion(_completion(OPENAI_SHAPE), id_factory=lambda: "call_1")
    assert changed
    msg = out["choices"][0]["message"]
    assert msg["tool_calls"] == [{"id": "call_1", "type": "function",
                                  "function": {"name": "grep", "arguments": json.dumps({"pattern": "owners_for"})}}]
    assert msg["content"] == "sure" and out["choices"][0]["finish_reason"] == "tool_calls"


def test_a_well_formed_completion_passes_through_unchanged():
    """C-6.2 — a response the server already structured, plain prose, or unparsable tags are
    returned exactly as they came."""
    native = _completion(None, tool_calls=[{"id": "c", "type": "function",
                                            "function": {"name": "Read", "arguments": "{}"}}])
    same, changed = normalize_completion(json.loads(json.dumps(native)))
    assert not changed and same == native
    prose = _completion("DONE")
    assert normalize_completion(json.loads(json.dumps(prose))) == (prose, False)
    junk = _completion(GARBAGE)
    out, changed = normalize_completion(json.loads(json.dumps(junk)))
    assert not changed and out["choices"][0]["message"]["content"] == GARBAGE
    assert normalize_completion({"error": "x"}) == ({"error": "x"}, False)


def test_a_tool_carrying_request_goes_out_with_thinking_off():
    """C-6.4 — vLLM #42021: with thinking on, Qwen3.5 hides its tool calls in the reasoning;
    the request-level workaround is applied at the relay, and only where tools are present."""
    from lib.toolcalls import prepare_request
    tools = [{"type": "function", "function": {"name": "glob", "parameters": {"type": "object"}}}]
    body, changed = prepare_request({"model": "m", "messages": [], "tools": tools})
    assert changed and body["chat_template_kwargs"] == {"enable_thinking": False}
    kept, changed = prepare_request({"model": "m", "messages": [], "tools": tools,
                                     "chat_template_kwargs": {"enable_thinking": True}})
    assert not changed and kept["chat_template_kwargs"]["enable_thinking"] is True, "the caller decided"
    merged, _ = prepare_request({"model": "m", "messages": [], "tools": tools,
                                 "chat_template_kwargs": {"x": 1}})
    assert merged["chat_template_kwargs"] == {"x": 1, "enable_thinking": False}
    plain = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    assert prepare_request(dict(plain)) == (plain, False)
    on, changed = prepare_request({"model": "m", "messages": [], "tools": tools}, thinking=True)
    assert changed and on["chat_template_kwargs"]["enable_thinking"] is True


def test_the_openhands_executor_can_be_pointed_at_the_relay():
    """C-6.3 — the relay is a base url like any other: the executor config carries it, and
    the lane behind it is not touched."""
    cfg = openhands_config("# Task", workspace="C:/repo", model="openai/qwopus-27b",
                           base_url="http://127.0.0.1:8414/v1")
    assert cfg["base_url"] == "http://127.0.0.1:8414/v1"
    assert LOCAL_GATEWAY.endswith(":8413"), "the gateway itself stays where the operator put it"
