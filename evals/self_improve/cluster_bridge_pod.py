"""Render a small Kubernetes Pod for the Codex-to-cluster Responses bridge.

The manifest contains bridge source code, never credentials. A pre-existing
Secret supplies the upstream and local client keys. Access is by port-forward.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .cluster_probe import gateway_url


DNS_LABEL = re.compile(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?\Z")
SOURCES = ("__init__.py", "cluster_bridge.py", "cluster_probe.py")


def _label(value: str) -> str:
    if len(value) > 63 or not DNS_LABEL.fullmatch(value):
        raise ValueError("Kubernetes names must be DNS labels of at most 63 characters")
    return value


def pod_manifest(*, name: str, namespace: str, secret_name: str,
                 upstream: str, source_dir: Path | None = None) -> dict:
    name, namespace, secret_name = map(_label, (name, namespace, secret_name))
    _label(name + "-code")
    gateway_url(upstream)
    source_dir = source_dir or Path(__file__).parent
    source = {filename: (source_dir / filename).read_text(encoding="utf-8")
              for filename in SOURCES}
    labels = {"app.kubernetes.io/name": "athena-cluster-bridge",
              "app.kubernetes.io/instance": name}
    return {"apiVersion": "v1", "kind": "List", "items": [
        {"apiVersion": "v1", "kind": "ConfigMap",
         "metadata": {"name": name + "-code", "namespace": namespace},
         "data": source},
        {"apiVersion": "v1", "kind": "Pod",
         "metadata": {"name": name, "namespace": namespace, "labels": labels},
         "spec": {"restartPolicy": "Always", "automountServiceAccountToken": False,
                  "securityContext": {"runAsNonRoot": True, "runAsUser": 65532,
                                      "seccompProfile": {"type": "RuntimeDefault"}},
                  "containers": [{
                      "name": "bridge", "image": "python:3.12-alpine",
                      "imagePullPolicy": "IfNotPresent", "workingDir": "/app",
                      "command": ["python", "-m", "evals.self_improve.cluster_bridge"],
                      "args": ["--upstream", upstream,
                               "--upstream-key-env", "ATHENA_CLUSTER_KEY",
                               "--client-key-env", "ATHENA_BRIDGE_CLIENT_KEY",
                               "--port", "8777"],
                      "env": [
                          {"name": "ATHENA_CLUSTER_KEY", "valueFrom": {"secretKeyRef": {
                              "name": secret_name, "key": "upstream-key"}}},
                          {"name": "ATHENA_BRIDGE_CLIENT_KEY", "valueFrom": {"secretKeyRef": {
                              "name": secret_name, "key": "client-key"}}},
                          {"name": "PYTHONDONTWRITEBYTECODE", "value": "1"},
                          {"name": "PYTHONUNBUFFERED", "value": "1"}],
                      "ports": [{"name": "responses", "containerPort": 8777}],
                      "volumeMounts": [{"name": "code", "mountPath": "/app/evals/self_improve",
                                        "readOnly": True}],
                      "resources": {"requests": {"cpu": "25m", "memory": "32Mi"},
                                    "limits": {"cpu": "250m", "memory": "128Mi"}},
                      "securityContext": {"allowPrivilegeEscalation": False,
                                          "readOnlyRootFilesystem": True,
                                          "capabilities": {"drop": ["ALL"]}}
                  }],
                  "volumes": [{"name": "code", "configMap": {"name": name + "-code"}}]}}
    ]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="athena-cluster-bridge")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--secret-name", required=True)
    parser.add_argument("--upstream", required=True)
    args = parser.parse_args()
    try:
        manifest = pod_manifest(name=args.name, namespace=args.namespace,
                                secret_name=args.secret_name, upstream=args.upstream)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
