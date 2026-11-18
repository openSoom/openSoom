"""Exercise the normal loopback workbench HTTP API inside its private test Pod."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import time
from uuid import NAMESPACE_URL, uuid5

import httpx

from opensoom.onem2m import CSEClient, CSEError
from opensoom.store import Store


def capture(run_id):
    base = "http://127.0.0.1:8181"
    with httpx.Client(base_url=base, timeout=90, trust_env=False) as client:
        unauthorized = client.get("/api/work-orders").status_code
        assert unauthorized == 401
        client.get("/").raise_for_status()
        queue = client.get("/api/work-orders").raise_for_status().json()
        order = next(w for w in queue["work_orders"] if w["run_id"] == run_id)
        assert order["mode"] == "mec046" and order["evidence_status"] == "verified_independent_sample"
        assert order["target_source"] == "work_order_cin" and order["status"] == "open"
        assert order["sample"]["value"] == 35 and order["priority"] == "inspect_actuator_feedback"
        older = [w for w in queue["work_orders"] if w["run_id"] != run_id and w.get("mode") == "mec046"]
        path = "/api/work-orders/" + order["work_order_id"] + "/inspections"
        request_id = str(uuid5(NAMESPACE_URL, "urn:opensoom:cloud:inspection:" + order["resource_id"]))
        form = {"work_order_ri": order["resource_id"], "request_id": request_id, "action":"scheduled",
                "note":"Arrange linkage travel check at the next accessible window."}
        bad_origin = client.post(path, headers={"Origin":"https://foreign.example"}, json=form).status_code
        headers = {"Origin":base}
        stale = client.post(path,headers=headers,json={**form,"work_order_ri":"old-cin"}).status_code
        assert (bad_origin,stale) == (403,409)
        first = client.post(path,headers=headers,json=form).raise_for_status().json()
        retry = client.post(path,headers=headers,json=form).raise_for_status().json()
        assert first["resource_id"] == retry["resource_id"] and first["read_rqi"] != retry["read_rqi"]
        again = client.get("/api/work-orders").raise_for_status().json()
        viewed = next(w for w in again["work_orders"] if w["resource_id"] == form["work_order_ri"])
        entries = [i for i in viewed["inspections"] if i["request_id"] == request_id]
        assert len(entries) == 1 and entries[0]["note"] == form["note"]
    config = json.loads(Path(os.environ["OPENSOOM_TECHNICIAN_CONFIG"]).read_text())
    with CSEClient(config["cse_url"],config["origin"],ca_file=config["cse_ca"],
                   bearer_token=os.environ["OPENSOOM_TECHNICIAN_CSE_TOKEN"]) as cse:
        def denied(path):
            try:
                cse.retrieve(path)
            except CSEError as exc:
                assert exc.rsc == 4103
                return {"rsc":exc.rsc,"rqi":exc.result["rqi"]}
            raise AssertionError("Unexpected access")
        forbidden = denied(config["facility_path"]+"/sensor_responses")
        other = denied(config["facility_path"].rsplit("/",1)[0]+"/learning-b/lounge/observations")
    keep = ("run_id","zone_id","asset_id","work_order_id","resource_id","read_rqi","incident_id","command_id",
            "target_source","target_airflow_m3_h","configured_target_m3_h","airflow","revision","status",
            "priority","requested_pct","sample","mode","evidence_status","provider_receipt")
    return {"observed_at":datetime.now(timezone.utc).isoformat(),"workbench_origin":base,"anonymous_get_http":unauthorized,
            "wrong_origin_post_http":bad_origin,"stale_cin_post_http":stale,"facility":queue["facility"],
            "queue_size":len(queue["work_orders"]),"existing_mec_orders_in_queue":len(older),
            "legacy_target_sources":sorted({w["target_source"] for w in older}),"reviewed_order":{k:order.get(k) for k in keep},
            "entry":{k:v for k,v in first.items() if k!="note"},"private_note_sha256":hashlib.sha256(form["note"].encode()).hexdigest(),
            "repeat_entry_ri":retry["resource_id"],"repeat_read_rqi":retry["read_rqi"],"same_request_entries":len(entries),
            "private_note_reread_in_technician_queue":True,"denied_sensor_responses":forbidden,"denied_other_site":other}


def operator_snapshot(run_id, expected_entry):
    """Read the operator's projection and native command state on either side of the field entry."""
    runtime = Path("/var/lib/opensoom")
    origin = Store(runtime / "operations.sqlite").get("config", "identities")["operator"]
    token = json.loads((runtime / "service-credentials.json").read_text())["operator_token"]
    deadline = time.monotonic() + 45
    with httpx.Client(base_url="http://127.0.0.1:8080", trust_env=False, timeout=40,
                      headers={"Authorization": "Bearer " + token}) as client, CSEClient(
                          os.environ["OPENSOOM_CSE_URL"], origin) as cse:
        while time.monotonic() < deadline:
            state = client.get("/api/state").raise_for_status().json()
            work = next((item for item in state["work_orders"] if item.get("run_id") == run_id
                         and item.get("evidence_status") == "verified_independent_sample"), None)
            if work:
                activity = work.get("latest_technician_activity") or {}
                if expected_entry is None or activity.get("resource_id") == expected_entry:
                    break
            time.sleep(1)
        else:
            raise RuntimeError("The operator has not received the expected current order or inspection.")
        incident = next(item for item in state["incidents"] if item["id"] == work["incident_id"])
        site = os.environ["OPENSOOM_CSE_BASE"] + "/opensoom/facilities/food-a"
        commands = cse.retrieve(site + "/cook/commands")
        assert incident["status"] == work["status"] == "open"
        return {"run_id": run_id, "work_order_id": work["work_order_id"], "work_order_ri": work["resource_id"],
                "incident_status": incident["status"], "work_order_status": work["status"],
                "projected_disposition": activity or None,
                "command_ids": sorted(item["id"] for item in state["commands"]),
                "native_command_container": {k: commands["body"]["m2m:cnt"][k] for k in ("ri", "st", "cni")},
                "native_rqi": commands["rqi"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--operator", action="store_true", help="Run inside the operations Pod to read the projection")
    parser.add_argument("--expected-entry", help="Wait for the recorded technician entry at the operator")
    args = parser.parse_args()
    if args.expected_entry and not args.operator:
        parser.error("--expected-entry requires --operator")
    result = operator_snapshot(args.run_id, args.expected_entry) if args.operator else capture(args.run_id)
    print(json.dumps(result, indent=2))
