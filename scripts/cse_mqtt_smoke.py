#!/usr/bin/env python3
"""Prove a native MQTT/TLS device write is visible through CSE HTTPS."""
import hashlib
import json
from pathlib import Path
import ssl
import socket
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from opensoom.onem2m import CSEClient, CSEError, MQTTCSEClient


def main():
    suffix = uuid.uuid4().hex[:10]
    name = "mqtt-" + suffix
    actor = "Cmqtt" + suffix
    root = "cse-secure/" + name
    ca = ROOT / ".runtime/pki/ca.crt"
    trace = ROOT / ".runtime" / f"mqtt-trace-{suffix}.jsonl"
    evidence = {"kind": "actual_native_oneM2M_MQTT_binding", "physical_data": "simulated", "cse": "ACME 2026.5.3", "broker": "aMQTT 0.12.2", "server_certificate_verification": True, "checks": {}, "limitations": ["Broker is loopback-only with anonymous lab clients; no production AE credential/topic binding is claimed.", "The CSE's HTTP listener does not require client certificates. Client-side server certificate validation remains enabled."]}
    with CSEClient("https://127.0.0.1:8443", ca_file=ca) as http:
        ae = http.create("cse-secure", 2, {"m2m:ae": {"rn": name, "api": "N.opensoom.mqtt", "rr": True, "srv": ["4"]}}, origin=actor)
        try:
            http.create(root, 3, {"m2m:cnt": {"rn": "observations"}}, origin=actor)
            with MQTTCSEClient("127.0.0.1", "/opensoom-secure", actor, ca, trace_path=trace) as mqtt:
                result = mqtt.create(root + "/observations", 4, {"m2m:cin": {"con": {"pm25_ug_m3": 24, "co2_ppm": 820, "simulated": True}, "cnf": "application/json:0"}})
                assert result["rsc"] == 2001
                evidence["checks"]["native_mqtt_create"] = result
                read = http.retrieve(root + "/observations/la", origin=actor)
                assert read["body"]["m2m:cin"]["con"]["pm25_ug_m3"] == 24
                assert read["body"]["m2m:cin"]["ri"] == result["body"]["m2m:cin"]["ri"]
                evidence["checks"]["https_same_resource"] = read
                denied = None
                try:
                    mqtt.create(root + "/observations", 4, {"m2m:cin": {"con": {"simulated": True}}}, origin="CNotThisDevice")
                except CSEError as error:
                    denied = error.result
                assert denied and denied["rsc"] == 4103, denied
                evidence["checks"]["native_mqtt_denial"] = denied
                evidence["request_topic"] = mqtt.request_topic
                evidence["response_topic"] = mqtt.response_topic
        finally:
            http.delete(root)
    for port, protocol in ((8443, "HTTPS"), (8883, "MQTT_TLS")):
        rejected = False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
                with ssl.create_default_context().wrap_socket(sock, server_hostname="localhost"):
                    pass
        except ssl.SSLCertVerificationError:
            rejected = True
        assert rejected, "Untrusted development certificate should be rejected"
        with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
            with ssl.create_default_context(cafile=str(ca)).wrap_socket(sock, server_hostname="localhost") as tls:
                evidence["checks"][protocol + "_tls"] = {"version": tls.version(), "cipher": tls.cipher()[0], "untrusted_certificate_rejected": rejected}
    evidence["trace_sha256"] = hashlib.sha256(trace.read_bytes()).hexdigest()
    evidence["native_request_response_trace"] = [json.loads(line) for line in trace.read_text().splitlines()]
    evidence["result"] = "PASS_NATIVE_MQTT_TLS_AND_HTTPS"
    path = ROOT / "evidence/runtime/cse-mqtt-tls-smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"result": evidence["result"], "evidence": str(path.relative_to(ROOT))}))


if __name__ == "__main__":
    main()
