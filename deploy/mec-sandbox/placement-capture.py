"""Capture native Sandbox/Helm ownership, persistent CSE state and per-host execution."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote
from commission import svc
from capture import get, mca

DATA=Path("placement-data")

def kube(*args):
    return json.loads(subprocess.check_output(["sudo","k3s","kubectl","-n","opensoom-workers",*args,"-o","json"]))

def local(name):
    return json.loads((DATA/name).read_text())

def hash_payload(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def capture(side):
    scenario="inspection-"+side
    readback=local("after-"+side+".json")["m2m:cin"]
    old=local("before-south.json" if side=="south" else "before.json")["m2m:cin"]
    apps=local("apps-"+side+".json")
    assert {(a["name"],a["nodeName"]) for a in apps} >= {("inspection-worker",side+"-edge"),("site-mn-cse",side+"-edge")}
    assert old["ri"] == readback["ri"] and old["con"] == readback["con"]
    pods=local("private-pods-"+side+".json")["items"]
    assert len(pods)==2
    releases=kube("get","configmap","-l","owner=helm")
    names=[{"name":i["metadata"]["name"],"uid":i["metadata"]["uid"],"status":i["metadata"]["labels"].get("status")}
           for i in releases["items"] if i["metadata"]["labels"].get("name","").startswith("meep-"+scenario+"-")]
    assert len(names)==2 and all(r["status"]=="deployed" for r in names)
    base=svc("meep-platform-ctrl")
    topology=get(base,"/platform-ctrl/v1/scenarios/"+scenario)
    assert topology["http"] == 200
    log=subprocess.check_output(["sudo","k3s","kubectl","logs","deployment/meep-virt-engine","--tail=1500"],text=True)
    import re
    lines=[re.sub(r"\x1b\[[0-9;]*m","",line) for line in log.splitlines() if "Installing chart: meep-"+scenario+"-" in line]
    assert len(lines)>=2
    csrs=mca("in","/cse-in?fu=1&ty=16","CAdmin")
    links=csrs["body"]["m2m:uril"]
    csr=next((mca("in","/"+link,"CAdmin") for link in links if "mn" in link.lower()),None)
    if not csr or csr["body"].get("m2m:csr",{}).get("csi")!="/opensoom-mn":
        raise RuntimeError("MN registration under central CSE was not retrieved")
    health=get(svc_worker("os-maintenance"),"/health")
    if health["http"]!=200 or health["body"].get("last_error"):
        raise RuntimeError("Managed maintenance worker is not ready: "+str(health))
    data={"captured_utc":datetime.now(timezone.utc).isoformat(),"side":side,"scenario":scenario,
       "physical_hosts":1,"logical_mec_hosts":["north-edge","south-edge"],
       "selection":"Scenario author selected the logical installation target. Sandbox controller and Virt Engine created the workloads.",
       "logical_app_instances":apps,"helm_configmap_receipts":names,"orchestrator_install_log":lines,
       "registered_topology":topology,"cse_csr":csr,"maintenance_health":health,
       "before_work_order":{"ri":old["ri"],"created":old["ct"],"content_sha256":hash_payload(old["con"])},
       "after_work_order":{"ri":readback["ri"],"created":readback["ct"],"content_sha256":hash_payload(readback["con"])},
       "pods":[{"name":p["metadata"]["name"],"uid":p["metadata"]["uid"],"logical_host":p["metadata"]["labels"]["opensoom.org/logical-host"],
                "kubernetes_node":p["spec"]["nodeName"],"created":p["metadata"]["creationTimestamp"],
                "images":[{"image":s["image"],"image_id":s["imageID"],"ready":s["ready"]} for s in p["status"]["containerStatuses"]]} for p in pods]}
    return data

def svc_worker(name):
    ip=kube("get","svc",name)["spec"]["clusterIP"]
    return f"http://{ip}:8080"

if __name__=="__main__":
    import sys
    print(json.dumps(capture(sys.argv[1]),indent=2))
