#!/usr/bin/env python3
"""Bounded actual-service acceptance; all physical equipment is simulated.

Run after restarting the service from the intended source checkpoint. This
script changes only the selected facility's scenario and temporarily removes
its operator's read access to one observation container, restoring it in finally.
No live model calls, credential output, gate decisions, or external submission.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import httpx
from opensoom.onem2m import CSEClient, CSEError


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def hashes():
    files = [ROOT / "src/opensoom" / (name + ".py") for name in ("core", "app", "models", "adapters", "policy", "store", "onem2m")]
    files += [Path(__file__), *sorted((ROOT / "profiles").glob("*.json")), *sorted((ROOT / "schemas").glob("*.json"))]
    if (ROOT / "config/facilities.json").exists():
        files.append(ROOT / "config/facilities.json")
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def trace_since(path, offset):
    if not path.exists():
        return []
    with path.open() as stream:
        stream.seek(offset)
        result = []
        for line in stream:
            try:
                result.append(json.loads(line))
            except ValueError:
                continue
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facility", choices=["food-a", "learning-b"], default="learning-b")
    parser.add_argument("--evidence", default="evidence/application/acceptance.json")
    args = parser.parse_args()
    fid = args.facility
    runtime = ROOT / ".runtime"
    credentials = json.loads((runtime / "service-credentials.json").read_text())
    suffix = uuid.uuid4().hex[:10]
    started = time.monotonic()
    overall_deadline = started + 180
    offsets = {name: (runtime / name).stat().st_size if (runtime / name).exists() else 0 for name in ("cse-requests.jsonl", "mqtt-requests.jsonl")}
    evidence = {"kind": "actual_service_and_CSE_acceptance", "acceptance_id": "acceptance-" + suffix, "started_at": now(), "mutated_facility": fid, "physical_devices": "simulated", "live_LLM_used": False, "source_sha256_before": hashes(), "scenarios": {}, "checks": {}, "limitations": ["Deterministic API scenario execution is not live-LLM evidence.", "HTTP8090 is a trusted loopback application; its CSE requests use the separate HTTPS/MQTT TLS profile.", "Native group member denial aborts the ACME aggregate; individual fallback reads are labeled separately.", "One field of the SDT model is exercised: integer PM2.5 µg/m³. CO2 ppm is not mapped to mg/m³."]}
    api = httpx.Client(base_url="http://127.0.0.1:8090", timeout=8, trust_env=False, headers={"Authorization": "Bearer " + credentials["operator_token"]})
    cse = CSEClient("https://127.0.0.1:8443", ca_file=runtime / "pki/ca.crt", timeout=8)
    base = "cse-secure/opensoom"

    def call(method, path, body=None, *, run_id=None, expected=200):
        if time.monotonic() > overall_deadline:
            raise TimeoutError("Acceptance exceeded its 180-second total limit")
        headers = {"X-OpenSoom-Run-ID": run_id} if run_id else {}
        response = api.request(method, path, json=body, headers=headers)
        assert response.status_code == expected, {"path": path, "status": response.status_code, "response": response.json()}
        return response.json()

    def tool(name, arguments, run_id=None, expected=200):
        return call("POST", "/api/tools/" + name, {"arguments": arguments}, run_id=run_id, expected=expected)

    def wait(check, seconds):
        deadline = min(time.monotonic() + seconds, overall_deadline)
        while time.monotonic() < deadline:
            result = check()
            if result:
                return result
            time.sleep(0.25)
        raise TimeoutError("Expected application outcome did not arrive")

    def current_state(run_id):
        state = call("GET", "/api/state")
        return {"facility": next(item for item in state["facilities"] if item["id"] == fid), "commands": [item for item in state["commands"] if item.get("run_id") == run_id], "incidents": [item for item in state["incidents"] if item["facility_id"] == fid], "runtime": state["runtime"]}

    def expected_denial(path, origin, resource=None):
        try:
            if resource is None:
                cse.retrieve(path, origin=origin)
            else:
                cse.create(path, 4, resource, origin=origin)
        except CSEError as error:
            assert error.rsc == 4103
            return error.result
        raise AssertionError("An unauthorized CSE operation succeeded")

    try:
        doctor = tool("doctor", {})
        assert doctor["status"] == "ready" and doctor["cse"]["base"] == "cse-secure"
        evidence["checks"]["service_readiness"] = doctor
        discovery = tool("discover", {})
        by_id = {item["id"]: item for item in discovery["facilities"]}
        assert {"food-a", "learning-b"} <= set(by_id)
        assert by_id["food-a"]["profile"] != by_id["learning-b"]["profile"]
        assert all(item["rsc"] == 2000 and item["body"]["m2m:uril"] for item in discovery["cse_discovery"])
        evidence["checks"]["actual_native_discovery"] = discovery
        zone = by_id[fid]["zones"][0]["id"]
        command_ids = set()
        for scenario in ("normal", "exhaust_fault", "stale", "missing", "missing_ack", "no_recovery"):
            run = call("POST", "/api/demo/start", {"facility_id": fid, "scenario": scenario, "autorun": True})
            run_id = run["run_id"]
            def completed():
                result = call("GET", "/api/runs/" + run_id)
                return result if result["status"] == "completed" else None
            completed_run = wait(completed, 42 if scenario == "missing_ack" else 20)
            state = current_state(run_id)
            assert completed_run["outcome"] == "PASS_FIXTURE"
            row = {"run_id": run_id, "run": completed_run, "state": state}
            if scenario == "normal":
                assert state["facility"]["status"] == "nominal" and not state["commands"] and not state["incidents"]
            elif scenario in ("stale", "missing"):
                assert state["facility"]["status"] == scenario and not state["commands"]
                refusal = tool("request_action", {"facility_id": fid, "zone_id": zone, "action": "set_damper", "value": 100, "reason": "Acceptance checks refusal of unsupported control", "request_id": run_id + ":must-refuse"}, run_id, expected=409)
                assert refusal["detail"]["code"] == "evidence_not_current"
                assert not current_state(run_id)["commands"]
                assert any(item["status"] != "resolved" for item in state["incidents"])
                row["action_refusal"] = refusal
            else:
                assert len(state["commands"]) == 1
                command = state["commands"][0]
                command_ids.add(command["id"])
                verification = tool("verify_result", {"facility_id": fid, "command_id": command["id"]}, run_id)
                row["verification"] = verification
                if scenario == "exhaust_fault":
                    assert verification["complete"] and verification["outcome"] == "recovered" and command["ack"]
                    assert datetime.fromisoformat(verification["observations"]["airflow"]["observed_at"]) > datetime.fromisoformat(command["ack_at"])
                    assert all(item["status"] == "resolved" for item in state["incidents"])
                elif scenario == "missing_ack":
                    assert not command["ack"] and verification["status"] == "timed_out" and not verification["complete"]
                    assert verification["outcome"] == "unresolved"
                else:
                    assert command["ack"] and verification["status"] == "unresolved" and not verification["complete"]
                    assert command.get("unresolved_samples", 0) >= 2 and verification["outcome"] == "unresolved"
                if scenario != "exhaust_fault":
                    assert any(item["status"] != "resolved" for item in state["incidents"])
            evidence["scenarios"][scenario] = row
            print(json.dumps({"scenario": scenario, "run_id": run_id, "result": "PASS_ACTUAL_SERVICE_SCENARIO"}), flush=True)

        # Read both configured adapters from real CSE observations without changing food-a.
        reuse = []
        for facility_id in ("food-a", "learning-b"):
            item = by_id[facility_id]
            zid = item["zones"][0]["id"]
            result = cse.retrieve(f"{base}/facilities/{facility_id}/{zid}/observations/la", origin="Cosdiagnostic")
            observation = json.loads(result["body"]["m2m:cin"]["con"])
            assert observation["facility_id"] == facility_id and observation["source"] == "simulated"
            reuse.append({"facility_id": facility_id, "profile_id": item["profile"], "adapter": observation["adapter"], "actual_CSE_observation": result})
        assert {item["adapter"] for item in reuse} == {"vendor-a", "vendor-b"}
        evidence["checks"]["two_profiles_and_actual_adapter_observations"] = reuse
        grouped = tool("read_group", {"facility_id": fid})
        replies = grouped["group"]["body"]["m2m:agr"]["m2m:rsp"]
        assert grouped["status"] == "ok" and len(replies) == 3 and all(item["rsc"] == 2000 for item in replies)
        evidence["checks"]["native_product_group_success"] = grouped

        operator = cse.retrieve("cse-secure/os-operator")["body"]["m2m:ae"]["aei"]
        observer = cse.retrieve("cse-secure/os-observer")["body"]["m2m:ae"]["aei"]
        diagnostic = cse.retrieve("cse-secure/os-diagnostic")["body"]["m2m:ae"]["aei"]
        scope_path = f"{base}/facilities/learning-b/{by_id['learning-b']['zones'][0]['id']}"
        evidence["checks"]["registered_AE_ACP_denials"] = {"observer_AEI": observer, "diagnostic_AEI": diagnostic, "wrong_facility_read": expected_denial(scope_path + "/observations/la", observer), "diagnostic_command_write": expected_denial(scope_path + "/commands", diagnostic, {"m2m:cin": {"con": "unauthorized-acceptance-probe"}})}

        # Remove only this container's operator reader, preserving adapter/diagnosis.
        selected_zone = by_id[fid]["zones"][1]["id"]
        selected_path = f"{base}/facilities/{fid}/{selected_zone}/observations"
        container = cse.retrieve(selected_path)["body"]["m2m:cnt"]
        original_acpi = container["acpi"]
        original_policy = cse.retrieve(original_acpi[0])["body"]["m2m:acp"]
        rules = json.loads(json.dumps(original_policy["pv"]))
        for rule in rules["acr"]:
            rule["acor"] = [actor for actor in rule["acor"] if actor != operator]
        rules["acr"] = [rule for rule in rules["acr"] if rule["acor"]]
        temp_name = "acceptance-" + suffix
        temp_policy = cse.create("cse-secure", 1, {"m2m:acp": {"rn": temp_name, "pv": rules, "pvs": original_policy["pvs"]}})
        try:
            cse.update(selected_path, {"m2m:cnt": {"acpi": [temp_policy["body"]["m2m:acp"]["ri"]]}})
            partial = tool("read_group", {"facility_id": fid})
            assert partial["status"] == "group_not_confirmed" and partial["group_error"]["rsc"] == 4103
            codes = {item["zone_id"]: item["response"]["rsc"] for item in partial["individual_diagnostic_reads"]}
            assert codes[selected_zone] == 4103 and list(codes.values()).count(2000) == 2
            evidence["checks"]["native_group_member_denial_with_product_fallback"] = partial
        finally:
            cse.update(selected_path, {"m2m:cnt": {"acpi": original_acpi}})
            cse.delete("cse-secure/" + temp_name)
        assert tool("read_group", {"facility_id": fid})["status"] == "ok"

        sdt_discovery = cse.discover(base, {"ty": 28, "lbl": "facility:" + fid}, origin=operator)
        assert len(sdt_discovery["body"]["m2m:uril"]) == 3
        model_rows = []
        for zid in (item["id"] for item in by_id[fid]["zones"]):
            model = cse.retrieve(f"{base}/{fid}-{zid}-air", origin=operator)
            observation_result = cse.retrieve(f"{base}/facilities/{fid}/{zid}/observations/la", origin=operator)
            observation = json.loads(observation_result["body"]["m2m:cin"]["con"])
            attrs = model["body"]["cod:aiQSr"]
            assert attrs["cnd"] == "org.onem2m.common.moduleclass.airQualitySensor"
            assert isinstance(attrs["pm25"], int) and attrs["pm25"] == round(observation["pm25"])
            assert "co2" not in attrs
            model_rows.append({"zone_id": zid, "source_pm25_ug_m3": observation["pm25"], "model": model, "source_observation_rqi": observation_result["rqi"], "co2_ppm_not_mapped": True})
        evidence["checks"]["actual_SDT_discovery_and_pm25_mapping"] = {"specification": "oneM2M TS-0023 v5.6.0 5.3.1.6", "source": "https://specifications.onem2m.org/ts/ts-0023/v5.6.0/5.3/#5316-airqualitysensor", "rounding": "Python round to nearest integer, ties to even; full precision retained in observations", "discovery": sdt_discovery, "models": model_rows, "application_read_evidence": tool("read_evidence", {"facility_id": fid})["standard_models"]}

        protocol = {}
        for event in trace_since(runtime / "mqtt-requests.jsonl", offsets["mqtt-requests.jsonl"]):
            request = event.get("request", {})
            target = request.get("to", "")
            if event.get("response", {}).get("rsc", 0) not in (2000, 2001, 2004):
                continue
            if "/" + fid + "/" in target and target.endswith("/observations"):
                protocol.setdefault("native_MQTT_observation", event)
            if target.endswith("/acks"):
                raw = request.get("pc", {}).get("m2m:cin", {}).get("con", "{}")
                if json.loads(raw).get("command_id") in command_ids:
                    protocol.setdefault("native_MQTT_ACK", event)
            if "cod:aiQSr" in request.get("pc", {}) and fid in target:
                protocol.setdefault("native_MQTT_SDT_update", event)
        for event in trace_since(runtime / "cse-requests.jsonl", offsets["cse-requests.jsonl"]):
            if event.get("method") == "POST" and event.get("path", "").endswith("/commands"):
                raw = event.get("request", {}).get("m2m:cin", {}).get("con", "{}")
                if json.loads(raw).get("id") in command_ids:
                    protocol.setdefault("HTTPS_command", event)
        assert set(protocol) == {"native_MQTT_observation", "native_MQTT_ACK", "native_MQTT_SDT_update", "HTTPS_command"}, list(protocol)
        evidence["checks"]["actual_product_mixed_protocol_trace"] = protocol
        evidence["result"] = "PASS_ACTUAL_APPLICATION_ACCEPTANCE"
    except Exception as error:
        evidence.update(result="FAIL_ACTUAL_APPLICATION_ACCEPTANCE", error={"type": type(error).__name__, "message": str(error)[:2000]})
        raise
    finally:
        evidence["completed_at"] = now()
        evidence["elapsed_seconds"] = round(time.monotonic() - started, 3)
        evidence["source_sha256_after"] = hashes()
        evidence["source_changed_during_run"] = evidence["source_sha256_before"] != evidence["source_sha256_after"]
        if evidence["source_changed_during_run"]:
            evidence["result"] = "FAIL_SOURCE_CHANGED_DURING_ACCEPTANCE"
        destination = ROOT / args.evidence
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
        cse.close()
        api.close()
    assert evidence["result"] == "PASS_ACTUAL_APPLICATION_ACCEPTANCE", evidence["result"]
    print(json.dumps({"result": evidence["result"], "evidence": str(destination.relative_to(ROOT)), "elapsed_seconds": evidence["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
