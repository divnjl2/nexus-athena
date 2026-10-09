"""Executable checks for the local Codex-to-cluster Responses bridge."""
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from evals.self_improve.cluster_bridge import make_server, normalize_request
from evals.self_improve.cluster_bridge_pod import pod_manifest


def test_bridge_keeps_instruction_text_and_rejects_late_developer():
    """C-5.2: role adaptation preserves text and refuses unsafe reordering."""
    original = {"model": "agent", "stream": True, "instructions": "base policy",
                "input": [{"role": "developer", "content": [
                    {"type": "input_text", "text": "task rule"}]},
                          {"role": "user", "content": "hello"}]}
    converted = normalize_request(original)
    assert converted["instructions"] == "base policy\n\ntask rule"
    assert converted["input"] == [{"role": "user", "content": "hello"}]
    assert original["input"][0]["role"] == "developer"
    with pytest.raises(ValueError, match="after conversation"):
        normalize_request({**original, "input": [original["input"][1], original["input"][0]]})
    with pytest.raises(ValueError, match="text only"):
        normalize_request({**original, "input": [{"role": "developer",
                                                  "content": [{"type": "input_image"}]}]})


def test_bridge_authenticates_and_preserves_sse_bytes():
    """C-5.2: loopback auth and streamed upstream bytes survive the bridge."""
    seen = []
    payload = (b'data: {"type":"response.created"}\n\n'
               b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n')

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            seen.append((self.path, self.headers.get("Authorization"),
                         json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    bridge = make_server(port=0,
                         upstream=f"http://127.0.0.1:{upstream.server_port}/v1",
                         upstream_key="upstream-secret", client_key="client-secret")
    threads = [threading.Thread(target=server.serve_forever, daemon=True)
               for server in (upstream, bridge)]
    for thread in threads:
        thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = f"http://127.0.0.1:{bridge.server_port}/v1/responses"
    body = {"model": "agent", "stream": True, "instructions": "base policy",
            "input": [{"role": "developer", "content": "task rule"},
                      {"role": "user", "content": "hello"}]}
    try:
        def call(key, value=body):
            request = urllib.request.Request(
                url, data=json.dumps(value).encode(), method="POST",
                headers={"Authorization": "Bearer " + key,
                         "Content-Type": "application/json"})
            return opener.open(request, timeout=3)

        with call("client-secret") as response:
            assert response.headers["Content-Type"] == "text/event-stream"
            assert response.read() == payload
        assert len(seen) == 1
        assert seen[0][0] == "/v1/responses"
        assert seen[0][1] == "Bearer upstream-secret"
        assert seen[0][2]["instructions"] == "base policy\n\ntask rule"
        assert seen[0][2]["input"] == [{"role": "user", "content": "hello"}]
        with pytest.raises(urllib.error.HTTPError) as denied:
            call("wrong-secret")
        assert denied.value.code == 401 and len(seen) == 1
        with pytest.raises(urllib.error.HTTPError) as invalid:
            call("client-secret", {**body, "input": [body["input"][1], body["input"][0]]})
        assert invalid.value.code == 400 and len(seen) == 1
    finally:
        for server in (bridge, upstream):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=3)


def test_pod_manifest_uses_secret_refs_and_no_service_exposure():
    """C-5.4: a port-forwarded pod contains code and references external keys."""
    manifest = pod_manifest(name="athena-bridge", namespace="agents",
                            secret_name="bridge-keys",
                            upstream="http://192.168.1.136:30400/v1")
    config, pod = manifest["items"]
    assert [item["kind"] for item in manifest["items"]] == ["ConfigMap", "Pod"]
    assert "normalize_request" in config["data"]["cluster_bridge.py"]
    assert pod["spec"]["automountServiceAccountToken"] is False
    container = pod["spec"]["containers"][0]
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert {entry["valueFrom"]["secretKeyRef"]["key"] for entry in container["env"]
            if "valueFrom" in entry} == {"upstream-key", "client-key"}
    assert all("value" not in entry for entry in container["env"]
               if "valueFrom" in entry)
    assert "Bearer " not in json.dumps(pod)
