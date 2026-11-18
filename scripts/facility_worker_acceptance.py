#!/usr/bin/env python3
"""Commission a third virtual facility, then reuse the shipped worker CLI roles.

Account-free and isolated: actual ACME CSE, original operational code and worker
processes, independently injected virtual sensor CINs. No MEC or model call.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

from cse_multiapp_smoke import ROOT, child_env, start_cse, stop_process
from facility_pack_acceptance import PACK
from opensoom import maintenance
from opensoom.core import Core, OperationError
from opensoom.facility_pack import worker_templates
from opensoom.models import ActionRequest, Observation, utcnow
from opensoom.onem2m import CSEClient, CSEError


SOURCES = ("src/opensoom/core.py", "src/opensoom/maintenance.py", "src/opensoom/maintenance_worker.py",
           "src/opensoom/mec_sensor.py", "src/opensoom/facility_pack.py", "src/opensoom/adapters.py",
           "src/opensoom/policy.py", "src/opensoom/onem2m.py", "scripts/facility_worker_acceptance.py",
           "scripts/facility_pack_acceptance.py", "profiles/food-production.json", "profiles/learning-space.json")


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def notify_sink():
    class Notify(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(200)
            self.send_header("X-M2M-RSC", "2000")
            self.send_header("X-M2M-RI", self.headers.get("X-M2M-RI", ""))
            self.send_header("X-M2M-RVI", "4")
            self.end_headers()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Notify)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run():
    before = hashes()
    with ExitStack() as stack:
        root = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="opensoom-facility-workers-")))
        processes = []
        stack.callback(lambda: [stop_process(process) for process in processes])
        url, cse_process, version = start_cse(root, processes)
        sink = notify_sink()
        stack.callback(sink.server_close)
        stack.callback(sink.shutdown)
        # Only this reproduction process receives the temporary configuration.
        prior = {k: v for k, v in os.environ.items() if k.startswith("OPENSOOM_")}
        def restore_environment():
            for name in list(os.environ):
                if name.startswith("OPENSOOM_"):
                    del os.environ[name]
            os.environ.update(prior)
        stack.callback(restore_environment)
        for name in prior:
            del os.environ[name]
        os.environ.update(OPENSOOM_CSE_BASE="cse-multiapp",
                          OPENSOOM_NOTIFY_URL=f"http://127.0.0.1:{sink.server_port}/notify")
        trace = root / "requests.jsonl"
        def core_client():
            return stack.enter_context(CSEClient(url, trace_path=trace))
        core = Core(runtime=root / "operations", cse=core_client())
        core.bootstrap()
        operator = {"role": "operator", "facilities": core.actor_facilities("operator")}
        draft = core.tool("draft_facility", PACK, operator)
        try:
            core.tool("activate_facility", {"version": draft["version"]}, operator)
        except OperationError as error:
            assert error.code == "admin_required"
            operator_denied = error.code
        else:
            raise AssertionError("Operator activated a facility")
        active = core.tool("activate_facility", {"version": draft["version"]}, {"role": "admin", "facilities": []})
        assert len(core.registry) == 3 and active["zone_ids"][1] == "conservation"
        core.cse.close()
        core = Core(runtime=root / "operations", cse=core_client())
        core.bootstrap()
        assert worker_templates(core, PACK["site_id"]) == active["worker_templates"]
        launched, configs, clients = [], {}, {}
        for fid in ("food-a", PACK["site_id"]):
            configs[fid] = worker_templates(core, fid)
            for role in ("maintenance", "bridge", "sensor"):
                clients[fid, role] = stack.enter_context(CSEClient(url, core.identities[role + ":" + fid], trace_path=trace))
            for role, config in configs[fid].items():
                path = root / (fid + "-" + role + ".json")
                path.write_text(json.dumps({**config, "cse_url": url, "bridge_mode": "local", "trace_path": str(trace)}))

        def scan(fid, role):
            config = root / (fid + "-" + role + ".json")
            log = root / (fid + "-" + role + ".log")
            with log.open("ab") as output:
                process = subprocess.Popen([sys.executable, "-m", "opensoom.maintenance_worker", role,
                                            "--config", str(config), "--once"], cwd=ROOT, env=child_env(),
                                           stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                try:
                    code = process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    stop_process(process)
                    raise
            if code:
                raise RuntimeError(f"The {role} worker failed for {fid}; no result is accepted")
            launched.append({"facility_id": fid, "role": role, "pid": process.pid, "exit_code": code,
                             "entrypoint": "python -m opensoom.maintenance_worker ROLE --config FILE --once"})

        def parent(fid, stream):
            return core.facility(fid)["path"] + "/" + stream

        def records(fid, stream, role="maintenance"):
            client = clients[fid, role]
            found = client.discover(parent(fid, stream), {"ty": 4, "drt": 1, "lvl": 1})
            rows = []
            for uri in found["body"].get("m2m:uril", []):
                reply = client.retrieve(parent(fid, stream) + "/" + uri.rsplit("/", 1)[-1])
                cin = reply["body"]["m2m:cin"]
                rows.append({"ri": cin["ri"], "rqi": reply["rqi"], "content": json.loads(cin["con"])})
            return rows

        def state_tags(fid, zone):
            streams = ("outcomes", "work_orders", "sensor_requests", "sensor_responses", "independent_samples",
                       zone + "/observations", zone + "/commands", zone + "/acks")
            result = {}
            for stream in streams:
                role = "sensor" if stream == "independent_samples" else "bridge" if stream == "sensor_requests" else "maintenance"
                # Device command counts are inspected by the ordinary operator.
                client = core.cse if stream.endswith("/commands") else clients[fid, role]
                kwargs = {"origin": core.identities["operator"]} if stream.endswith("/commands") else {}
                reply = client.retrieve(parent(fid, stream), **kwargs)
                cnt = reply["body"]["m2m:cnt"]
                result[stream] = {"ri": cnt["ri"], "st": cnt["st"], "cni": cnt["cni"]}
            return result

        denials = []
        for fid, other in (("food-a", PACK["site_id"]), (PACK["site_id"], "food-a")):
            zone = "cook" if fid == "food-a" else "conservation"
            probes = [
                ("maintenance", "GET", parent(other, "outcomes")),
                ("bridge", "GET", parent(other, "independent_samples")),
                ("maintenance", "POST", parent(fid, zone + "/commands")),
                ("bridge", "POST", parent(fid, "work_orders")),
            ]
            for role, method, path in probes:
                try:
                    if method == "GET":
                        clients[fid, role].retrieve(path)
                    else:
                        clients[fid, role].create(path, 4, {"m2m:cin": {"rn": "forbidden-probe", "con": "{}"}})
                except CSEError as error:
                    assert error.rsc == 4103
                    denials.append({"facility_id": fid, "role": role, "origin": clients[fid, role].origin,
                                    "method": method, "path": path, "receipt": error.result})
                else:
                    raise AssertionError("CSE permitted a cross-facility or wrong-role operation")

        def exercise(fid, zone):
            actor = {"role": "operator", "facilities": [fid]}
            run_id = core.start_demo(fid, "normal", False, actor)["run_id"]
            facility = core.facility(fid)
            profile_zone = core.zone(facility, zone)
            cfg = configs[fid]["maintenance"]
            binding = cfg["assets"][zone]
            target = profile_zone["minimum_airflow"]
            other_zone = facility["zones"][0]["id"] if zone != facility["zones"][0]["id"] else facility["zones"][1]["id"]
            def neighboring_counts():
                return {stream: core.cse.retrieve(parent(fid, other_zone + "/" + stream), origin=core.identities["operator"])["body"]["m2m:cnt"]["st"]
                        for stream in ("observations", "commands", "acks")}
            neighbor_before = neighboring_counts()
            def observe(flow, dust=12):
                obs = Observation(facility_id=fid, zone_id=zone, observed_at=utcnow(), adapter=facility["adapter"],
                                  airflow=flow, pm25=dust, co2=610, fan_running=True, damper_pct=80)
                receipt = core.publish(obs)
                maintenance.flush_outbox(core)
                return {"cin_ri": receipt["body"]["m2m:cin"]["ri"], "write_rqi": receipt["rqi"],
                        "observation": obs.model_dump()}
            def command(value, suffix):
                item = core.request_action(ActionRequest(facility_id=fid, zone_id=zone, action="set_damper", value=value,
                            reason="Scripted virtual commissioning", request_id=run_id + suffix), actor, run_id)
                core.acknowledge_pending(facility, only_command_id=item["id"])
                return core.store.get("commands", item["id"])
            def order():
                maintenance.refresh_work_orders(core)
                rows = [o for o in core.state(actor)["work_orders"] if o["run_id"] == run_id]
                assert len(rows) == 1
                return rows[0]
            def independent(value, cmd):
                elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(cmd["ack_at"])).total_seconds()
                time.sleep(max(0, cfg["settle_seconds"] - elapsed + .02))
                payload = {"facility_id": fid, "zone_id": zone, **binding, "observed_at": utcnow(),
                           "value": value, "unit": "%", "source": "independent_position_sensor", "simulated": True}
                receipt = clients[fid, "sensor"].create(parent(fid, "independent_samples"), 4,
                                    {"m2m:cin": {"con": json.dumps(payload), "cnf": "application/json:0"}})
                return {"cin_ri": receipt["body"]["m2m:cin"]["ri"], "write_rqi": receipt["rqi"], "sample": payload}

            opening = observe(target + 40, dust=profile_zone["pm25_warning"] + 50)
            scan(fid, "maintenance")
            original = order()
            first = command(80, "-first")
            adequate_flow = [observe(target + 40, dust=profile_zone["pm25_warning"] + 50) for _ in range(2)]
            scan(fid, "maintenance")
            scan(fid, "bridge")
            assert core.store.get("commands", first["id"])["observed_result"] == "unresolved"
            assert not records(fid, "sensor_requests")
            assert order()["work_order_id"] == original["work_order_id"] and order()["revision"] == 1
            delayed_low = observe(target - 45)
            scan(fid, "maintenance")
            requests = records(fid, "sensor_requests")
            assert len(requests) == 1 and requests[0]["content"]["source_cin_ri"] == delayed_low["cin_ri"]
            mismatch_sample = independent(35, first)
            scan(fid, "bridge")
            scan(fid, "maintenance")
            mismatch = order()
            assert mismatch["priority"] == "inspect_actuator_feedback" and mismatch["sample"]["value"] == 35
            assert mismatch["provider_receipt"]["sample_cin_ri"] == mismatch_sample["cin_ri"]
            second = command(95, "-second")
            later_low = [observe(target - 45) for _ in range(2)]
            scan(fid, "maintenance")
            matched_sample = independent(93, second)
            scan(fid, "bridge")
            scan(fid, "maintenance")
            matched = order()
            assert matched["priority"] == "inspect_airflow_path" and matched["sample"]["value"] == 93
            assert matched["provider_receipt"]["sample_cin_ri"] == matched_sample["cin_ri"]
            assert matched["work_order_id"] == mismatch["work_order_id"] == original["work_order_id"]
            assert core.store.get("incidents", fid + ":" + zone)["status"] == "open"
            historical = records(fid, "work_orders")
            assert len({row["content"]["work_order_id"] for row in historical}) == 1
            assert next(row for row in historical if row["ri"] == mismatch["resource_id"])["content"]["sample"]["value"] == 35
            assert neighboring_counts() == neighbor_before
            return {"facility_id": fid, "zone_id": zone, "zone_index": [z["id"] for z in facility["zones"]].index(zone),
                    "profile_id": facility["profile"], "target_airflow_m3_h": target, "binding": binding,
                    "run_id": run_id, "opening_observation": opening, "original_order": original,
                    "first_command": first, "adequate_flow_but_other_fault": adequate_flow,
                    "sensor_requests_before_late_low_flow": 0, "late_low_flow": delayed_low,
                    "first_sensor_request": requests[0], "first_independent_sample": mismatch_sample,
                    "mismatch_order": mismatch, "next_command": second, "next_low_flow": later_low,
                    "next_independent_sample": matched_sample, "matched_order": matched,
                    "current_command": core.store.get("commands", second["id"]),
                    "sensor_requests": records(fid, "sensor_requests"),
                    "sensor_responses": records(fid, "sensor_responses"), "work_order_history": historical,
                    "same_logical_work_order": True, "facility_condition": "unresolved",
                    "neighbor_zone": other_zone, "neighbor_tags_before_and_after": neighbor_before}

        a = exercise("food-a", "cook")
        a_before = state_tags("food-a", "cook")
        b = exercise(PACK["site_id"], "conservation")
        a_after = state_tags("food-a", "cook")
        assert a_before == a_after
        assert b["target_airflow_m3_h"] == 560 and b["late_low_flow"]["observation"]["airflow"] == 515
        assert b["zone_index"] == 1 and a["binding"] != b["binding"]
        events = [json.loads(row) for row in trace.read_text().splitlines()]
        origins = {core.identities[role + ":" + fid] for fid in configs for role in ("maintenance", "bridge", "sensor")}
        # Retain selected role receipts, not configuration secrets or runtime files.
        writes = [event for event in events if event["origin"] in origins and event["method"] == "POST"]
        after = hashes()
        return {"status": "passed", "captured_at": utcnow(), "scope":
                "Scripted synthetic commissioning, actual isolated ACME CSE and separate shipped worker CLI processes. "
                "Local independent-sample bridge only; no new hosted model inference, MEC platform/API or physical experiment.",
                "isolation": {"temporary_runtime": True, "ephemeral_loopback_port": True, "cse_pid": cse_process.pid,
                              "existing_services_or_vm_modified": False, "owned_workers_exited": True, "cse_stopped_on_exit": True},
                "acme_version": version, "administrator_activation": active, "operator_activation_denied": operator_denied,
                "persisted_templates_after_core_restart": configs[PACK["site_id"]], "role_templates": configs,
                "applications": {"operations": "Original Core, in-process commissioning driver", "maintenance_and_bridge": launched,
                                 "sensor": "Separate facility-scoped AE clients inject independent virtual observations"},
                "facility_a": a, "new_facility_b": b, "permission_denials": denials,
                "facility_a_unchanged_while_b_operated": {"before": a_before, "after": a_after},
                "worker_write_receipts": writes, "source_sha256": after,
                "source_unchanged_during_run": before == after, "source_before": before}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": result["status"], "site": result["new_facility_b"]["facility_id"],
                      "target_m3_h": result["new_facility_b"]["target_airflow_m3_h"],
                      "same_work_order": result["new_facility_b"]["same_logical_work_order"],
                      "source_unchanged": result["source_unchanged_during_run"]}))
