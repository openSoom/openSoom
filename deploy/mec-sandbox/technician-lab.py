"""Install a loopback-only human workbench into the existing private Option C lab."""
import argparse
import base64
import json
import secrets
import subprocess

NAMESPACE = "opensoom-workers"
GATEWAY = "https://os-gateway.opensoom-workers.svc.cluster.local:8443"
CONFIG_SCRIPT = """
import json, os
from pathlib import Path
from opensoom.store import Store
db = Store(Path('/var/lib/opensoom/operations.sqlite'))
site = db.get('facilities', 'food-a')
roles = db.get('config', 'identities')
print(json.dumps({'facility_id': site['id'], 'facility_path': site['path'], 'name': site['name'],
                  'profile': site['profile'], 'simulation': site['simulated'], 'origin': roles['technician:food-a'],
                  'zones': {z['id']: {'name': z['name'], 'target_m3_h': z['minimum_airflow']} for z in site['zones']}}))
"""


def kub(*args, payload=None):
    return subprocess.check_output(["sudo", "k3s", "kubectl", "-n", NAMESPACE, *args],
                                   input=json.dumps(payload) if payload is not None else None, text=True)


def apply(kind, name, *, api="v1", **fields):
    resource = {"apiVersion": api, "kind": kind, "metadata": {"name": name, "namespace": NAMESPACE}, **fields}
    kub("apply", "-f", "-", payload=resource)


def encode(data):
    return base64.b64encode(data.encode()).decode()


def install(image):
    config = json.loads(kub("exec", "deploy/os-operations", "--", "python", "-c", CONFIG_SCRIPT))
    if config["facility_id"] != "food-a" or not config["origin"].startswith("Cos") or config["origin"] == "CAdmin":
        raise ValueError("Expected the commissioned food-a technician AE")
    config.update(cse_url=GATEWAY, cse_ca="/etc/opensoom/trust/ca.crt")
    gateway = json.loads(kub("get", "secret/os-gateway-secret", "-o", "json"))
    tokens = json.loads(base64.b64decode(gateway["data"]["workers.json"]))
    origin = config["origin"]
    if origin not in tokens:
        installed = kub("get", "secret/os-technician-credentials", "--ignore-not-found", "-o", "json")
        tokens[origin] = (base64.b64decode(json.loads(installed)["data"]["cse-token"]).decode()
                          if installed else secrets.token_urlsafe(36))
        patches = [{"op": "test", "path": "/metadata/resourceVersion", "value": gateway["metadata"]["resourceVersion"]},
                   {"op": "replace", "path": "/data/workers.json", "value": encode(json.dumps(tokens))}]
        kub("patch", "secret/os-gateway-secret", "--type=json", "--patch-file=/dev/stdin", payload=patches)
    # The gateway loads its origin/token mapping at process startup.
    kub("rollout", "restart", "deploy/os-gateway")
    kub("rollout", "status", "deploy/os-gateway", "--timeout=120s")
    apply("Secret", "os-technician-credentials", data={"cse-token": encode(tokens[origin])})
    apply("ConfigMap", "os-technician-config", data={"facility.json": json.dumps(config)})
    selector = {"matchLabels": {"app": "os-technician"}}
    container = {"name": "workbench", "image": image, "imagePullPolicy": "IfNotPresent",
                 "args": ["--factory", "opensoom.technician:create_app", "--host", "127.0.0.1", "--port", "8181",
                          "--no-access-log", "--no-proxy-headers"],
                 "securityContext": {"allowPrivilegeEscalation": False, "runAsNonRoot": True,
                                     "runAsUser":65532, "capabilities":{"drop":["ALL"]}},
                 "env": [{"name":"OPENSOOM_TECHNICIAN_CONFIG","value":"/etc/opensoom/site/facility.json"},
                         {"name":"OPENSOOM_TECHNICIAN_CSE_TOKEN","valueFrom":{"secretKeyRef":{
                             "name":"os-technician-credentials","key":"cse-token"}}}],
                 "volumeMounts":[{"name":"site","mountPath":"/etc/opensoom/site","readOnly":True},
                                 {"name":"trust","mountPath":"/etc/opensoom/trust","readOnly":True}]}
    spec = {"containers":[container],"automountServiceAccountToken":False,
            "volumes":[{"name":"site","configMap":{"name":"os-technician-config"}},
                       {"name":"trust","configMap":{"name":"os-worker-trust"}}]}
    apply("Deployment","os-technician",api="apps/v1",
          spec={"replicas":1,"selector":selector,"template":{"metadata":{"labels":selector["matchLabels"]},"spec":spec}})
    kub("rollout","status","deploy/os-technician","--timeout=120s")
    return {"facility_id":config["facility_id"],"technician_ae":origin,"deployment":"os-technician",
            "bind":"127.0.0.1:8181","service_created":False}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image",required=True,help="The preloaded operations image containing the technician package")
    print(json.dumps(install(parser.parse_args().image)))
