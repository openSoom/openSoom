"""Build the colocated MN Helm chart and its private, stable service route."""
import json
import subprocess
from workloads import workload

source=json.loads(subprocess.check_output(["sudo","k3s","kubectl","get","deployment/opensoom-mn","-o","json"]))
template=source["spec"]["template"]
name="os-managed-mn"
key="opensoom.org/logical-host"
template["metadata"]["labels"]={"app":name,key:"{{ .Values.logicalHost }}"}
labels={"app":name}
cse={"apiVersion":"apps/v1","kind":"Deployment","metadata":{"name":name,"labels":{key:"{{ .Values.logicalHost }}"}},
     "spec":{"replicas":1,"strategy":{"type":"Recreate"},"selector":{"matchLabels":labels},"template":template}}
chart={"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"opensoom-managed-mn-chart"},"data":{
    "chart":"apiVersion: v2\nname: opensoom-site-mn\nversion: 0.1.0\ntype: application\n",
    "cse":json.dumps(cse),"north":"logicalHost: north-edge\n","south":"logicalHost: south-edge\n"}}
svc={"apiVersion":"v1","kind":"Service","metadata":{"name":name,"namespace":"opensoom-workers"},
     "spec":{"selector":labels,"ports":[{"port":8080,"targetPort":8080}]}}
# Keep the original CSE DNS, port and Service IP for callbacks and Mcc while
# its only storage owner moves to the platform-managed namespace.
route,_=workload("opensoom-mn-relay","nginx:1.28.0-alpine",8080)
rspec=route["spec"]["template"]["spec"]
rspec["volumes"]=[{"name":"config","configMap":{"name":"opensoom-mn-route"}}]
rspec["containers"][0]["volumeMounts"]=[{"name":"config","mountPath":"/etc/nginx/conf.d","readOnly":True}]
conf={"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"opensoom-mn-route"},
      "data":{"mn.conf":"server { listen 8080; location / { proxy_pass http://os-managed-mn.opensoom-workers.svc.cluster.local:8080; } }"}}
print(json.dumps({"apiVersion":"v1","kind":"List","items":[chart,svc,conf,route]}))
