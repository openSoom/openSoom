#!/usr/bin/env python3
"""Verify real Mcc registration, routing, discovery and cross-scope denial."""
import argparse
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from opensoom.onem2m import CSEClient, CSEError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--central-port", type=int, default=8180)
    parser.add_argument("--food-port", type=int, default=8181)
    parser.add_argument("--learning-port", type=int, default=8182)
    args = parser.parse_args()
    suffix = uuid.uuid4().hex[:8]
    run_label = "opensoom-run-" + suffix
    operator = "Coperator" + suffix
    ae_name = "site-smoke-" + suffix
    central = CSEClient(f"http://127.0.0.1:{args.central_port}")
    sites = {"food": CSEClient(f"http://127.0.0.1:{args.food_port}"), "learning": CSEClient(f"http://127.0.0.1:{args.learning_port}")}
    cleanups = []
    evidence = {"kind": "actual_multi_CSE_Mcc_execution", "physical_data": "simulated", "topology": {"central": "IN-CSE /opensoom-central", "food": "MN-CSE /opensoom-food", "learning": "MN-CSE /opensoom-learning"}, "checks": {}, "limitations": ["Three actual CSE processes run on one host; no MEC hosting or geographic distribution is claimed.", "Local development HTTP trust boundary; this is separate from the verified HTTPS/MQTT TLS profile.", "Remote registration/announcements do not establish handover or automatic replication."]}
    try:
        registrations = central.discover("cse-central", {"ty": 16})
        assert len(registrations["body"]["m2m:uril"]) >= 2
        evidence["checks"]["native_remote_CSE_registrations"] = registrations
        central.create("cse-central", 2, {"m2m:ae": {"rn": ae_name, "api": "N.opensoom.central", "rr": True, "srv": ["4"]}}, origin=operator)
        cleanups.append((central, "cse-central/" + ae_name))
        for name, local in sites.items():
            base = "cse-" + name
            local_actor = "C" + name + suffix
            policy = local.create(base, 1, {"m2m:acp": {"rn": ae_name + "-policy", "pv": {"acr": [{"acor": [local_actor], "acop": 63}, {"acor": ["/opensoom-central/" + operator], "acop": 34}]}, "pvs": {"acr": [{"acor": [local_actor], "acop": 63}]}}})
            cleanups.append((local, base + "/" + ae_name + "-policy"))
            local.create(base, 2, {"m2m:ae": {"rn": ae_name, "api": "N.opensoom.facility", "rr": True, "srv": ["4"], "acpi": [policy["body"]["m2m:acp"]["ri"]]}}, origin=local_actor)
            local_root = base + "/" + ae_name
            cleanups.append((local, local_root))
            resource = local.create(local_root, 3, {"m2m:cnt": {"rn": "observations", "lbl": ["opensoom", name, run_label], "acpi": [policy["body"]["m2m:acp"]["ri"]], "at": ["/opensoom-central"], "aa": ["lbl"]}}, origin=local_actor)
            local.create(local_root + "/observations", 4, {"m2m:cin": {"con": {"facility": name, "simulated": True, "sequence": 1}}}, origin=local_actor)
            remote_path = "~/opensoom-" + name + "/" + local_root
            found = central.discover(remote_path, {"ty": 3, "lbl": name}, origin=operator)
            assert found["body"]["m2m:uril"], found
            observed = central.retrieve(remote_path + "/observations/la", origin=operator)
            assert observed["body"]["m2m:cin"]["con"]["facility"] == name
            denied = None
            try:
                central.retrieve(remote_path + "/observations/la", origin="COutsideScope")
            except CSEError as error:
                denied = error.result
            assert denied and denied["rsc"] == 4103
            write_denied = None
            try:
                central.create(remote_path + "/observations", 4, {"m2m:cin": {"con": {"unexpected_write": True}}}, origin=operator)
            except CSEError as error:
                write_denied = error.result
            assert write_denied and write_denied["rsc"] == 4103
            evidence["checks"][name] = {"resource_created": resource, "remote_discovery": found, "remote_read": observed, "cross_scope_denial": denied, "read_only_operator_write_denied": write_denied}
        announcements = None
        for _ in range(30):
            announcements = central.discover("cse-central", {"ty": 10003, "lbl": run_label})
            if len(announcements["body"].get("m2m:uril", [])) == 2:
                break
            time.sleep(0.1)
        assert announcements and len(announcements["body"].get("m2m:uril", [])) == 2
        evidence["checks"]["selective_container_announcements"] = announcements
        announced = [central.retrieve("~" + uri) for uri in announcements["body"]["m2m:uril"]]
        assert {item["body"]["m2m:cntA"]["lnk"].split("/")[1] for item in announced} == {"opensoom-food", "opensoom-learning"}
        assert all(run_label in item["body"]["m2m:cntA"]["lbl"] for item in announced)
        evidence["checks"]["announced_container_readback"] = announced
        evidence["result"] = "PASS_NATIVE_MULTISITE_CSE"
    finally:
        for client, path in reversed(cleanups):
            try:
                client.delete(path)
            except CSEError:
                pass
        central.close()
        for client in sites.values():
            client.close()
    path = ROOT / "evidence/runtime/cse-multisite-smoke.json"
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"result": evidence["result"], "evidence": str(path.relative_to(ROOT))}))


if __name__ == "__main__":
    main()
