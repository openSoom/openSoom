"""Capture only allowlisted project data from the private, real service endpoints."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from uuid import uuid4
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from commission import svc


def get(base, path, extra=None):
    start=datetime.now(timezone.utc).isoformat()
    req=Request(base+path, headers=extra or {})
    try:
        response=urlopen(req,timeout=5)
    except HTTPError as err:
        response=err
    with response:
        body=response.read()
        return {"method":"GET","path":path,"requested_utc":start,"http":response.status,
                "oneM2M_request_id":(extra or {}).get("X-M2M-RI"),"oneM2M_status":response.headers.get("X-M2M-RSC"),
                "body":json.loads(body) if body else None}

def mca(name, resource, origin):
    return get(svc("opensoom-"+name,8080),resource,{"X-M2M-Origin":origin,"X-M2M-RI":"os-capture-"+uuid4().hex[:12],"X-M2M-RVI":"4"})

def capture():
    gateway=svc("opensoom-mec-ingress")
    provider=mca("provider","/cse-provider/transducer/shaft","CAdmin")
    ri=provider["body"]["os:shaft"]["ri"]
    admissions=get(svc("meep-sandbox-ctrl"),"/sandbox-ctrl/v1/applications")
    registry=get(gateway,"/mec_service_mgmt/v1/services")
    platform=get(gateway,"/opensoom/mep1/iots/v1/registered_iot_platforms/opensoom-position-provider")
    discovery=get(gateway,"/opensoom/mep1/sens/v1/queries/sensor_discovery?"+urlencode({"type":"FLX","sensorPropertyList":"saref:any"}))
    reading=get(gateway,"/opensoom/mep1/sens/v1/queries/sensor_data?sensorIdentifier="+ri)
    missing=get(gateway,"/opensoom/mep1/sens/v1/queries/sensor_data?sensorIdentifier=unknown-opensoom-sensor")
    workloads=json.loads(subprocess.check_output(["sudo","k3s","kubectl","get","pods","-o","json"]))
    pods=[{"name":item["metadata"]["name"],"uid":item["metadata"]["uid"],
           "phase":item["status"]["phase"],"node":item["spec"].get("nodeName"),
           "containers":[{"name":c["name"],"digest":c.get("imageID"),"ready":c["ready"]}
                         for c in item["status"].get("containerStatuses",[])]}
          for item in workloads["items"]]
    sample=json.loads(next(item["CharacteristicValue"] for item in json.loads(reading["body"]["data"]) if item["CharacteristicName"]=="sample"))
    assert reading["http"]==discovery["http"]==platform["http"]==registry["http"]==200
    assert any(s["sensorIdentifier"]==ri for s in discovery["body"])
    assert {row["serCategory"]["id"] for row in registry["body"]} >= {"sssId","iotId"}
    assert sample["value"]==35 and sample["simulated"] and sample["source"]=="independent_position_sensor"
    return {"captured_utc":datetime.now(timezone.utc).isoformat(),"upstream_revision":"8c66f08e443be174f109fe2ac645247c9afcd449",
            "physical_host_count":1,"workloads":pods,"controller_admissions":admissions,"native_registry":registry,
            "native_033_provider":platform,"native_046_discovery":discovery,"native_046_data":reading,
            "native_046_missing":missing,"provider_mca_latest":provider,"mapped_sample":sample,
            "registration_receipt":json.loads(Path("provider-registration.json").read_text())}

if __name__=="__main__":
    print(json.dumps(capture(),indent=2))
