"""Loopback Responses bridge for Codex and Qwen-backed cluster lanes.

Codex places a leading developer message in ``input``. Some Qwen chat
templates only accept one leading system instruction. The bridge appends the
developer text to ``instructions`` and streams the upstream response verbatim.
Both client and upstream keys are supplied outside Git and never logged.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .cluster_probe import gateway_url


MAX_BODY_BYTES = 8_000_000


def _text_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(isinstance(part, dict) and
                                         part.get("type") == "input_text" and
                                         isinstance(part.get("text"), str)
                                         for part in content):
        return "".join(part["text"] for part in content)
    raise ValueError("developer content must contain text only")


def normalize_request(body: dict) -> dict:
    """Preserve request fields and all instruction text while removing late roles."""
    if not isinstance(body, dict) or not isinstance(body.get("input"), list) or \
            not isinstance(body.get("model"), str) or body.get("stream") is not True:
        raise ValueError("streamed Responses input and model are required")
    instruction = body.get("instructions")
    if instruction is not None and not isinstance(instruction, str):
        raise ValueError("instructions must be text")
    input_items = body["input"]
    leading = []
    index = 0
    while index < len(input_items):
        item = input_items[index]
        if not isinstance(item, dict) or item.get("role") != "developer":
            break
        leading.append(_text_content(item.get("content")))
        index += 1
    if any(isinstance(item, dict) and item.get("role") == "developer"
           for item in input_items[index:]):
        raise ValueError("developer message appeared after conversation input")
    if not leading:
        return body
    result = dict(body)
    result["instructions"] = "\n\n".join(part for part in [instruction or "", *leading] if part)
    result["input"] = input_items[index:]
    return result


def make_server(*, port: int, upstream: str, upstream_key: str,
                client_key: str, timeout: int = 300) -> ThreadingHTTPServer:
    if not 0 <= port <= 65535 or not upstream_key or not client_key or timeout < 1:
        raise ValueError("port, both keys and positive timeout are required")
    endpoint = gateway_url(upstream)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _json_error(self, status: int, message: str) -> None:
            payload = json.dumps({"error": {"message": message}}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            if self.path != "/v1/responses":
                self._json_error(404, "unknown endpoint")
                return
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied, "Bearer " + client_key):
                self._json_error(401, "bridge authentication failed")
                return
            try:
                size = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._json_error(411, "content length required")
                return
            if not 0 < size <= MAX_BODY_BYTES:
                self._json_error(413, "request body outside bridge limit")
                return
            try:
                body = json.loads(self.rfile.read(size))
                normalized = normalize_request(body)
            except (json.JSONDecodeError, ValueError):
                self._json_error(400, "unsupported Responses request")
                return
            request = urllib.request.Request(
                endpoint, data=json.dumps(normalized).encode("utf-8"),
                headers={"Authorization": "Bearer " + upstream_key,
                         "Content-Type": "application/json",
                         "Accept": "text/event-stream"}, method="POST")
            headers_sent = False
            try:
                with opener.open(request, timeout=timeout) as response:
                    content_type = response.headers.get("Content-Type", "")
                    if "text/event-stream" not in content_type.lower():
                        self._json_error(502, "upstream did not stream SSE")
                        return
                    self.send_response(response.status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    headers_sent = True
                    for line in response:
                        self.wfile.write(line)
                        self.wfile.flush()
            except urllib.error.HTTPError as exc:
                self._json_error(exc.code, f"upstream HTTP {exc.code}")
            except (urllib.error.URLError, TimeoutError, OSError):
                if headers_sent:
                    # A truncated SSE stream must not become a completed turn.
                    self.close_connection = True
                else:
                    self._json_error(502, "upstream transport failed")

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", required=True, help="cluster gateway /v1 URL")
    parser.add_argument("--upstream-key-env")
    parser.add_argument("--upstream-key-file", type=Path)
    parser.add_argument("--client-key-env", required=True)
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if bool(args.upstream_key_env) == bool(args.upstream_key_file):
        parser.error("choose exactly one upstream key source")
    upstream_key = (os.environ.get(args.upstream_key_env, "") if args.upstream_key_env else
                    args.upstream_key_file.read_text(encoding="utf-8").strip())
    client_key = os.environ.get(args.client_key_env, "")
    with make_server(port=args.port, upstream=args.upstream,
                     upstream_key=upstream_key, client_key=client_key,
                     timeout=args.timeout) as server:
        print(json.dumps({"schema": "athena.cluster-bridge/1",
                          "listen": f"127.0.0.1:{server.server_port}",
                          "upstream": args.upstream, "ready": True}), flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
