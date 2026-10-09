"""Executable checks for the cluster gateway qualification probe."""
import io
import json
import urllib.error

import pytest

from evals.self_improve.cluster_probe import (ProbeError, completed_response,
                                              gateway_url, probe)


class Stream(io.BytesIO):
    def __init__(self, response, *, terminal=True):
        events = [b'data: {"type":"response.created"}\n\n']
        if terminal:
            payload = json.dumps({"type": "response.completed", "response": response})
            events.append(("data: " + payload + "\n\n").encode())
        super().__init__(b"".join(events))
        self.headers = {"Content-Type": "text/event-stream"}


class Gateway:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append((request, timeout))
        return next(self.responses)


def completed(output):
    return {"status": "completed", "model": "cluster-upstream",
            "output": output}


def message(value):
    return {"type": "message", "content": [{"type": "output_text", "text": value}]}


def test_probe_requires_terminal_sse_and_replayed_tool_result(monkeypatch):
    """C-5.1: only a full streamed tool loop qualifies the selected gateway."""
    monkeypatch.setattr("evals.self_improve.cluster_probe.secrets.token_hex", lambda n: "1234567890abcdef")
    call = {"type": "function_call", "name": "athena_probe_value",
            "arguments": "{}", "call_id": "call-1"}
    gateway = Gateway([Stream(completed([message("hello")])),
                       Stream(completed([call])),
                       Stream(completed([message("athena-1234567890abcdef")]))])
    result = probe("http://192.168.1.136:30400/v1", "agent", "private-key",
                   opener=gateway)
    assert result["checks"] == {"sse_terminal": True, "text": True,
                                "function_call": True, "replayed_tool_result": True}
    assert result["requested_model"] == "agent"
    assert "private-key" not in json.dumps(result)
    bodies = [json.loads(request.data) for request, _ in gateway.requests]
    assert all(body["stream"] for body in bodies)
    assert bodies[1]["tool_choice"] == {"type": "function", "name": "athena_probe_value"}
    assert bodies[2]["input"][-1] == {"type": "function_call_output",
                                      "call_id": "call-1", "output": "athena-1234567890abcdef"}
    assert gateway.requests[0][0].get_header("Authorization") == "Bearer private-key"


def test_probe_fails_closed_on_partial_stream_bad_route_and_http_auth():
    """C-5.1: readiness, partial output and rejected credentials are not proof."""
    with pytest.raises(ProbeError, match="response.completed"):
        completed_response(Stream(completed([message("partial")]), terminal=False))
    with pytest.raises(ValueError):
        gateway_url("http://user:secret@host/v1")
    with pytest.raises(ValueError):
        gateway_url("http://host/v1?key=secret")

    class Rejected:
        def open(self, request, *, timeout):
            raise urllib.error.HTTPError(request.full_url, 401, "secret-bearing reason", {}, None)

    with pytest.raises(ProbeError, match="HTTP 401") as caught:
        probe("http://host/v1", "agent", "private-key", opener=Rejected())
    assert "private-key" not in str(caught.value)
