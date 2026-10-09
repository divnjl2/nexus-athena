"""Check a cluster gateway's Responses transport before an agent benchmark.

The probe sends synthetic inputs only. It never prints a credential or server
response body, and it bypasses workstation HTTP proxies for the explicit URL.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class ProbeError(Exception):
    """A gateway capability was not verified."""


def gateway_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or \
            parsed.username or parsed.password or parsed.query or parsed.fragment or \
            parsed.path.rstrip("/") != "/v1":
        raise ValueError("base URL must be an http(s) /v1 URL without credentials or query")
    return base_url.rstrip("/") + "/responses"


def completed_response(stream) -> dict:
    """Require an actual terminal SSE event; a partial stream is not success."""
    if "text/event-stream" not in stream.headers.get("Content-Type", "").lower():
        raise ProbeError("gateway did not return an SSE stream")
    data_lines: list[str] = []
    completed = None
    total_bytes = 0
    for raw in stream:
        total_bytes += len(raw)
        if total_bytes > 4_000_000:
            raise ProbeError("SSE stream exceeded the probe limit")
        try:
            line = raw.decode("utf-8", "strict").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise ProbeError("SSE stream was not UTF-8") from exc
        if not line:
            if data_lines:
                payload = "\n".join(data_lines)
                data_lines.clear()
                if payload == "[DONE]":
                    continue
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise ProbeError("invalid SSE JSON") from exc
                if not isinstance(event, dict):
                    raise ProbeError("invalid SSE event")
                if event.get("type") == "response.completed":
                    completed = event.get("response")
                elif event.get("type") in ("response.failed", "error"):
                    raise ProbeError("gateway emitted a failure event")
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not isinstance(completed, dict) or completed.get("status") != "completed":
        raise ProbeError("stream ended without response.completed")
    if not isinstance(completed.get("output"), list) or any(
            not isinstance(item, dict) for item in completed["output"]):
        raise ProbeError("completed response has invalid output items")
    return completed


def response_text(response: dict) -> str:
    parts = []
    for item in response["output"]:
        if item.get("type") != "message":
            continue
        if not isinstance(item.get("content"), list):
            raise ProbeError("message has invalid content")
        for part in item["content"]:
            if not isinstance(part, dict):
                raise ProbeError("message has invalid content")
            if part.get("type") == "output_text":
                if not isinstance(part.get("text"), str):
                    raise ProbeError("message has invalid text")
                parts.append(part["text"])
    return "".join(parts)


def request_response(opener, url: str, key: str, body: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps({**body, "stream": True}).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 "Accept": "text/event-stream"}, method="POST")
    try:
        with opener.open(request, timeout=timeout) as stream:
            return completed_response(stream)
    except urllib.error.HTTPError as exc:
        raise ProbeError(f"gateway returned HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProbeError(f"gateway transport failed ({type(exc).__name__})") from None


def probe(base_url: str, model: str, key: str, *, timeout: int = 90,
          opener=None) -> dict:
    if not model or not key or timeout < 1:
        raise ValueError("model, credential and positive timeout are required")
    url = gateway_url(base_url)
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
    first = request_response(opener, url, key,
                             {"model": model, "input": "Reply with one short sentence.",
                              "max_output_tokens": 128}, timeout)
    if not response_text(first).strip():
        raise ProbeError("completed text response had no output")

    tool = {"type": "function", "name": "athena_probe_value",
            "description": "Read a synthetic probe value.",
            "parameters": {"type": "object", "properties": {},
                           "required": [], "additionalProperties": False}}
    user = {"role": "user", "content": "Call athena_probe_value, then report its value."}
    second = request_response(opener, url, key,
                              {"model": model, "input": [user], "tools": [tool],
                               "tool_choice": {"type": "function", "name": tool["name"]},
                               "max_output_tokens": 128}, timeout)
    calls = [item for item in second.get("output", [])
             if item.get("type") == "function_call"]
    if len(calls) != 1 or calls[0].get("name") != tool["name"] or \
            not isinstance(calls[0].get("call_id"), str) or not calls[0]["call_id"]:
        raise ProbeError("forced function call was not returned")
    try:
        arguments = json.loads(calls[0].get("arguments", ""))
    except json.JSONDecodeError as exc:
        raise ProbeError("function arguments were invalid JSON") from exc
    if arguments != {}:
        raise ProbeError("function arguments did not match probe schema")
    value = "athena-" + secrets.token_hex(8)
    tool_output = {"type": "function_call_output", "call_id": calls[0]["call_id"],
                   "output": value}
    third = request_response(opener, url, key,
                             {"model": model, "input": [user, *second["output"], tool_output],
                              "max_output_tokens": 128}, timeout)
    if value not in response_text(third):
        raise ProbeError("follow-up did not use the function result")
    return {"schema": "athena.cluster-probe/1",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "gateway": base_url.rstrip("/"), "requested_model": model,
            "reported_models": [first.get("model"), second.get("model"),
                                third.get("model")],
            "checks": {"sse_terminal": True, "text": True,
                       "function_call": True, "replayed_tool_result": True}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    credential = parser.add_mutually_exclusive_group(required=True)
    credential.add_argument("--key-env", help="name of an environment variable")
    credential.add_argument("--key-file", type=Path, help="path to a private key file")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--output", type=Path, help="write the non-secret result as JSON")
    args = parser.parse_args()
    try:
        key = (os.environ.get(args.key_env, "") if args.key_env else
               args.key_file.read_text(encoding="utf-8").strip())
        result = probe(args.base_url, args.model, key, timeout=args.timeout)
    except OSError:
        print(json.dumps({"schema": "athena.cluster-probe/1", "passed": False,
                          "reason": "credential file unavailable"}))
        return 2
    except (ValueError, ProbeError) as exc:
        print(json.dumps({"schema": "athena.cluster-probe/1", "passed": False,
                          "reason": str(exc)}))
        return 2
    result["passed"] = True
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
