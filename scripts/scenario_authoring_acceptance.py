"""Rehearse saved virtual trials across a real service restart on a dedicated CSE."""
import argparse
import json
from pathlib import Path
import uuid

from opensoom.mcp_server import ServiceError, ServiceProxy
from opensoom.onem2m import CSEClient
from opensoom.store import Store


def inspect_zones(cse, facility, observer):
    states = {}
    for zone in facility["zones"]:
        states[zone["id"]] = {}
        for stream in ("commands", "observations", "acks"):
            reply = cse.retrieve(zone["path"] + "/" + stream, origin=observer)
            container = reply["body"]["m2m:cnt"]
            states[zone["id"]][stream] = {"st": container["st"], "cni": container["cni"], "rqi": reply["rqi"]}
    return states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "replay"))
    parser.add_argument("--service", required=True)
    parser.add_argument("--cse", required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    store = Store(options.runtime / "operations.sqlite")
    credentials = json.loads((options.runtime / "service-credentials.json").read_text())
    service = ServiceProxy(options.service, token=credentials["operator_token"])
    facility = store.get("facilities", "learning-b")
    cse = CSEClient(options.cse)
    observer = store.get("config", "identities")["diagnostic"]
    fid, zone = facility["id"], facility["zones"][-1]["id"]
    assert zone != facility["zones"][0]["id"]
    before = inspect_zones(cse, facility, observer)
    if options.stage == "prepare":
        result = {"kind": "real CSE; simulated physical input/actuator", "facility": fid, "zone": zone}
        draft = {"facility_id": fid, "scenario_id": "trial-" + uuid.uuid4().hex[:10], "zone_id": zone,
                 "observation_age_seconds": 90, "airflow_m3_h": 347, "damper_percent": 89, "expected_result": "command_refused"}
        assert not any(item["scenario_id"] == draft["scenario_id"] for item in store.list("scenario_definitions"))
        invalid = []
        for changes, expected in [({"zone_id": "unknown"}, "unknown_zone"), ({"airflow_m3_h": "347 CFM"}, "invalid_arguments"),
                                  ({"damper_percent": 101}, "invalid_arguments"), ({"unit": "CFM"}, "invalid_arguments")]:
            try:
                service.call("save_scenario", {**draft, **changes})
            except ServiceError as error:
                assert error.result["code"] == expected, error.result
                invalid.append({"changes": changes, "error": expected})
            else:
                raise AssertionError("Invalid draft accepted")
        saved = service.call("save_scenario", draft)
        result.update(definition=saved, invalid_inputs=invalid)
    else:
        result = json.loads(options.output.read_text())
        saved = result["definition"]
        assert store.get("scenario_definitions", saved["version"])["version"] == saved["version"]

    execution_args = {"facility_id": fid, "scenario_id": saved["scenario_id"], "version": saved["version"], "request_id": uuid.uuid4().hex}
    trial = service.call("run_scenario", execution_args)
    repeat = service.call("run_scenario", execution_args)
    assert repeat["execution_id"] == trial["execution_id"]
    read = service.call("read_scenario_run", {"facility_id": fid, "execution_id": trial["execution_id"]})
    assert read["assertion_passed"] and read["command_state_tag_delta"] == 0, read
    assert read["readback"]["cin"] == trial["cin"] and read["readback"]["airflow_m3_h"] == saved["airflow_m3_h"]
    after = inspect_zones(cse, facility, observer)
    for zid in before:
        for stream in before[zid]:
            assert after[zid][stream]["st"] - before[zid][stream]["st"] == int(zid == zone and stream == "observations")
    result[options.stage] = {"execution": read, "before": before, "after": after, "retry_execution_id": repeat["execution_id"]}
    if options.stage == "replay":
        assert result["prepare"]["execution"]["execution_id"] != read["execution_id"]
        assert result["prepare"]["execution"]["version"] == read["version"]
        fresh_args = {key: saved[key] for key in ("facility_id", "scenario_id", "zone_id", "observation_age_seconds", "airflow_m3_h", "damper_percent", "expected_result")}
        fresh = service.call("save_scenario", {**fresh_args, "observation_age_seconds": 0, "expected_result": "device_acknowledged"})
        fresh_trial = service.call("run_scenario", {**execution_args, "version": fresh["version"], "request_id": uuid.uuid4().hex})
        assert fresh_trial["assertion_passed"] and fresh_trial["command_state_tag_delta"] == 1, fresh_trial
        assert fresh_trial["command"]["ack_rqi"]
        result["fresh_contrast"] = fresh_trial
        mismatch = service.call("save_scenario", {**fresh_args, "expected_result": "device_acknowledged"})
        observed = service.call("run_scenario", {**execution_args, "version": mismatch["version"], "request_id": uuid.uuid4().hex})
        assert not observed["assertion_passed"] and observed["actual_result"] == "command_refused"
        result["incorrect_expectation"] = observed
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"{options.stage} verified {saved['scenario_id']} {trial['execution_id']}")


if __name__ == "__main__":
    main()
