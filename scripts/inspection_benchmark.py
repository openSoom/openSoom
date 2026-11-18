#!/usr/bin/env python3
"""Compare three ventilation decisions at the same checkpoint on real oneM2M records."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from cse_multiapp_smoke import ROOT, child_env, start_cse, stop_process
from facility_pack_acceptance import PACK
from facility_worker_acceptance import notify_sink
from opensoom import maintenance
from opensoom.core import Core
from opensoom.facility_pack import worker_templates
from opensoom.models import ActionRequest, Observation, utcnow
from opensoom.onem2m import CSEClient


MATRIX = "scenarios/inspection-benchmark.json"
SOURCES = [
    MATRIX, "scripts/inspection_benchmark.py", "scripts/cse_multiapp_smoke.py",
    "scripts/facility_worker_acceptance.py", "scripts/facility_pack_acceptance.py",
    "src/opensoom/core.py", "src/opensoom/maintenance.py", "src/opensoom/maintenance_worker.py",
    "src/opensoom/onem2m.py", "src/opensoom/facility_pack.py", "src/opensoom/policy.py",
    "src/opensoom/models.py", "src/opensoom/mec_sensor.py", "src/opensoom/store.py",
    "config/facilities.json", "profiles/food-production.json", "profiles/learning-space.json",
    "deploy/acme-single.ini", "deploy/cse-requirements.txt",
]
POLICIES = ("ack_only", "airflow_only", "opensoom")
SPECIFIC = {"inspect_actuator_feedback", "inspect_airflow_path"}


def fingerprint():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def phase_time(age):
    return (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(timespec="milliseconds")


def reread(client, path, origin=None):
    result = client.retrieve(path, origin=origin)
    cin = result["body"]["m2m:cin"]
    return json.loads(cin["con"]), cin["ri"], result["rqi"]


def replay_site(core, url, directory, matrix, case, fid, zid):
    """Inputs are published by the adapter/sensor. Expectations stay in the scorer."""
    facility = core.facility(fid)
    zone = core.zone(facility, zid)
    target = zone["minimum_airflow"]
    actors = {"role": "operator", "facilities": [fid]}
    run = core.start_demo(fid, "normal", False, actors)["run_id"]
    workers = worker_templates(core, fid)
    for role, fields in workers.items():
        (directory / f"{fid}-{role}.json").write_text(json.dumps({**fields, "cse_url": url, "bridge_mode": "local",
                                                                 "trace_path": str(directory / "roles.jsonl")}))

    def scan(role):
        subprocess.run([sys.executable, "-m", "opensoom.maintenance_worker", role, "--config",
                        str(directory / f"{fid}-{role}.json"), "--once"], cwd=ROOT, env=child_env(),
                       stdout=subprocess.DEVNULL, check=True, timeout=30)

    def observation(flow, high_particles=False, age=0):
        obs = Observation(facility_id=fid, zone_id=zid, observed_at=phase_time(age),
                          airflow=flow, pm25=zone["pm25_warning"] + 30 if high_particles else 10,
                          co2=600, fan_running=True, damper_pct=matrix["command_pct"], adapter=facility["adapter"])
        created = core.publish(obs)["body"]["m2m:cin"]
        value, ri, rqi = reread(core.cse, zone["path"] + "/observations/" + created["rn"], core.identities["operator"])
        maintenance.flush_outbox(core)
        return {"cin": ri, "read_rqi": rqi, "measured_at": value["observed_at"], "airflow_m3_h": value["airflow"],
                "pm25_ug_m3": value["pm25"]}

    def order():
        maintenance.refresh_work_orders(core)
        orders = [row for row in core.state(actors)["work_orders"] if row["run_id"] == run]
        if len(orders) != 1:
            raise ValueError("Expected one work order for this incident")
        return orders[0]

    initial = observation(target - 45)
    scan("maintenance")
    original = order()
    action = ActionRequest(facility_id=fid, zone_id=zid, action="set_damper", value=matrix["command_pct"],
                           reason="Virtual inspection benchmark", request_id=f"{run}-damper")
    command = core.request_action(action, actors, run)
    ack = None
    if case["ack"]:
        core.acknowledge_pending(facility, only_command_id=command["id"])
        event, cin, rqi = reread(core.cse, zone["path"] + "/acks/la", core.identities["operator"])
        assert event["command_id"] == command["id"] and event["value"] == command["value"]
        ack = {"cin": cin, "read_rqi": rqi, "at": event["ack_at"], "opening_pct": event["value"]}

    observations = [observation(target + delta, case.get("particles_above_warning", False),
                                case.get("airflow_age_seconds", 0)) for delta in case["followup_offsets_m3_h"]]
    scan("maintenance")
    shaft = None
    if "shaft_pct" in case:
        settle = workers["maintenance"]["settle_seconds"]
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(ack["at"])).total_seconds()
        time.sleep(max(0, settle - elapsed + .03))
        reading = {"facility_id": fid, "zone_id": zid, **workers["maintenance"]["assets"][zid],
                   "unit": "%", "value": case["shaft_pct"], "observed_at": phase_time(case.get("shaft_age_seconds", 0)),
                   "source": "independent_position_sensor", "simulated": True}
        origin = core.identities[f"sensor:{fid}"]
        parent = facility["path"] + "/independent_samples"
        cin = core.create_content(parent, reading, origin)["body"]["m2m:cin"]
        result, ri, rqi = reread(core.cse, parent + "/" + cin["rn"], origin)
        shaft = {"cin": ri, "read_rqi": rqi, "measured_at": result["observed_at"], "opening_pct": result["value"]}
    scan("bridge")
    scan("maintenance")

    final = order()
    raw, ri, rqi = reread(core.cse, final["resource_id"], core.identities[f"maintenance:{fid}"])
    assert raw["run_id"] == run and raw["work_order_id"] == original["work_order_id"] == final["work_order_id"]
    assert raw["status"] == "open" and raw["priority"] == final["priority"]
    assert not raw.get("sample") or raw["provider_receipt"]["sample_cin_ri"] == shaft["cin"]
    site_requests = core.cse.retrieve(facility["path"] + "/sensor_requests", origin=core.identities[f"bridge:{fid}"])
    # This facility and CSE were created for this one case.
    request_count = site_requests["body"]["m2m:cnt"]["cni"]
    incident = core.store.get("incidents", fid + ":" + zid)
    verified = core.verify(command["id"], actors, fid, run)
    assert incident["id"] == raw["incident_id"] and (incident["status"] == "resolved") == verified["complete"]

    profile = core.profiles[facility["profile"]]
    n = profile["recovery_samples"]
    at = datetime.now(timezone.utc)
    # A strong airflow-only baseline knows the current command, time, site target and confirmation count.
    tail = observations[-n:]
    good_airflow = bool(ack) and len(tail) == n and all(
        datetime.fromisoformat(ack["at"]) < datetime.fromisoformat(obs["measured_at"]) <= at
        and (at - datetime.fromisoformat(obs["measured_at"])).total_seconds() <= profile["freshness_seconds"]
        and obs["airflow_m3_h"] >= target for obs in tail)
    return {
        "case": case["id"], "facility": fid, "zone": zid, "run_id": run, "target_m3_h": target,
        "incident_id": raw["incident_id"], "command_id": command["id"], "command_cin": command["cse_resource_id"],
        "initial_low_flow_cin": initial["cin"], "ack": ack, "post_command_measurements": observations,
        "shaft": shaft, "work_order_id": raw["work_order_id"], "opening_order_cin": original["resource_id"],
        "final_order_cin": ri, "order_read_rqi": rqi, "final_order_revision": raw["revision"],
        "order_status": raw["status"], "evidence_status": raw["evidence_status"], "sensor_requests": request_count,
        "request_cin": raw.get("request_ri"), "response_cin": raw.get("response_ri"),
        "incident_status": incident["status"], "current_command_observed_result": verified["observed_result"],
        "decisions": {"ack_only": {"recovered": bool(ack), "inspection": "unavailable"},
                      "airflow_only": {"recovered": good_airflow, "inspection": "inspection"},
                      "opensoom": {"recovered": verified["complete"], "inspection": raw["priority"]}},
    }


def replay_case(matrix, case):
    processes = []
    with ExitStack() as stack:
        folder = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="opensoom-inspection-study-")))
        stack.callback(lambda: [stop_process(process) for process in processes])
        url, _, version = start_cse(folder, processes)
        sink = notify_sink()
        stack.callback(sink.server_close)
        stack.callback(sink.shutdown)
        env = {**child_env(), "OPENSOOM_CSE_BASE": "cse-multiapp",
               "OPENSOOM_NOTIFY_URL": f"http://127.0.0.1:{sink.server_port}/notify"}
        with patch.dict(os.environ, env, clear=True):
            client = stack.enter_context(CSEClient(url, trace_path=folder / "operations.jsonl"))
            core = Core(runtime=folder / "operations", cse=client)
            core.bootstrap()
            admin = {"role": "admin", "facilities": []}
            draft = core.tool("draft_facility", PACK, admin)
            core.tool("activate_facility", {"version": draft["version"]}, admin)
            records = [replay_site(core, url, folder, matrix, case, fid, zid) for fid, zid in matrix["sites"].items()]
    return version, records


def summarize(matrix, results):
    expected = {case["id"]: case["expect"] for case in matrix["cases"]}
    review = []
    for case in results:
        truth = expected[case["case"]]
        actual = case["decisions"]["opensoom"]
        assert truth["recovered"] == actual["recovered"] and truth["inspection"] == actual["inspection"], case
        assert case["sensor_requests"] == truth["shaft_requests"], case
        review.append((case, truth))
    groups = {
        "false_recoveries": [(row, truth) for row, truth in review if not truth["recovered"]],
        "missed_recoveries": [(row, truth) for row, truth in review if truth["recovered"]],
        "specific_first_checks_matching_reference": [(row, truth) for row, truth in review if truth["inspection"] in SPECIFIC],
        "unsupported_specific_checks_missing_or_stale_shaft": [(row, truth) for row, truth in review if row["case"] in ("shaft_missing", "shaft_stale")],
    }
    scores = {}
    for name, group in groups.items():
        counts = {}
        for policy in POLICIES:
            decisions = [row["decisions"][policy] for row, _ in group]
            if name == "false_recoveries":
                count = sum(d["recovered"] for d in decisions)
            elif name == "missed_recoveries":
                count = sum(not d["recovered"] for d in decisions)
            elif name == "specific_first_checks_matching_reference":
                count = sum(row["decisions"][policy]["inspection"] == truth["inspection"] for row, truth in group)
            else:
                count = sum(d["inspection"] in SPECIFIC for d in decisions)
            counts[policy] = count
        scores[name] = {"eligible": len(group), **counts}
    return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before = fingerprint()
    matrix = json.loads((ROOT / MATRIX).read_text())
    rows = []
    for case in matrix["cases"]:
        print(f"Testing {case['id']}...", flush=True)
        version, observed = replay_case(matrix, case)
        rows.extend(observed)
    assert fingerprint() == before, "Sources changed during the benchmark. Rerun on stable sources."
    report = {"status": "passed", "captured_at": utcnow(), "fixture": MATRIX,
              "scope": "Scripted virtual equipment and reference inspection priorities, real isolated ACME over HTTP, production operations core and separate maintenance/bridge CLI processes using local oneM2M shaft evidence. Baselines calculated on these same records. No cloud MEC, hosted model, field trial or elapsed-time benefit measured by this experiment.",
              "acme_version": version, "source_sha256": before, "scores": summarize(matrix, rows), "cases": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["scores"], indent=2))


if __name__ == "__main__":
    main()
