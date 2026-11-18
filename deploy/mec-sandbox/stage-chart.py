"""Derive a chart for the very same worker image, config, service and CSE identity."""
import copy
import json
import subprocess

worker_ns="opensoom-workers"
obj=json.loads(subprocess.check_output(["sudo","k3s","kubectl","-n",worker_ns,"get","deployment/os-maintenance","-o","json"]))
template=copy.deepcopy(obj["spec"]["template"])
key="opensoom.org/placement-owner"
labels=template["metadata"]["labels"]
labels[key]="sandbox"
labels["opensoom.org/logical-host"]="{{ .Values.logicalHost }}"
selector={key:"sandbox","app":"os-maintenance"}
resource={"apiVersion":"apps/v1","kind":"Deployment","metadata":{
    "name":"os-managed-maintenance","labels":{"opensoom.org/logical-host":"{{ .Values.logicalHost }}"}},
    "spec":{"replicas":1,"strategy":{"type":"Recreate"},"selector":{"matchLabels":selector},"template":template}}
# Helm stores the rendered manifest as a ConfigMap. Credentials stay Secret refs.
for c in template["spec"]["containers"]:
    for e in c.get("env",[]):
        if any(t in e["name"] for t in ["TOKEN","PASSWORD","SECRET","PRIVATE_KEY"]) and "value" in e:
            raise ValueError("inline confidential value would be persisted")
chart={"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"opensoom-managed-chart"},"data":{
    "chart":"apiVersion: v2\nname: opensoom-maintenance\nversion: 0.1.0\ntype: application\n",
    "worker":json.dumps(resource),"north":"logicalHost: north-edge\n","south":"logicalHost: south-edge\n"}}
print(json.dumps(chart))
