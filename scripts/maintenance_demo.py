#!/usr/bin/env python3
"""Run one isolated, replayable facility incident through the actual ACME and maintenance apps."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import uuid

import httpx

from opensoom.onem2m import CSEClient, CSEError
from opensoom.store import Store
from opensoom.ventilation_trials import SCENARIOS as AIR_QUALITY_SCENARIOS

ROOT = Path(__file__).resolve().parents[1]


def available_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def until(description, read, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = read()
            if result:
                return result
        except (httpx.RequestError, CSEError):
            pass
        time.sleep(.25)
    raise TimeoutError(description)


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(5)


def run_lab(args):
    runtime_root = ROOT / ".runtime"
    runtime_root.mkdir(exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="maintenance-lab-", dir=runtime_root))
    ports = {name: available_port() for name in ("central", "mn", "api", "gateway", "maintenance", "bridge", "technician")}
    if args.dashboard_port:
        ports["api"] = args.dashboard_port
    if args.technician_port:
        ports["technician"] = args.technician_port
    if len(set(ports.values())) != len(ports):
        raise RuntimeError("Port collision. Rerun to allocate new ports.")
    url = {name: f"http://127.0.0.1:{port}" for name, port in ports.items()}
    worker_url = url["gateway"].replace("http:", "https:")
    # Workers receive only the credential for their own role.
    base_env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TMPDIR", "SYSTEMROOT")}
    env = {**base_env, "OPENSOOM_CSE_RUNTIME_DIR": str(folder), "OPENSOOM_RUNTIME_DIR": str(folder / "operations"),
           "OPENSOOM_CSE_URL": url["mn"], "OPENSOOM_CSE_BASE": "cse-food",
           "OPENSOOM_NOTIFY_URL": url["api"] + "/api/notify",
           "OPENSOOM_TECHNICIAN_URL": url["technician"], "OPENSOOM_TECHNICIAN_FACILITY": "food-a"}
    if args.hold and not args.mec_config:
        env["OPENSOOM_LOCAL_SHAFT_REPLAY_FACILITY"] = "food-a"
    runtime_script = [sys.executable, str(ROOT / "scripts/cse_runtime.py")]
    with ExitStack() as stack:
        def spawn(name, command, run_env):
            log = stack.enter_context((folder / (name + ".log")).open("a"))
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                       cwd=ROOT, env=run_env)
            stack.callback(stop, process)
            return process

        for role, options in (("central", ["--port", str(ports["central"])]),
                              ("food", ["--port", str(ports["mn"]), "--registrar-port", str(ports["central"])])):
            stack.callback(subprocess.run, [*runtime_script, "stop", "--name", role], env=env,
                           stdout=subprocess.DEVNULL, check=False)
            subprocess.run([*runtime_script, "start", "--name", role, *options], env=env, check=True,
                           stdout=subprocess.DEVNULL)
        api = stack.enter_context(httpx.Client(base_url=url["api"], trust_env=False, timeout=20))
        uvicorn = [sys.executable, "-m", "uvicorn", "--host", "127.0.0.1", "--no-access-log"]
        spawn("operations", [*uvicorn, "--port", str(ports["api"]), "opensoom.app:app"], env)
        until("Facility CSE bootstrap", lambda: api.get("/api/health").json()["cse_connected"])
        service_credentials = json.loads((folder / "operations/service-credentials.json").read_text())
        api.headers["Authorization"] = "Bearer " + service_credentials["operator_token"]
        state = lambda: api.get("/api/state").raise_for_status().json()
        db = Store(folder / "operations/operations.sqlite")
        ids = db.get("config", "identities")
        fid, site = "food-a", "cse-food/opensoom/facilities/food-a"
        mcfg = next(f["maintenance"] for f in json.loads((ROOT/"config/facilities.json").read_text())["facilities"] if f["id"] == fid)
        zone = next(iter(mcfg["assets"]))
        tokens = {ids[role + ":" + fid]: secrets.token_urlsafe(36) for role in ("maintenance","bridge","sensor","technician")}
        credentials = folder / "workers.json"
        credentials.write_text(json.dumps(tokens))
        credentials.chmod(0o600)
        # Use the same project-local TLS generation as the ordinary ACME secure profile.
        import cse_runtime
        cse_runtime.RUNTIME = folder
        pki = cse_runtime.prepare_certificates()
        spawn("gateway", [*uvicorn, "--port", str(ports["gateway"]), "--ssl-certfile", str(pki/"server.crt"),
             "--ssl-keyfile", str(pki/"server.key"), "--factory", "opensoom.worker_access:create_app"],
             {**env, "OPENSOOM_WORKER_CREDENTIALS_FILE": str(credentials)})

        def worker_client(role, credential_role=None):
            origin = ids[role + ":" + fid]
            return stack.enter_context(CSEClient(worker_url, origin, ca_file=pki/"ca.crt",
                          bearer_token=tokens[ids[(credential_role or role) + ":" + fid]]))
        maintenance = worker_client("maintenance")
        bridge = worker_client("bridge")
        sensor = worker_client("sensor")
        technician = worker_client("technician")
        upstream = stack.enter_context(CSEClient(url["mn"]))
        until("Authenticated worker gateway", lambda: maintenance.retrieve(site + "/outcomes"))

        facility = db.get("facilities", fid)
        field_config = folder / "technician.json"
        field_config.write_text(json.dumps({
            "facility_id": fid, "facility_path": site, "name": facility["name"], "profile": facility["profile"],
            "simulation": facility["simulated"], "origin": technician.origin, "cse_url": worker_url,
            "cse_ca": str(pki/"ca.crt"), "zones": {z["id"]: {"name": z["name"], "target_m3_h": z["minimum_airflow"]}
                                                   for z in facility["zones"]},
        }))
        def start_technician():
            return spawn("technician", [*uvicorn, "--port", str(ports["technician"]), "--factory", "opensoom.technician:create_app"],
                         {**base_env, "OPENSOOM_TECHNICIAN_CONFIG": str(field_config),
                          "OPENSOOM_TECHNICIAN_CSE_TOKEN": tokens[technician.origin]})
        desk_process = start_technician()
        desk = stack.enter_context(httpx.Client(base_url=url["technician"], trust_env=False, timeout=10))
        until("Technician workbench", lambda: desk.get("/").is_success)

        def start_worker(role):
            config = {**mcfg, "origin": ids[role + ":" + fid], "cse_url": worker_url, "cse_ca": str(pki/"ca.crt"),
                      "facility_id": fid, "facility_path": site, "listen_port": ports[role], "poll_seconds": 1,
                      "bridge_mode": "local", "trace_path": str(folder / (role + ".jsonl"))}
            role_env = {**base_env, "OPENSOOM_WORKER_CSE_TOKEN": tokens[config["origin"]]}
            if role == "bridge" and args.mec_config:
                config.update(json.loads(args.mec_config.read_text()))
                config["bridge_mode"] = "mec046"
                if os.getenv("OPENSOOM_MEC_TOKEN"):
                    role_env["OPENSOOM_MEC_TOKEN"] = os.environ["OPENSOOM_MEC_TOKEN"]
            file = folder / (role + ".json")
            file.write_text(json.dumps(config))
            proc = spawn(role, [sys.executable, "-m", "opensoom.maintenance_worker", role, "--config", str(file)], role_env)
            until(role + " callback", lambda: httpx.get(url[role] + "/health", trust_env=False).json())
            return proc

        maint_process = start_worker("maintenance")
        start_worker("bridge")
        for stream, role in (("outcomes", "maintenance"), ("sensor_responses", "maintenance"), ("sensor_requests","bridge")):
            upstream.create(site+"/"+stream, 23, {"m2m:sub":{"rn":"notify-"+role,"nu":[url[role]+"/notify"],
                            "enc":{"net":[3],"chty":[4]},"nct":1}})
        stop(maint_process)
        started = api.post("/api/demo/start", json={"facility_id":fid, "scenario":"no_recovery","autorun":True})
        run_id = started.raise_for_status().json()["run_id"]
        def active_command():
            return next((c for c in state()["commands"] if c.get("run_id")==run_id and c.get("observed_result")=="unresolved"), None)
        command = until("Local operation reaches unresolved without maintenance", active_command)
        assert not [o for o in state()["work_orders"] if o["run_id"]==run_id]
        maint_process = start_worker("maintenance")
        def order_at(revision):
            return next((o for o in state()["work_orders"] if o.get("run_id")==run_id and o.get("revision",0)>=revision), None)
        provider = "mec046" if args.mec_config else "local"
        pending = until("CSE catch-up after worker restart", lambda: order_at(3 if provider == "local" else 2))
        def seed_local(value):
            return sensor.create(site + "/independent_samples", 4, {"m2m:cin": {
                "cnf": "application/json:0", "con": json.dumps(value)}})

        def receipts(parent, origin):
            path = site + "/" + parent
            found = origin.discover(path, {"ty": 4, "drt": 1, "lvl": 1})
            return [origin.retrieve(path + "/" + uri.rsplit("/", 1)[-1])["body"]["m2m:cin"]
                    for uri in found["body"]["m2m:uril"]]

        sample = {**mcfg["assets"][zone], "facility_id":fid,"zone_id":zone,"value":35,"unit":"%",
                  "source":"independent_position_sensor","simulated":True,"observed_at":datetime.now(timezone.utc).isoformat()}
        seed = None
        rejected_samples = []
        if provider == "local":
            wrong_asset = seed_local({**sample, "asset_id": "unmapped-virtual-asset"})
            def bridge_scans():
                return httpx.get(url["bridge"] + "/health", trust_env=False).json()["scans"]
            initial_scans = bridge_scans()
            until("Bridge reconciled with an unrelated asset", lambda: bridge_scans() >= initial_scans + 2)
            assert order_at(4) is None
            rejected_samples.append({"sample_ri": wrong_asset["body"]["m2m:cin"]["ri"],
                                     "reason": "unrelated_asset_ignored", "scans": bridge_scans() - initial_scans})
            for invalid, reason in (({"unit": "rpm"}, "unexpected_measurement_unit"),
                                    ({"observed_at": None}, "invalid_measurement_time"),
                                    ({"observed_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()}, "before_actuator_settled")):
                invalid_sample = seed_local({**sample, **invalid})
                def rejection():
                    for cin in receipts("sensor_responses", maintenance):
                        body = json.loads(cin["con"])
                        if body.get("reason") == reason and body.get("request_id") == pending["request_id"]:
                            return cin["ri"]
                    return None
                response_ri = until("Reject " + reason, rejection)
                assert order_at(4) is None
                rejected_samples.append({"sample_ri": invalid_sample["body"]["m2m:cin"]["ri"],
                                         "reason": reason, "response_ri": response_ri})
            sample["observed_at"] = datetime.now(timezone.utc).isoformat()
            seed = seed_local(sample)
        else:
            print(f"Ready for independent MEC sample on {sample['sensor_id']} (run {run_id})", flush=True)
        final = until("Independent sensor changes inspection priority", lambda: order_at(4), args.sample_timeout)
        assert final["work_order_id"]==pending["work_order_id"] and final["priority"]=="inspect_actuator_feedback"
        result_state = state()
        incident = next(i for i in result_state["incidents"] if i["id"]==command["incident_id"])
        assert incident["status"]=="open"
        orders = [o for o in result_state["work_orders"] if o["incident_id"]==incident["id"]]
        assert len(orders)==1
        observations = maintenance.retrieve(site + "/" + zone + "/observations", params={"fu": 1, "ty": 4, "drt": 1})
        source = None
        for uri in observations["body"]["m2m:uril"]:
            cin = maintenance.retrieve(site + "/" + zone + "/observations/" + uri.rsplit("/", 1)[-1])["body"]["m2m:cin"]
            if cin["ri"] == final["source_cin_ri"]:
                source = json.loads(cin["con"])
                break
        assert source is not None
        target_zone = next(z for f in result_state["facilities"] if f["id"] == fid for z in f["zones"] if z["id"] == zone)
        assert source["airflow"] < target_zone["target_airflow"]
        before_replay = {cin["ri"] for cin in receipts("work_orders", maintenance)}
        stop(maint_process)
        start_worker("maintenance")
        for _ in range(2):
            httpx.post(url["maintenance"] + "/notify", json={"m2m:sgn": {"sur": "demo-replay"}},
                       trust_env=False).raise_for_status()
        until("Worker enumerated retained resources after restart",
              lambda: httpx.get(url["maintenance"] + "/health", trust_env=False).json()["scans"] >= 2)
        after_replay = {cin["ri"] for cin in receipts("work_orders", maintenance)}
        assert before_replay == after_replay
        def denied(call):
            try:
                call()
            except CSEError as exc:
                if exc.rsc!=4103:
                    raise
                return {"rsc":exc.rsc,"rqi":exc.result["rqi"]}
            raise AssertionError("Unauthorized access succeeded")
        test_write = {"m2m:cin":{"con":"scope check"}}
        denials = {
            "maintenance_command":denied(lambda: maintenance.create(site+"/"+zone+"/commands",4,test_write)),
            "bridge_command":denied(lambda: bridge.create(site+"/"+zone+"/commands",4,test_write)),
            "maintenance_response":denied(lambda: maintenance.create(site+"/sensor_responses",4,test_write)),
            "bridge_work_order":denied(lambda: bridge.create(site+"/work_orders",4,test_write)),
            "bridge_request":denied(lambda: bridge.create(site+"/sensor_requests",4,test_write)),
            "other_facility":denied(lambda: maintenance.retrieve("cse-food/opensoom/facilities/learning-b/lounge/observations")),
            "credential_origin_mismatch":denied(lambda: worker_client("bridge","maintenance").retrieve(site+"/sensor_requests")),
            "technician_command":denied(lambda: technician.create(site+"/"+zone+"/commands",4,test_write)),
            "technician_work_order":denied(lambda: technician.create(site+"/work_orders",4,test_write)),
            "technician_sensor_response":denied(lambda: technician.create(site+"/sensor_responses",4,test_write)),
            "technician_other_facility":denied(lambda: technician.retrieve("cse-food/opensoom/facilities/learning-b/lounge/observations")),
            "maintenance_inspection":denied(lambda: maintenance.create(site+"/inspections",4,test_write)),
        }
        desk_api = "/api/work-orders"
        field_order = next(o for o in desk.get(desk_api).raise_for_status().json()["work_orders"] if o["run_id"] == run_id)
        assert field_order["resource_id"] == final["resource_id"] and field_order["configured_target_m3_h"] == target_zone["target_airflow"]
        assert field_order["target_source"] == "work_order_cin"
        inspection_path = desk_api + "/" + final["work_order_id"] + "/inspections"
        data = {"work_order_ri": final["resource_id"], "action": "scheduled", "request_id": str(uuid.uuid4()),
                "note": "Demonstration: booked the actuator travel and position feedback check."}
        headers = {"Origin": url["technician"]}
        unauthorized = httpx.get(url["technician"] + desk_api, trust_env=False).status_code
        wrong_origin = desk.post(inspection_path, headers={"Origin": url["api"]}, json=data).status_code
        stale_revision = desk.post(inspection_path, headers=headers, json={**data, "work_order_ri": pending["resource_id"]}).status_code
        assert (unauthorized, wrong_origin, stale_revision) == (401, 403, 409)
        entry = desk.post(inspection_path, headers=headers, json=data).raise_for_status().json()
        retry = desk.post(inspection_path, headers=headers, json=data).raise_for_status().json()
        assert retry["resource_id"] == entry["resource_id"]
        conflicting = desk.post(inspection_path, headers=headers, json={**data, "note": "A different entry."}).status_code
        assert conflicting == 409
        denials["operator_private_field_note"] = denied(lambda: upstream.retrieve(site+"/inspection_notes/la", origin=ids["operator"]))
        denials["maintenance_private_field_note"] = denied(lambda: maintenance.retrieve(site+"/inspection_notes/la"))
        stop(desk_process)
        start_technician()
        until("Restarted technician workbench", lambda: desk.get("/").is_success)
        after_restart = next(o for o in desk.get(desk_api).raise_for_status().json()["work_orders"] if o["run_id"] == run_id)
        assert after_restart["resource_id"] == final["resource_id"] and after_restart["status"] == "open"
        assert [n["resource_id"] for n in after_restart["inspections"]] == [entry["resource_id"]]
        assert after_restart["inspections"][0]["note"] == data["note"]
        def operator_activity():
            return next((o["latest_technician_activity"] for o in state()["work_orders"] if o["run_id"] == run_id
                         and o.get("latest_technician_activity", {}).get("resource_id") == entry["resource_id"]), None)
        disposition = until("Operator reads the current revision's inspection disposition", operator_activity)
        assert set(disposition) == {"action", "recorded_at", "resource_id", "work_order_ri"}
        def read_role_state(role):
            auth = {"Authorization": "Bearer " + service_credentials[role + "_token"]}
            return api.get("/api/state", headers=auth).raise_for_status().json()

        observer_view = read_role_state("observer")
        assert fid in {facility["id"] for facility in observer_view["facilities"]}
        assert observer_view["work_orders"] == []
        maintenance_view = read_role_state("maintenance")
        maintenance_order = next(order for order in maintenance_view["work_orders"] if order["run_id"] == run_id)
        assert maintenance_order["resource_id"] == final["resource_id"]
        assert "latest_technician_activity" not in maintenance_order
        after_note = state()
        assert {c["id"] for c in after_note["commands"]} == {c["id"] for c in result_state["commands"]}
        assert next(i for i in after_note["incidents"] if i["id"]==incident["id"])["status"] == "open"
        trace = {r:httpx.get(url[r]+"/health",trust_env=False).json() for r in ("maintenance","bridge")}
        topology = upstream.retrieve("cse-food")["body"]["m2m:cb"]
        central = stack.enter_context(CSEClient(url["central"]))
        csr = until("MN registered at central IN-CSE",lambda: central.discover("cse-central",{"ty":16})["body"].get("m2m:uril"))
        result = {"status":"passed","sensor_path":provider,"virtual_equipment":True,"facility_id":fid,
                  "run_id":run_id,"site_cse_id":topology["csi"],"site_node_type":topology["cst"],"central_remote_cses":csr,
                  "configured_apps":{f["id"]:f["maintenance_enabled"] for f in result_state["facilities"]},
                  "command":command,"incident":incident,"before_independent_sample":pending,"after":final,
                  "logical_order_count":len(orders),"worker_health":trace,"denials":denials,
                  "airflow":{"observed":source["airflow"],"target":target_zone["target_airflow"],"unit":"m³/h",
                             "observation_ri":final["source_cin_ri"]},
                  "invalid_local_samples":rejected_samples,
                  "replay":{"duplicate_callback_hints":2,"restarted_after_write":True,
                            "revision_cins_before":sorted(before_replay),"revision_cins_after":sorted(after_replay)},
                  "local_sample_cin":seed["body"]["m2m:cin"]["ri"] if seed else None,
                  "technician":{"separate_web_process":True,"facility_id":fid,"work_order_ri":final["resource_id"],
                                "inspection_cin":entry["resource_id"],"action":entry["action"], "read_rqi":entry["read_rqi"],
                                "profile_target_m3_h":field_order["configured_target_m3_h"],
                                "target_source":field_order["target_source"],"operator_disposition":disposition,
                                "unauthenticated_http":unauthorized,"foreign_origin_http":wrong_origin,
                                "stale_work_order_http":stale_revision,"conflicting_retry_http":conflicting,"retry_same_cin":True,
                                "observer_order_count":len(observer_view["work_orders"]),
                                "maintenance_saw_order":True,"maintenance_saw_technician_activity":False,
                                "restarted_entries":1,"new_device_commands":0,"incident_after_entry":"open"},
                  "dashboard":"live service projection from oneM2M work_order CINs"}
        if args.opening_scenario:
            opening = api.post("/api/demo/start", json={"facility_id": fid, "scenario": args.opening_scenario,
                                                        "autorun": True}).raise_for_status().json()
            def opening_command():
                return next((cmd for cmd in state()["commands"] if cmd["run_id"] == opening["run_id"]
                             and (cmd.get("air_quality_outcome") or {}).get("latest")), None)
            active = until("First post-ACK air-quality observation", opening_command)
            result["opening_trial"] = {"scenario": args.opening_scenario, "run_id": opening["run_id"],
                                       "command_id": active["id"], "first_outcome": active["air_quality_outcome"]}
            print(json.dumps({"opening_scenario": args.opening_scenario, "opening_run_id": opening["run_id"],
                              "command_id": active["id"]}), flush=True)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps({"result":"passed","run_id":run_id,"work_order":final["work_order_id"],
                          "dashboard":url["api"],"technician":url["technician"],"runtime":str(folder)}),flush=True)
        if args.hold:
            print("Dashboard is live. Select Run scenario to replay a trial. Press Ctrl+C to close the lab.", flush=True)
            seeded = {command["id"]}
            while True:
                if provider == "local":
                    snapshot = state()
                    current_site = next(f for f in snapshot["facilities"] if f["id"] == fid)
                    position = 98 if current_site["scenario"] == "no_recovery_matching_shaft" else 35
                    for action in snapshot["commands"]:
                        if (action.get("run_id") == current_site["active_run"]
                                and current_site["scenario"] in ("no_recovery", "no_recovery_matching_shaft")
                                and action["facility_id"] == fid and action["zone_id"] == zone and action["id"] not in seeded
                                and action.get("observed_result") == "unresolved" and action.get("ack_at")
                                and (datetime.now(timezone.utc) - datetime.fromisoformat(action["ack_at"])).total_seconds() >= 10):
                            seed_local({**sample, "value": position, "observed_at": datetime.now(timezone.utc).isoformat()})
                            seeded.add(action["id"])
                time.sleep(1)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--dashboard-port",type=int)
    parser.add_argument("--technician-port",type=int,help="Local port for the separate technician workbench")
    parser.add_argument("--mec-config",type=Path,help="Use an already provisioned MEC registry and authorized service origins")
    parser.add_argument("--sample-timeout",type=int,default=90)
    parser.add_argument("--hold",action="store_true")
    parser.add_argument("--opening-scenario", choices=AIR_QUALITY_SCENARIOS,
                        help="Open the live dashboard on this air-quality trial after the maintenance checks (--hold)")
    args = parser.parse_args()
    if args.opening_scenario and not args.hold:
        parser.error("--opening-scenario opens the live dashboard and requires --hold")
    try:
        run_lab(args)
    except KeyboardInterrupt:
        pass
