"""Run from stdin inside the isolated test facility's os-operations Pod."""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4
import httpx
from opensoom.onem2m import CSEClient, CSEError


def subscribe():
    base = os.environ["OPENSOOM_CSE_BASE"] + "/opensoom/facilities/food-a"
    out=[]
    with CSEClient(os.environ["OPENSOOM_CSE_URL"]) as cse:
        for stream, role in [("outcomes","maintenance"),("sensor_requests","bridge"),("sensor_responses","maintenance"),("provider_requests","bridge")]:
            target=base+"/"+stream
            rn="notify-"+role
            address="http://os-"+role+".opensoom-workers.svc.cluster.local:8080/notify"
            sub={"rn":rn,"nu":[address],"enc":{"net":[3],"chty":[4]},"nct":1}
            try:
                res=cse.create(target,23,{"m2m:sub":sub})
            except CSEError as err:
                if err.rsc!=4105:
                    raise
                res=cse.retrieve(target+"/"+rn)
            actual=res["body"]["m2m:sub"]
            if address not in actual["nu"]:
                raise ValueError("Existing subscription has an unexpected callback")
            out.append({"resource_id":actual["ri"],"request_id":res["rqi"]})
    return out


def run(action):
    if action=="subscribe":
        return subscribe()
    creds=json.loads(Path("/var/lib/opensoom/service-credentials.json").read_text())
    base="http://127.0.0.1:8080/api"
    if action=="start":
        route="/demo/start"
        payload={"facility_id":"food-a","scenario":"no_recovery","autorun":True}
        token=creds["operator_token"]
    else:
        route="/tools/commission_provider"
        payload={"arguments":{"facility_id":"food-a","provider_profile":"independent-shaft-provider","request_id":"lab-"+uuid4().hex[:12]}}
        token=creds["admin_token"]
    with httpx.Client(trust_env=False,timeout=15) as client:
        response=client.post(base+route,json=payload,headers={"Authorization":"Bearer "+token})
        response.raise_for_status()
        return response.json()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["subscribe","commission","start"])
    print(json.dumps(run(parser.parse_args().action),indent=2))
