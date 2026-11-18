#!/usr/bin/env python3
"""Replay a field inspection and later operating recovery against a private ACME instance."""
import argparse
import hashlib
import json
import os
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from cse_multiapp_smoke import ROOT, child_env, start_cse, stop_process
from facility_worker_acceptance import notify_sink
from opensoom import maintenance
from opensoom.core import Core
from opensoom.facility_pack import worker_templates
from opensoom.maintenance_worker import MaintenanceWorker, read_content
from opensoom.models import ActionRequest, Observation, utcnow
from opensoom.onem2m import CSEClient
from opensoom.technician import FieldDesk, build_app


def source_hashes():
    names = ("scripts/field_recovery_acceptance.py", "src/opensoom/core.py", "src/opensoom/maintenance.py",
             "src/opensoom/maintenance_worker.py", "src/opensoom/technician.py", "src/opensoom/policy.py")
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def run():
    before = source_hashes()
    with ExitStack() as stack:
        tmp = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="opensoom-inspection-recovery-")))
        processes = []
        stack.callback(lambda: [stop_process(proc) for proc in processes])
        url, _, version = start_cse(tmp, processes)
        sink = notify_sink()
        stack.callback(sink.server_close)
        stack.callback(sink.shutdown)
        env = {**child_env(), "OPENSOOM_CSE_BASE": "cse-multiapp",
               "OPENSOOM_NOTIFY_URL": f"http://127.0.0.1:{sink.server_port}/notify"}
        stack.enter_context(patch.dict(os.environ, env, clear=True))
        core = Core(tmp / "site", stack.enter_context(CSEClient(url)))
        core.bootstrap()
        fid, zid = "food-a", "cook"
        actor = {"role": "operator", "facilities": [fid]}
        run_id = core.start_demo(fid, "normal", False, actor)["run_id"]
        facility = core.facility(fid)
        zone = core.zone(facility, zid)
        conf = worker_templates(core, fid)
        field_config = {"facility_id": fid, "facility_path": facility["path"], "profile": facility["profile"],
                        "name": facility["name"], "simulation": True,
                        "zones": {z["id"]: {"name": z["name"], "target_m3_h": z["minimum_airflow"]} for z in facility["zones"]}}
        field = FieldDesk(field_config, CSEClient(url, core.identities["technician:" + fid]))
        site_origin = "http://127.0.0.1:19888"
        technician = stack.enter_context(TestClient(build_app(field), base_url=site_origin, client=("127.0.0.1", 50123)))
        technician.get("/").raise_for_status()

        def worker(role):
            item = MaintenanceWorker(role, {**conf[role], "bridge_mode": "local", "cse_url": url})
            stack.callback(item.close)
            return item

        def publish(flow):
            obs = Observation(facility_id=fid, zone_id=zid, observed_at=utcnow(), airflow=flow, co2=610, pm25=12,
                              fan_running=True, damper_pct=95, adapter=facility["adapter"])
            return core.publish(obs)["body"]["m2m:cin"]["ri"]

        def view():
            maintenance.refresh_work_orders(core)
            orders = core.state(actor)["work_orders"]
            assert len(orders) == 1
            return orders[0]

        def desk_order():
            response = technician.get("/api/work-orders")
            assert response.is_success, response.text
            items = response.json()["work_orders"]
            assert len(items) == 1
            return items[0]

        def command_count():
            return core.cse.retrieve(zone["path"] + "/commands", origin=core.identities["operator"])["body"]["m2m:cnt"]["cni"]

        maint = worker("maintenance")
        bridge = worker("bridge")
        publish(360)
        maintenance.flush_outbox(core)
        maint.scan()
        initial = view()
        cmd = core.request_action(ActionRequest(facility_id=fid, zone_id=zid, action="set_damper", value=95,
                                  reason="Virtual field inspection trial", request_id=run_id + "-damper"), actor, run_id)
        core.acknowledge_pending(facility, only_command_id=cmd["id"])
        publish(360)
        publish(360)
        maintenance.flush_outbox(core)
        maint.scan()
        pending = desk_order()
        assert pending["evidence_status"] == "awaiting_independent_sample"
        entry_form = {"request_id": str(uuid4()), "action": "checked", "work_order_ri": pending["resource_id"],
                      "note": "Inspected the linkage. Awaiting operating measurements."}
        endpoint = "/api/work-orders/" + initial["work_order_id"] + "/inspections"
        headers = {"Origin": site_origin}
        entry = technician.post(endpoint, headers=headers, json=entry_form).raise_for_status().json()
        assert view()["latest_technician_activity"]["resource_id"] == entry["resource_id"]
        assert core.store.get("incidents", fid + ":" + zid)["status"] == "open"
        count = command_count()
        # Hold the worker offline while the operator acquires the qualifying measurements.
        maint.close()
        first = publish(940)
        maintenance.flush_outbox(core)
        assert core.store.get("incidents", fid + ":" + zid)["status"] == "recovering"
        assert view()["resource_id"] == pending["resource_id"]
        second = publish(945)
        maintenance.flush_outbox(core)
        assert core.store.get("incidents", fid + ":" + zid)["status"] == "resolved"
        assert desk_order()["resource_id"] == pending["resource_id"]
        # A valid shaft reply is retained too. It must not re-prioritize a recovered command.
        time.sleep(conf["bridge"]["settle_seconds"] + .05)
        sample = {"facility_id": fid, "zone_id": zid, **conf["bridge"]["assets"][zid], "unit": "%", "value": 35,
                  "observed_at": utcnow(), "source": "independent_position_sensor", "simulated": True}
        core.create_content(facility["path"] + "/independent_samples", sample, core.identities["sensor:" + fid])
        bridge.scan()
        maint = worker("maintenance")
        maint.scan()
        resolved = view()
        recovered = desk_order()
        assert recovered["work_order_id"] == initial["work_order_id"]
        assert recovered["resource_id"] == resolved["resource_id"] and recovered["status"] == "open"
        assert recovered["evidence_status"] == "operational_recovery_verified"
        assert recovered["inspections"][0]["resource_id"] == entry["resource_id"]
        assert recovered["inspections"][0]["work_order_ri"] == pending["resource_id"]
        assert "latest_technician_activity" not in resolved
        recovery = recovered["recovery"]
        assert [o["cin_ri"] for o in recovery["observations"]] == [first, second]
        assert recovery["ack"]["cin_ri"] == core.store.get("commands", cmd["id"])["ack_source"]["cin_ri"]
        revisions = [read_content(maint.cin(p)) for p in maint.children("work_orders")]
        assert sorted(r["revision"] for r in revisions) == [1, 2, 5]
        late = [maint.cin(p) for p in maint.children("sensor_responses")]
        assert len(late) == 1 and read_content(late[0])["status"] == "measured"
        maint.close()
        replayed = worker("maintenance")
        replayed.scan()
        assert len(list(replayed.children("work_orders"))) == len(revisions)
        assert view()["resource_id"] == recovered["resource_id"]
        assert desk_order()["resource_id"] == recovered["resource_id"] and command_count() == count == 1
        stale = technician.post(endpoint, headers=headers, json={**entry_form, "request_id": str(uuid4())})
        assert stale.status_code == 409
        acknowledged = technician.post(endpoint, headers=headers, json=entry_form).raise_for_status().json()
        assert acknowledged["resource_id"] == entry["resource_id"]
        assert before == source_hashes(), "Source changed during the field recovery trial"
        return {"status": "passed", "acme_version": version, "run_id": run_id, "facility_id": fid,
                "scope": "Virtual measurements, real loopback CSE and facility-scoped AEs. Field app normal HTTP routes were exercised by an in-process ASGI client. Independent sensor was local.",
                "work_order_id": initial["work_order_id"], "initial_order_ri": initial["resource_id"],
                "reviewed_order_ri": pending["resource_id"], "checked_field_entry_ri": entry["resource_id"],
                "after_checked": "open", "after_one_nominal": "recovering", "after_two_nominal": "resolved",
                "field_work_order_status": recovered["status"], "final_order_ri": recovered["resource_id"],
                "final_order_rqi": recovered["read_rqi"], "recovery_outcome_ri": recovered["outcome_ri"],
                "recovery": recovery, "late_shaft_reply_ri": late[0]["ri"], "work_order_revisions": [1, 2, 5],
                "same_order_after_restart": True, "stale_field_revision_http": stale.status_code,
                "device_command_count_before_and_after": [count, command_count()],
                "source_sha256": before}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "run_id", "work_order_id", "final_order_ri")}))
