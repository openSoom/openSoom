"""Install the private demo facility using the production worker manifest renderer."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess

from workloads import workload

ROOT = Path(__file__).resolve().parents[2]
NS = "opensoom-workers"
GATEWAY = "https://os-gateway.opensoom-workers.svc.cluster.local:8443"
REGISTRY = "http://opensoom-mec-ingress.default.svc.cluster.local"
ROLE_NAMES = ["maintenance", "bridge", "sensor"]
SPEC = importlib.util.spec_from_file_location("worker_deploy", ROOT/"apps/mec-maintenance/deployment.py")
worker_deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker_deploy)


def identity(role):
    return "Cos" + role + hashlib.sha256(b"food-a").hexdigest()[:16]


def resource(kind, name, **fields):
    version = {"NetworkPolicy":"networking.k8s.io/v1"}.get(kind, "v1")
    return {"apiVersion":version,"kind":kind,"metadata":{"namespace":NS,"name":name},**fields}


def token_secret(name, values):
    encoded={k:base64.b64encode(v.encode()).decode() for k,v in values.items()}
    return resource("Secret",name,data=encoded)


def render(args):
    state = args.state.resolve()
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    store = state/"roles.json"
    if not store.exists():
        with open(store,"x",opener=lambda path,flags: os.open(path,flags,0o600)) as handle:
            json.dump({identity(r):secrets.token_urlsafe(32) for r in ROLE_NAMES},handle)
    tokens=json.loads(store.read_text())
    cert,key = state/"tls.crt",state/"tls.key"
    if cert.exists() != key.exists():
        raise ValueError("The gateway certificate and key must be restored together.")
    if not cert.exists():
        subprocess.run(["openssl","req","-x509","-newkey","rsa:2048","-nodes","-days","30",
            "-subj","/CN=os-gateway.opensoom-workers.svc.cluster.local","-addext",
            "subjectAltName=DNS:os-gateway.opensoom-workers.svc.cluster.local","-keyout",str(key),"-out",str(cert)],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    items=[{"apiVersion":"v1","kind":"Namespace","metadata":{"name":NS}},
           resource("ConfigMap","os-worker-trust",data={"ca.crt":cert.read_text()}),
           token_secret("os-gateway-secret",{"tls.crt":cert.read_text(),"tls.key":key.read_text(),"workers.json":json.dumps(tokens)})]
    for role in ("maintenance","bridge"):
        items.append(token_secret("os-"+role+"-credentials",{"cse-token":tokens[identity(role)]}))
    mn="http://opensoom-mn.default.svc.cluster.local:8080"
    operations,ops_svc=workload("os-operations",args.operations,8080,
        {"OPENSOOM_CSE_URL":mn,"OPENSOOM_CSE_BASE":"cse-mn",
         "OPENSOOM_NOTIFY_URL":"http://os-operations.opensoom-workers.svc.cluster.local:8080/api/notify",
         "OPENSOOM_RUNTIME_DIR":"/var/lib/opensoom","OPENSOOM_FACILITY_IDS":"food-a,learning-b"},
        ["opensoom.app:app","--host","0.0.0.0","--port","8080","--no-access-log"])
    gateway,gateway_svc=workload("os-gateway",args.operations,8443,
        {"OPENSOOM_CSE_URL":mn,"OPENSOOM_WORKER_CREDENTIALS_FILE":"/etc/opensoom/server/workers.json"},
        ["--factory","opensoom.worker_access:create_app","--host","0.0.0.0","--port","8443",
         "--ssl-certfile","/etc/opensoom/server/tls.crt","--ssl-keyfile","/etc/opensoom/server/tls.key","--no-access-log"])
    for obj in [operations,ops_svc,gateway,gateway_svc]:
        obj["metadata"]["namespace"]=NS
    for dep,src,mount in [(operations,{"emptyDir":{}},"/var/lib/opensoom"),
                            (gateway,{"secret":{"secretName":"os-gateway-secret"}},"/etc/opensoom/server")]:
        spec=dep["spec"]["template"]["spec"]
        spec["securityContext"]={"runAsNonRoot":True,"runAsUser":65532,"fsGroup":65532,"seccompProfile":{"type":"RuntimeDefault"}}
        spec["volumes"]=[{"name":"run",**src}]
        spec["containers"][0].update({"volumeMounts":[{"name":"run","mountPath":mount,"readOnly":"secret" in src}],
            "securityContext":{"allowPrivilegeEscalation":False,"readOnlyRootFilesystem":True,"capabilities":{"drop":["ALL"]}}})
    items.extend([operations,ops_svc,gateway,gateway_svc])
    profile=next(x["maintenance"] for x in json.loads((ROOT/"config/facilities.json").read_text())["facilities"] if x["id"]=="food-a")
    record=json.loads(args.record.read_text())
    if isinstance(record,list): record=record[1]
    role_configs={}
    for role in ("maintenance","bridge"):
        conf={k:v for k,v in profile.items() if k!="provider_profiles"}
        conf.update({"origin":identity(role),"facility_id":"food-a","facility_path":"cse-mn/opensoom/facilities/food-a",
                     "cse_url":GATEWAY,"cse_ca":"/etc/opensoom/trust/ca.crt","poll_seconds":3})
        if role=="bridge":
            conf.update({"bridge_mode":"mec046","registry_url":REGISTRY+"/mec_service_mgmt/v1/services",
                "allowed_service_origins":[REGISTRY],"sensor_type":"FLX","sensor_test_callback":"http://os-bridge.opensoom-workers.svc.cluster.local:8080/mec046/test","provider_sensor_ids":{"shaft-position-01":args.sensor_ri},
                "provider_registration":{"profile":"independent-shaft-provider","record":record}})
        role_configs[role]=worker_deploy.settings(conf,role)
        egress=[{"to":[{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"kube-system"}},
                        "podSelector":{"matchLabels":{"k8s-app":"kube-dns"}}}],"ports":[{"protocol":x,"port":53} for x in ("UDP","TCP")]},
                {"to":[{"podSelector":{"matchLabels":{"app":"os-gateway"}}}],"ports":[{"port":8443}]}]
        if role=="bridge":
            egress.append({"to":[{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"default"}},
                        "podSelector":{"matchLabels":{"app":"opensoom-mec-ingress"}}}],"ports":[{"port":80}]})
        items.append(resource("NetworkPolicy","os-"+role+"-egress",spec={"podSelector":{"matchLabels":{"app":"os-"+role}},
                    "policyTypes":["Egress"],"egress":egress}))
    items.extend(worker_deploy.kubernetes(args.worker,role_configs,NS)["items"])
    return {"apiVersion":"v1","kind":"List","items":items}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state",type=Path,required=True,help="Private local directory for this test's credentials")
    parser.add_argument("--record",type=Path,required=True,help="Approved provider profile or native 033 registration response")
    parser.add_argument("--sensor-ri",required=True)
    parser.add_argument("--worker",required=True)
    parser.add_argument("--operations",required=True)
    arguments=parser.parse_args()
    payload=json.dumps(render(arguments))
    subprocess.run(["sudo","k3s","kubectl","apply","-f","-"],input=payload,text=True,check=True)
