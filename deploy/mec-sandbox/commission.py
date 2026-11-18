"""Register the headless service instances and the independent provider over native APIs."""
import json
import os
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

def svc(name, port=80):
    addr = subprocess.check_output(["sudo","k3s","kubectl","get","svc",name,"-o","jsonpath={.spec.clusterIP}"],text=True)
    return f"http://{addr}:{port}"

def api(method, url, data=None):
    request = Request(url, method=method, headers={"Content-Type":"application/json"},
                      data=json.dumps(data).encode() if data is not None else None)
    try:
        with urlopen(request, timeout=8) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except HTTPError as err:
        raise RuntimeError(f"{method} {url.split('/',3)[-1]}: {err.code} {err.read().decode()[:180]}") from err

def register_provider():
    base = svc("mep1-meep-iot") + "/iots/v1/registered_iot_platforms"
    data = {"iotPlatformId":"opensoom-position-provider","enabled":True,
        "userTransportInfo":[{"id":"position-events","name":"Provider MQTT","type":"MB_TOPIC_BASED",
                              "protocol":"MQTT","version":"3.1.1",
                              "endpoint":{"addresses":[{"host":"opensoom-provider-events.default.svc.cluster.local","port":1883}]},
                              "security":{},"implSpecificInfo":{}}],
        "customServicesTransportInfo":[{"id":"positions","name":"cse-provider","type":"REST_HTTP",
                                  "protocol":"REST_HTTP","version":"4",
                                  "endpoint":{"addresses":[{"host":"opensoom-provider.default.svc.cluster.local","port":8080}]}}]}
    try:
        _, existing = api("GET", base)
    except RuntimeError as err:
        if ": 404" not in str(err):
            raise
        existing = []
    if any(entry["iotPlatformId"] == data["iotPlatformId"] for entry in (existing or [])):
        return api("GET",base+"/"+data["iotPlatformId"])
    return api("POST",base,data)

def admit_services():
    base = svc("meep-sandbox-ctrl") + "/sandbox-ctrl/v1/applications"
    _, existing = api("GET",base)
    known={row["id"] for row in (existing or [])}
    results=[]
    for index, name in enumerate(("meep-app-enablement","meep-iot","meep-sss"), 1):
        entry={"id":f"48a303e4-4ecc-4c3d-ad00-{index:012d}","name":"mep1-"+name,"nodeName":"mep1","type":"USER"}
        results.append(api("GET",base+"/"+entry["id"]) if entry["id"] in known else api("POST",base,entry))
    return results

if __name__ == "__main__":
    import sys
    name=sys.argv[1]
    print(json.dumps(register_provider() if name=="provider" else admit_services(),indent=2))
