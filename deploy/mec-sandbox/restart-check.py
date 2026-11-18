"""Verify a managed maintenance Pod replacement against immutable remote CSE state."""
from datetime import datetime, timezone
import json
import subprocess
import time
from commission import svc
from capture import get, mca

K=["sudo","k3s","kubectl","-n","opensoom-workers"]
S="opensoom.org/placement-owner=sandbox"


def pod():
    rows=json.loads(subprocess.check_output([*K,"get","pod","-l",S,"-o","json"]))["items"]
    return next((r for r in rows if not r["metadata"].get("deletionTimestamp")),None)


def receipt():
    row=mca("mn","/cse-mn/opensoom/facilities/food-a/work_orders/la","CAdmin")
    cin=row["body"]["m2m:cin"]
    data=json.loads(cin["con"])
    return {"ri":cin["ri"],"work_order":data["work_order_id"],"revision":data["revision"],"request_id":row["oneM2M_request_id"],
            "status":row["oneM2M_status"]}


def run():
    before=pod(); assert before
    before_order=receipt()
    start=time.monotonic()
    start_time=datetime.now(timezone.utc).isoformat()
    subprocess.run([*K,"delete","pod",before["metadata"]["name"],"--wait=false"],check=True,stdout=subprocess.DEVNULL)
    ip=json.loads(subprocess.check_output([*K,"get","service/os-maintenance","-o","json"]))["spec"]["clusterIP"]
    for _ in range(100):
        after=pod()
        if after and after["metadata"]["uid"]!=before["metadata"]["uid"]:
            try:
                h=get("http://"+ip+":8080","/health")["body"]
                if h["role"]=="maintenance" and h["scans"]>=1 and not h["last_error"]:
                    break
            except (TimeoutError, OSError, KeyError):
                pass
        time.sleep(1)
    else:
        raise RuntimeError("Managed worker did not resume reconciliation")
    after_order=receipt()
    assert before_order["ri"]==after_order["ri"] and before_order["revision"]==after_order["revision"]==4
    return {"initiated_utc":start_time,"replacement_observed_seconds":round(time.monotonic()-start,3),
            "interruption":"Deliberate maintenance Pod deletion on the selected south Sandbox logical edge.",
            "recovery":"Its existing Kubernetes Deployment recreated the Pod. The host and MN-CSE remained online.",
            "old_pod_uid":before["metadata"]["uid"],"new_pod_uid":after["metadata"]["uid"],
            "health":h,"before_order":before_order,"after_order":after_order}

if __name__=="__main__":
    print(json.dumps(run(),indent=2))
