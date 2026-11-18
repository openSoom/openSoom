#!/usr/bin/env python3
"""Exercise repeated and unordered measurements in isolated ACME and operations stores."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from cse_multiapp_smoke import child_env, start_cse, stop_process
from facility_worker_acceptance import notify_sink
from opensoom.core import Core, OperationError
from opensoom.models import ActionRequest, Observation, utcnow
from opensoom.onem2m import CSEClient
from opensoom.policy import diagnose


def capture():
    with ExitStack() as stack:
        folder = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="opensoom-observation-sequence-")))
        processes = []
        stack.callback(lambda: [stop_process(proc) for proc in processes])
        url, _, version = start_cse(folder, processes)
        sink = notify_sink()
        stack.callback(sink.server_close)
        stack.callback(sink.shutdown)
        env = {**child_env(), "OPENSOOM_CSE_BASE":"cse-multiapp",
               "OPENSOOM_NOTIFY_URL":f"http://127.0.0.1:{sink.server_port}/notify"}
        stack.enter_context(patch.dict(os.environ, env, clear=True))
        client = stack.enter_context(CSEClient(url))
        service = Core(runtime=folder/"operations", cse=client)
        service.bootstrap()
        fid, zid = "food-a", "cook"
        actor = {"role":"operator", "facilities":[fid]}
        stream = fid + ":" + zid
        results = {}
        for case_id in ("retransmission", "delayed", "contradictory", "future", "sensor_gap", "unread_interval"):
            if case_id == "sensor_gap":
                service.profiles["food-production"]["freshness_seconds"] = 1
            run = service.start_demo(fid, "exhaust_fault", False, actor)["run_id"]
            facility = service.facility(fid)
            zone = service.zone(facility, zid)
            request = ActionRequest(facility_id=fid, zone_id=zid, action="set_damper", value=100,
                                    reason="Virtual observation order trial", request_id=run+"-damper")
            cmd = service.request_action(request, actor, run)
            service.acknowledge_pending(facility, cmd["id"])
            ack = client.retrieve(zone["path"]+"/acks/la", origin=service.identities["operator"])
            ack_resource = ack["body"]["m2m:cin"]
            assert json.loads(ack_resource["con"])["command_id"] == cmd["id"]
            time.sleep(.035)
            anchor = datetime.now(timezone.utc)
            checkpoints = []

            def send(label, offset_ms, healthy=True):
                stamp = (anchor+timedelta(milliseconds=offset_ms)).isoformat(timespec="milliseconds")
                obs = Observation(facility_id=fid, zone_id=zid, observed_at=stamp, received_at=utcnow(),
                                  adapter="vendor-a", airflow=1050 if healthy else 360, fan_running=True,
                                  pm25=10 if healthy else 63, co2=600, damper_pct=100)
                sent = service.publish(obs)
                native = sent["body"]["m2m:cin"]
                immutable = client.retrieve(zone["path"]+"/observations/"+native["rn"], origin=service.identities["operator"])
                assert immutable["body"]["m2m:cin"]["ri"] == native["ri"]
                current = service.refresh_observation(fid, zid)
                incident = service.store.get("incidents", stream)
                command = service.verify(cmd["id"], actor, fid, run)
                sdtr = client.retrieve(zone["standard_path"], origin=service.identities["operator"])
                views = {}
                if label in ("late_healthy_after_critical", "retransmitted_healthy_at_conflict_time", "future_sample"):
                    observer = {"role":"observer","facilities":[fid]}
                    evidence = service.tool("read_evidence", {"facility_id":fid,"zone_id":zid}, observer)
                    zone_state = next(z for z in evidence["zones"] if z["id"] == zid)
                    group = service.tool("read_group", {"facility_id":fid}, observer)["group"]
                    resources = [response["pc"]["m2m:cin"] for response in group["body"]["m2m:agr"]["m2m:rsp"]]
                    reading = next(r for r in resources if json.loads(r["con"])["zone_id"] == zid)
                    assert reading["ri"] == native["ri"]
                    views = {"group_raw_cin":reading["ri"],"group_native_rqi":group["rqi"],
                             "read_evidence_cin":zone_state.get("observation_cin"), "read_evidence_status":zone_state["status"],
                             "read_evidence_quality":zone_state["observations"]["airflow"]["quality"],
                             "verify_result_cin":command.get("observation_cin")}
                checkpoints.append({"step":label,"observed_at":stamp,"cin":native["ri"],"native_st":native["st"],"read_rqi":immutable["rqi"],
                                    "projected_cin":current["cin_id"],"quality":current.get("sequence_issue"),
                                    "recovery_count":incident["recovery_count"],"incident":incident["status"],
                                    "complete":command["complete"],"sdt_pm25":sdtr["body"]["cod:aiQSr"]["pm25"],
                                    "recovery_cins":[s["cin_ri"] for s in command.get("recovery_observations",[])], **views})
            send("healthy", -4)
            if case_id == "retransmission":
                service = Core(runtime=folder/"operations", cse=client)
                send("recreated_same_sample_after_restart", -4)
                send("distinct_healthy", 0)
            elif case_id == "delayed":
                send("older_healthy", -9)
                send("current_critical", 0, False)
                send("late_healthy_after_critical", -7)
                time.sleep(.015)
                send("first_new_healthy", 4)
                send("second_new_healthy", 8)
            elif case_id == "contradictory":
                send("conflicting_same_time", -4, False)
                send("retransmitted_healthy_at_conflict_time", -4)
                try:
                    retry = request.model_copy(update={"request_id":run+"-conflicting-observation"})
                    service.request_action(retry, actor, run)
                except OperationError as exc:
                    control = exc.code
                else:
                    control = "accepted"
                send("first_new_healthy", 0)
                time.sleep(.01)
                send("second_new_healthy", 3)
            elif case_id == "future":
                send("future_sample", 60000)
                send("old_healthy_after_future", -8)
                send("first_new_healthy", 0)
                time.sleep(.01)
                send("second_new_healthy", 3)
            elif case_id == "sensor_gap":
                time.sleep(1.15)
                anchor = datetime.now(timezone.utc)
                send("first_healthy_after_sensor_gap", -4)
                send("second_healthy_after_sensor_gap", 0)
            else:
                # An external adapter can write while the operations reader is offline.
                hidden = Observation(facility_id=fid, zone_id=zid,
                    observed_at=(anchor-timedelta(milliseconds=2)).isoformat(), adapter="vendor-a",
                    airflow=360, pm25=63, co2=600, fan_running=True, damper_pct=95)
                hidden_cin = service.create_content(zone["path"]+"/observations", hidden.model_dump(),
                                                    service.identities["adapter"])["body"]["m2m:cin"]
                send("first_read_after_unseen_critical_cin", 0)
                time.sleep(.012)
                send("second_contiguous_healthy", 7)
            results[case_id] = {"profile_freshness_seconds":service.profiles["food-production"]["freshness_seconds"],
                                "run_id":run, "command_id":cmd["id"], "ack_cin":ack_resource["ri"],
                                "ack_rqi":ack["rqi"],"checkpoints":checkpoints}
            if case_id == "contradictory":
                results[case_id]["control_at_conflict"] = control
            if case_id == "unread_interval":
                results[case_id]["unseen_input"] = {"cin":hidden_cin["ri"],"native_st":hidden_cin["st"],
                                                    "airflow":hidden.airflow}
        # The new scenario intentionally supplies stale acquisition timestamps.
        stale = service.start_demo(fid, "stale", False, actor)["run_id"]
        stale_status = service.facility_view(service.facility(fid))["status"]
        return {"acme":version,"cases":results,"new_stale_scenario":{"run_id":stale,"status":stale_status},
                "source_sha256":{name:hashlib.sha256(Path(inspect.getfile(obj)).read_bytes()).hexdigest()
                                 for name,obj in (("src/opensoom/core.py",Core),("src/opensoom/policy.py",diagnose))}}


def verify(run):
    steps = {k:v["checkpoints"] for k,v in run["cases"].items()}
    assert [r["recovery_count"] for r in steps["retransmission"]] == [1,1,2]
    assert [r["recovery_count"] for r in steps["delayed"]] == [1,1,0,0,1,2]
    late = steps["delayed"][3]
    assert late["sdt_pm25"] == 63 and late["group_raw_cin"] == late["cin"]
    assert late["read_evidence_cin"] == late["verify_result_cin"] == steps["delayed"][2]["cin"]
    assert late["read_evidence_status"] == "critical"
    assert steps["contradictory"][2]["read_evidence_quality"] == "conflicting_measurements"
    assert steps["future"][1]["read_evidence_quality"] == "future_at_ingest"
    assert [r["recovery_count"] for r in steps["contradictory"]] == [1,0,0,1,2]
    assert run["cases"]["contradictory"]["control_at_conflict"] == "evidence_not_current"
    assert [r["recovery_count"] for r in steps["future"]] == [1,0,0,1,2]
    assert [r["recovery_count"] for r in steps["sensor_gap"]] == [1,1,2]
    assert [r["recovery_count"] for r in steps["unread_interval"]] == [1,1,2]
    first,after,_ = steps["unread_interval"]
    assert first["native_st"] < run["cases"]["unread_interval"]["unseen_input"]["native_st"] < after["native_st"]
    for rows in steps.values():
        assert all(not r["complete"] for r in rows[:-1]) and rows[-1]["complete"]
        assert len(set(rows[-1]["recovery_cins"])) == 2 and rows[-1]["cin"] == rows[-1]["recovery_cins"][-1]
    assert run["new_stale_scenario"]["status"] == "stale"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--capture-baseline",action="store_true",help="Record historical behavior before the fix.")
    parser.add_argument("--compare-with",type=Path,help="A baseline captured with this driver on the earlier source.")
    args = parser.parse_args()
    run = capture()
    if not args.capture_baseline:
        verify(run)
    if args.compare_with:
        baseline = json.loads(args.compare_with.read_text())
        for name in ("retransmission","delayed","sensor_gap","unread_interval"):
            assert baseline["cases"][name]["checkpoints"][1]["complete"]
        assert baseline["cases"]["contradictory"]["control_at_conflict"] == "accepted"
        report = {"status":"passed","method":"Same scripted acquisitions in separate fresh ACME instances with virtual equipment. The operations object is restarted on its original persistent store before resending the same acquisition.",
                  "clock_scope":"The adapter normalizes UTC acquisition times to milliseconds. More than five seconds ahead of native CSE creation time is invalid on arrival.",
                  "baseline":baseline,"current":run}
    else:
        report = run
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print({k:[r["recovery_count"] for r in v["checkpoints"]] for k,v in run["cases"].items()})
