#!/usr/bin/env python3
"""Exercise native oneM2M services against a running real CSE.

This creates only a unique smoke namespace and removes it on success or failure.
The simulated observation is not a physical measurement.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from opensoom.onem2m import CSEClient, CSEError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--base", default="cse-in")
    parser.add_argument("--ca-file")
    parser.add_argument("--evidence", default="evidence/runtime/cse-smoke.json")
    args = parser.parse_args()
    suffix = uuid.uuid4().hex[:10]
    actor = "Csmoke" + suffix
    stranger = "Cdenied" + suffix
    namespace = "smoke-" + suffix
    root = args.base + "/" + namespace
    events: queue.Queue[dict] = queue.Queue()
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            events.put({"rqi": self.headers.get("X-M2M-RI"), "body": payload})
            self.send_response(200)
            self.send_header("X-M2M-RSC", "2000")
            self.send_header("X-M2M-RI", self.headers.get("X-M2M-RI", ""))
            self.send_header("X-M2M-RVI", "4")
            self.end_headers()
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    trace_path = ROOT / ".runtime" / f"cse-smoke-{suffix}.jsonl"
    client = CSEClient(args.url, ca_file=args.ca_file, trace_path=trace_path)
    evidence = {"kind": "actual_CSE_execution", "cse": "ACME 2026.5.3", "transport": "HTTPS" if args.url.startswith("https") else "HTTP_loopback", "physical_data": "simulated", "checks": {}, "limitations": ["ACP tests use claimed originators on a trusted loopback transport; not proof of cryptographic AE identity binding.", "CSE success and notifications do not prove actuator response or ventilation performance."]}
    cleanups = []
    try:
        evidence["checks"]["cse_base"] = client.retrieve(args.base)
        ae = client.create(args.base, 2, {"m2m:ae": {"rn": namespace, "api": "N.opensoom.smoke", "rr": True, "srv": ["4"]}}, origin=actor)
        cleanups.append(root)
        actor = ae["body"]["m2m:ae"]["aei"]
        evidence["checks"]["ae_registration"] = {"rsc": ae["rsc"], "aei": actor, "rqi": ae["rqi"]}
        acp = client.create(args.base, 1, {"m2m:acp": {"rn": namespace + "-acp", "pv": {"acr": [{"acor": [actor], "acop": 63}]}, "pvs": {"acr": [{"acor": [actor], "acop": 63}]}}})
        acp_path = args.base + "/" + namespace + "-acp"
        cleanups.insert(0, acp_path)
        cnt = client.create(root, 3, {"m2m:cnt": {"rn": "observations", "lbl": ["opensoom", "smoke"], "acpi": [acp["body"]["m2m:acp"]["ri"]]}}, origin=actor)
        endpoint = f"http://127.0.0.1:{server.server_port}/notify"
        sub = client.create(root + "/observations", 23, {"m2m:sub": {"rn": "watch", "nu": [endpoint], "enc": {"net": [3]}, "nct": 1}}, origin=actor)
        created = client.create(root + "/observations", 4, {"m2m:cin": {"con": {"pm25_ug_m3": 18, "simulated": True}, "cnf": "application/json:0"}}, origin=actor)
        found = client.discover(root, filters={"ty": 3, "lbl": "smoke"}, origin=actor)
        assert found["body"].get("m2m:uril"), found
        evidence["checks"]["discovery"] = found
        denied = None
        try:
            client.retrieve(root + "/observations", origin=stranger)
        except CSEError as error:
            denied = error.result
        assert denied and denied["rsc"] == 4103, denied
        evidence["checks"]["unprivileged_acp_denial"] = denied
        evidence["checks"]["permitted_acp_read"] = client.retrieve(root + "/observations", origin=actor)
        other_acp = client.create(args.base, 1, {"m2m:acp": {"rn": namespace + "-other-acp", "pv": {"acr": [{"acor": [actor], "acop": 63}]}, "pvs": {"acr": [{"acor": [actor], "acop": 63}]}}})
        other_acp_path = args.base + "/" + namespace + "-other-acp"
        cleanups.insert(0, other_acp_path)
        second = client.create(root, 3, {"m2m:cnt": {"rn": "second-zone", "acpi": [other_acp["body"]["m2m:acp"]["ri"]]}}, origin=actor)
        group = client.create(root, 9, {"m2m:grp": {"rn": "zone-group", "mt": 3, "mnm": 2, "mid": [cnt["body"]["m2m:cnt"]["ri"], second["body"]["m2m:cnt"]["ri"]]}}, origin=actor)
        grouped = client.group_read(root + "/zone-group", origin=actor)
        replies = grouped["body"]["m2m:agr"]["m2m:rsp"]
        assert replies and all(r["rsc"] == 2000 for r in replies), grouped
        evidence["checks"]["native_group_fanout"] = grouped
        client.update(other_acp_path, {"m2m:acp": {"pv": {"acr": [{"acor": [stranger], "acop": 63}]}}}, origin=actor)
        partial = None
        try:
            client.group_read(root + "/zone-group", origin=actor)
        except CSEError as error:
            partial = error.result
        assert partial and partial["rsc"] == 4103, partial
        first_member = client.retrieve(root + "/observations", origin=actor)
        second_denied = None
        try:
            client.retrieve(root + "/second-zone", origin=actor)
        except CSEError as error:
            second_denied = error.result
        assert second_denied and second_denied["rsc"] == 4103
        evidence["checks"]["native_group_partial_failure"] = {"native_aggregate_error": partial, "independent_member_checks": [first_member, second_denied], "observed_behavior": "ACME aborts the aggregate on the denied member; no all-success or native mixed-result claim."}
        sdt = client.create(root, 28, {"cod:aiQSr": {"rn": "air-quality", "cnd": "org.onem2m.common.moduleclass.airQualitySensor", "lbl": ["opensoom", "air-quality"], "pm25": 18, "co2": 750.0}}, origin=actor)
        evidence["checks"]["sdt_air_quality_creation"] = sdt
        evidence["checks"]["sdt_discovery"] = client.discover(root, filters={"ty": 28, "lbl": "air-quality"}, origin=actor)
        invalid = None
        try:
            client.update(root + "/air-quality", {"cod:aiQSr": {"pm25": "invalid"}}, origin=actor)
        except CSEError as error:
            invalid = error.result
        assert invalid and invalid["rsc"] == 4000, invalid
        evidence["checks"]["sdt_type_rejection"] = invalid
        notifications = []
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                event = events.get(timeout=0.2)
                notifications.append(event)
                if event["body"].get("m2m:sgn", {}).get("nev"):
                    break
            except queue.Empty:
                pass
        assert any(e["body"].get("m2m:sgn", {}).get("vrq") for e in notifications), notifications
        assert any(e["body"].get("m2m:sgn", {}).get("nev") for e in notifications), notifications
        evidence["checks"]["subscription"] = {"creation_rqi": sub["rqi"], "cin_rqi": created["rqi"], "verification_and_notification": notifications}
        evidence["result"] = "PASS_NATIVE_CSE_SMOKE"
    finally:
        for path in reversed(cleanups):
            try:
                client.delete(path)
            except CSEError:
                pass
        client.close()
        server.shutdown()
        server.server_close()
    evidence["request_trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    # Publish selected synthetic requests/results, not environment details or credentials.
    destination = ROOT / args.evidence
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"result": evidence["result"], "checks": list(evidence["checks"]), "evidence": args.evidence}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
