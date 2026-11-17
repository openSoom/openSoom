#!/usr/bin/env python3
"""Run two actual openSoom facilities through a central CSE outage and replay."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx

from opensoom.core import Core
from opensoom.federation import FederationReceiver
from opensoom.onem2m import CSEClient, CSEError

CENTRAL_ACTOR = "Ccentraloperator"
SITES = {
    "food": {"facility_id": "food-a", "profile_id": "food-production", "api_port": 8091, "cse_port": 8181, "zone": "cook"},
    "learning": {"facility_id": "learning-b", "profile_id": "learning-space", "api_port": 8092, "cse_port": 8182, "zone": "classroom"},
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def source_hashes():
    paths = [ROOT / "src/opensoom" / (name + ".py") for name in ("core", "app", "models", "policy", "adapters", "store", "onem2m", "federation")]
    paths += [Path(__file__).resolve(), ROOT / "scripts/cse_runtime.py", ROOT / "deploy/acme-single.ini", *sorted((ROOT / "profiles").glob("*.json"))]
    if (ROOT / "config/facilities.json").exists():
        paths.append(ROOT / "config/facilities.json")
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def runtime_command(*args):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/cse_runtime.py"), *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Project CSE command failed: " + result.stdout.strip())
    return json.loads(result.stdout.strip().splitlines()[-1])


def wait_for(check, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (httpx.TransportError, CSEError):
            pass
        time.sleep(0.2)
    raise TimeoutError("Product topology condition was not reached in the bounded wait")


def api(site, method, path, data=None):
    credentials = json.loads((site["runtime"] / "service-credentials.json").read_text())
    with httpx.Client(base_url=f"http://127.0.0.1:{site['api_port']}", timeout=15, trust_env=False, headers={"Authorization": "Bearer " + credentials["operator_token"]}) as client:
        response = client.request(method, path, json=data)
        response.raise_for_status()
        return response.json()


def stop_apps(records):
    for record in records:
        command = subprocess.run(["ps", "-p", str(record["pid"]), "-o", "command="], capture_output=True, text=True).stdout
        cwd = subprocess.run(["lsof", "-a", "-p", str(record["pid"]), "-d", "cwd", "-Fn"], capture_output=True, text=True).stdout
        owned_module = "opensoom.cli serve" in command or "uvicorn opensoom.app:app" in command
        if "n" + str(ROOT) in cwd.splitlines() and owned_module and f"--port {record['api_port']}" in command and record["api_port"] in (8091, 8092):
            try:
                os.kill(record["pid"], signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 20
    for record in records:
        while time.monotonic() < deadline:
            result = subprocess.run(["ps", "-p", str(record["pid"]), "-o", "stat="], capture_output=True, text=True)
            if result.returncode or result.stdout.strip().startswith("Z"):
                break
            time.sleep(0.1)


def start_apps(run_id):
    folder = ROOT / ".runtime/product-topology"
    folder.mkdir(parents=True, exist_ok=True)
    pidfile = folder / "processes.json"
    if pidfile.exists():
        stop_apps(json.loads(pidfile.read_text()))
        time.sleep(1)
    records, processes = [], {}
    for name, site in SITES.items():
        runtime = folder / run_id / name
        runtime.mkdir(parents=True, mode=0o700)
        site["runtime"] = runtime
        env = {key: value for key, value in os.environ.items() if not key.startswith("OPENSOOM_") and key not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY"}}
        env.update(OPENSOOM_RUNTIME_DIR=str(runtime), OPENSOOM_FACILITY_IDS=site["facility_id"], OPENSOOM_CSE_URL=f"http://127.0.0.1:{site['cse_port']}", OPENSOOM_CSE_BASE="cse-" + name, OPENSOOM_NOTIFY_URL=f"http://127.0.0.1:{site['api_port']}/api/notify", OPENSOOM_CENTRAL_ORIGIN="/opensoom-central/" + CENTRAL_ACTOR)
        with (runtime / "service.log").open("a") as log:
            # The ordinary CLI owns one lifecycle record for the main service.
            # This explicit topology harness owns its two independent API PIDs.
            process = subprocess.Popen([str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "opensoom.app:app", "--host", "127.0.0.1", "--port", str(site["api_port"]), "--no-access-log"], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        records.append({"pid": process.pid, "api_port": site["api_port"], "runtime": str(runtime)})
        processes[site["api_port"]] = process
    pidfile.write_text(json.dumps(records, indent=2) + "\n")
    for site in SITES.values():
        def ready(site=site):
            if processes[site["api_port"]].poll() is not None:
                raise RuntimeError("Facility API exited; inspect its .runtime/product-topology service.log")
            credential_path = site["runtime"] / "service-credentials.json"
            if not credential_path.exists():
                return None
            with httpx.Client(timeout=1, trust_env=False) as client:
                result = client.get(f"http://127.0.0.1:{site['api_port']}/api/health").json()
                credentials = json.loads(credential_path.read_text())
                same_instance = client.get(f"http://127.0.0.1:{site['api_port']}/api/state", headers={"Authorization": "Bearer " + credentials["operator_token"]}).status_code == 200
            return result if same_instance and result["cse_connected"] and result["configured_facilities"] == 1 else None
        wait_for(ready)
    return records


def snapshot(central, name):
    site = SITES[name]
    freshness_limit = json.loads((ROOT / "profiles" / (site["profile_id"] + ".json")).read_text())["freshness_seconds"]
    base = f"~/opensoom-{name}/cse-{name}/opensoom/facilities/{site['facility_id']}"
    discovery = central.discover(base, {"ty": 3, "lbl": "opensoom:observations"}, origin=CENTRAL_ACTOR)
    assert len(discovery["body"]["m2m:uril"]) == 3
    rows = []
    for uri in discovery["body"]["m2m:uril"]:
        container = central.retrieve("~" + uri, origin=CENTRAL_ACTOR)
        latest = central.retrieve("~" + uri + "/la", origin=CENTRAL_ACTOR)
        raw = latest["body"]["m2m:cin"]["con"]
        observation = json.loads(raw) if isinstance(raw, str) else raw
        assert observation["facility_id"] == site["facility_id"]
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(observation["observed_at"])).total_seconds()
        rows.append({"zone_id": observation["zone_id"], "container_state_tag": container["body"]["m2m:cnt"]["st"], "observation_age_seconds": round(age, 3), "freshness_limit_seconds": freshness_limit, "fresh": 0 <= age <= freshness_limit, "latest": latest})
    return {"read_at": now(), "discovery": discovery, "zones": rows}


def intent_for(site, request_id, ttl=30, **changes):
    issued = datetime.now(timezone.utc)
    return {"schema_version": 1, "request_id": request_id, "facility_id": site["facility_id"], "zone_id": site["zone"], "profile_id": site["profile_id"], "profile_version": 1, "issued_at": issued.isoformat(timespec="milliseconds"), "expires_at": (issued + timedelta(seconds=ttl)).isoformat(timespec="milliseconds"), "action": "set_damper", "value": 100.0, "reason": "Preauthorized virtual distributed scenario", **changes}


def make_receiver(name, queue_ri):
    site = SITES[name]
    previous = os.environ.get("OPENSOOM_CSE_BASE")
    os.environ["OPENSOOM_CSE_BASE"] = "cse-" + name
    try:
        core = Core(runtime=site["runtime"], cse=CSEClient(f"http://127.0.0.1:{site['cse_port']}"))
    finally:
        if previous is None:
            os.environ.pop("OPENSOOM_CSE_BASE", None)
        else:
            os.environ["OPENSOOM_CSE_BASE"] = previous
    return FederationReceiver(core, site["facility_id"], site["profile_id"], queue_ri)


def retrieved_intent(local, resource):
    # The facility's own registered operator retrieves via its MN-CSE's Mcc route.
    return local.retrieve("~/opensoom-central/" + resource, origin="Cosoperator")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-running", action="store_true", help="Leave only this script's facility APIs available for inspection")
    args = parser.parse_args()
    run_id = "topology-" + uuid.uuid4().hex[:10]
    subprocess.run([sys.executable, str(ROOT / "scripts/cse_bootstrap.py"), "multisite", "--skip-install"], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    apps, central_stopped, receivers = [], False, []
    central = CSEClient("http://127.0.0.1:8180", timeout=2)
    sites = {name: CSEClient(f"http://127.0.0.1:{site['cse_port']}") for name, site in SITES.items()}
    evidence = {"run_id": run_id, "started_at": now(), "kind": "actual_openSoom_multi_CSE_continuity", "physical_devices": "simulated", "source_sha256_before": source_hashes(), "checks": {}, "limitations": ["Separate processes on one host; not geographic distribution, MEC, or handover.", "Central outage is an actual stopped IN-CSE; the two MN-CSEs and facility APIs remain running.", "Central snapshots expose a polling gap; retained local samples are not claimed to have been delivered live.", "Intent expiry/profile rejection is a facility service decision after a successful CSE read; ACP denial is recorded separately.", "Loopback HTTP retains the documented trusted-local-process identity boundary."]}
    queue_root = "cse-central/federation-" + run_id
    try:
        try:
            central.create("cse-central", 2, {"m2m:ae": {"rn": "central-operator", "api": "N.org.opensoom.central", "rr": False, "srv": ["4"]}}, origin=CENTRAL_ACTOR)
        except CSEError as error:
            if error.rsc not in (4105, 4117):
                raise
        try:
            apps = start_apps(run_id)
        except Exception:
            # A failed second API must not leave the first child running.
            pidfile = ROOT / ".runtime/product-topology/processes.json"
            if pidfile.exists():
                stop_apps([item for item in json.loads(pidfile.read_text()) if run_id in item.get("runtime", "")])
            raise
        for site in SITES.values():
            api(site, "POST", "/api/demo/start", {"facility_id": site["facility_id"], "scenario": "normal", "autorun": False})
        before = {name: snapshot(central, name) for name in SITES}
        evidence["checks"]["central_product_discovery_before_outage"] = before
        for name, local in sites.items():
            for row in before[name]["zones"]:
                path = f"cse-{name}/opensoom/facilities/{SITES[name]['facility_id']}/{row['zone_id']}/observations"
                local.update(path, {"m2m:cnt": {"at": ["/opensoom-central"], "aa": ["lbl"]}})
        announcements = central.discover("cse-central", {"ty": 10003, "lbl": "opensoom:observations"})
        assert len(announcements["body"]["m2m:uril"]) >= 6
        evidence["checks"]["product_observation_announcements"] = announcements
        policy = central.create("cse-central", 1, {"m2m:acp": {"rn": "policy-" + run_id, "pv": {"acr": [{"acor": [CENTRAL_ACTOR], "acop": 63}, {"acor": ["/opensoom-food/Cosoperator", "/opensoom-learning/Cosoperator"], "acop": 34}]}, "pvs": {"acr": [{"acor": ["CAdmin"], "acop": 63}]}}})
        queue = central.create("cse-central", 3, {"m2m:cnt": {"rn": "federation-" + run_id, "acpi": [policy["body"]["m2m:acp"]["ri"]], "mni": 20, "lbl": ["opensoom:central-intents", run_id]}})
        queue_ri = queue["body"]["m2m:cnt"]["ri"]
        delayed = intent_for(SITES["food"], run_id + ":delayed", ttl=3)
        queued = central.create(queue_root, 4, {"m2m:cin": {"con": json.dumps(delayed), "cnf": "application/json:0"}}, origin=CENTRAL_ACTOR)
        delayed_ri = queued["body"]["m2m:cin"]["ri"]
        evidence["checks"]["central_intent_persisted_before_outage"] = queued
        outage_started = now()
        runtime_command("stop", "--name", "central")
        central_stopped = True
        failure = None
        try:
            central.retrieve("cse-central")
        except CSEError as error:
            failure = error.result
        assert failure and failure["rsc"] == 0
        evidence["checks"]["central_unavailable"] = {"at": outage_started, "response": failure, "cached_snapshot_status": "unavailable_do_not_treat_cache_as_live"}
        local_run = api(SITES["food"], "POST", "/api/demo/start", {"facility_id": "food-a", "scenario": "exhaust_fault", "autorun": True})
        def completed_local():
            value = api(SITES["food"], "GET", "/api/runs/" + local_run["run_id"])
            return value if value["status"] == "completed" else None
        run = wait_for(completed_local, 20)
        local_state = api(SITES["food"], "GET", "/api/state")
        command = next(item for item in local_state["commands"] if item["id"] in run["command_ids"])
        assert command["status"] == "verified" and command["ack"] and command["verification_rqi"]
        assert all(item["status"] == "resolved" for item in local_state["incidents"])
        assert run["outcome"] == "PASS_FIXTURE"
        evidence["checks"]["local_recovery_while_central_down"] = {"run": run, "command": command, "incidents": local_state["incidents"], "local_runtime": local_state["runtime"]}
        runtime_command("start", "--name", "central", "--port", "8180")
        central_stopped = False
        reconnected_at = now()
        after = {name: wait_for(lambda name=name: snapshot(central, name), 20) for name in SITES}
        gaps = {}
        for name in SITES:
            previous = {row["zone_id"]: row for row in before[name]["zones"]}
            assert all(row["fresh"] for row in after[name]["zones"])
            gaps[name] = {row["zone_id"]: row["container_state_tag"] - previous[row["zone_id"]]["container_state_tag"] for row in after[name]["zones"]}
        evidence["checks"]["reconnected_product_state"] = {"reconnected_at": reconnected_at, "outage_seconds": (datetime.fromisoformat(reconnected_at) - datetime.fromisoformat(outage_started)).total_seconds(), "snapshots": after, "container_state_tag_delta_between_central_snapshots": gaps, "gap_interpretation": "State changed while the central snapshot was unavailable; this is not a packet-loss count or proof of complete history replay.", "live_central_observation_during_gap": False}
        food_receiver = make_receiver("food", queue_ri)
        receivers.append(food_receiver)
        reread = retrieved_intent(sites["food"], delayed_ri)
        expired = food_receiver.receive(reread)
        replay = food_receiver.receive(retrieved_intent(sites["food"], delayed_ri))
        assert expired["status"] == "rejected" and expired["code"] == "central_intent_expired"
        assert replay["replayed"] and replay["status"] == "rejected"
        wrong = intent_for(SITES["food"], run_id + ":wrong-profile", profile_id="learning-space")
        wrong_write = central.create(queue_root, 4, {"m2m:cin": {"con": json.dumps(wrong)}}, origin=CENTRAL_ACTOR)
        wrong_receipt = food_receiver.receive(retrieved_intent(sites["food"], wrong_write["body"]["m2m:cin"]["ri"]))
        assert wrong_receipt["code"] == "central_profile_mismatch"
        final_food = api(SITES["food"], "GET", "/api/state")
        assert final_food["commands"] == local_state["commands"]
        assert final_food["incidents"] == local_state["incidents"]
        evidence["checks"]["delayed_and_wrong_profile_intents"] = {"actual_cse_read": reread, "expired_receipt": expired, "duplicate_expired_receipt": replay, "wrong_profile_receipt": wrong_receipt, "command_ids_before": [item["id"] for item in local_state["commands"]], "command_ids_after": [item["id"] for item in final_food["commands"]], "local_incident_unchanged": True}
        denied = None
        try:
            central.create("~/opensoom-food/cse-food/opensoom/facilities/food-a/cook/commands", 4, {"m2m:cin": {"con": json.dumps(delayed)}}, origin=CENTRAL_ACTOR)
        except CSEError as error:
            denied = error.result
        assert denied and denied["rsc"] == 4103
        evidence["checks"]["central_cannot_bypass_local_authority"] = denied
        api(SITES["learning"], "POST", "/api/demo/start", {"facility_id": "learning-b", "scenario": "exhaust_fault", "autorun": False})
        fresh = intent_for(SITES["learning"], run_id + ":fresh")
        fresh_write = central.create(queue_root, 4, {"m2m:cin": {"con": json.dumps(fresh)}}, origin=CENTRAL_ACTOR)
        learning_receiver = make_receiver("learning", queue_ri)
        receivers.append(learning_receiver)
        fresh_read = retrieved_intent(sites["learning"], fresh_write["body"]["m2m:cin"]["ri"])
        accepted = learning_receiver.receive(fresh_read)
        assert accepted["status"] == "accepted"
        def confirmed():
            value = api(SITES["learning"], "POST", "/api/tools/verify_result", {"arguments": {"facility_id": "learning-b", "command_id": accepted["command_id"]}})
            return value if value["complete"] else None
        verified = wait_for(confirmed, 20)
        accepted_replay = learning_receiver.receive(retrieved_intent(sites["learning"], fresh_write["body"]["m2m:cin"]["ri"]))
        assert accepted_replay["replayed"] and accepted_replay["command_id"] == accepted["command_id"]
        learning_state = api(SITES["learning"], "GET", "/api/state")
        assert len([item for item in learning_state["commands"] if item["request_id"] == fresh["request_id"]]) == 1
        evidence["checks"]["fresh_central_intent_local_policy_ack_recovery"] = {"actual_cse_read": fresh_read, "accepted_receipt": accepted, "verified_result": verified, "replayed_receipt": accepted_replay, "one_local_command_only": True}
        evidence["source_sha256_after"] = source_hashes()
        evidence["source_changed_during_run"] = evidence["source_sha256_before"] != evidence["source_sha256_after"]
        assert not evidence["source_changed_during_run"], "Source changed during topology acceptance"
        evidence.update(result="PASS_PRODUCT_MULTISITE_CONTINUITY", completed_at=now())
        path = ROOT / "evidence/runtime/product-multisite-continuity.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps({"result": evidence["result"], "run_id": run_id, "evidence": str(path.relative_to(ROOT))}))
    finally:
        if central_stopped:
            runtime_command("start", "--name", "central", "--port", "8180")
        for receiver in receivers:
            receiver.core.cse.close()
        if not args.keep_running:
            stop_apps(apps)
        central.close()
        for local in sites.values():
            local.close()


if __name__ == "__main__":
    main()
