#!/usr/bin/env python3
"""Replay the three dashboard trials and audit their outcomes against independent CSE reads."""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from math import isclose
from pathlib import Path
import subprocess
import sys
import tempfile

import httpx

from cse_multiapp_smoke import ROOT, child_env, start_cse, stop_process
from maintenance_demo import available_port, until
from opensoom.onem2m import CSEClient
from opensoom import ventilation_trials as trials


def seconds(start, end):
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


def read_cin(cse, path):
    result = cse.retrieve(path)
    resource = result["body"]["m2m:cin"]
    assert result["rsc"] == 2000
    record = {"cin_path": path, "cin_ri": resource["ri"], "state_tag": resource["st"], "read_rqi": result["rqi"]}
    return record, json.loads(resource["con"])


def measured_window(cse, outcome):
    baseline, latest = outcome["baseline"], outcome["latest"]
    container = baseline["cin_path"].rsplit("/", 1)[0]
    first = read_cin(cse, baseline["cin_path"])[0]["state_tag"]
    final = read_cin(cse, latest["cin_path"])[0]["state_tag"]
    uris = cse.discover(container, {"ty": 4, "drt": 1, "lvl": 1})["body"]["m2m:uril"]
    rows = []
    for uri in uris:
        path = container + "/" + uri.rsplit("/", 1)[-1]
        record, value = read_cin(cse, path)
        if first <= record["state_tag"] <= final:
            rows.append({**record, **{key: value[key] for key in ("observed_at", "pm25", "co2", "airflow")}})
    rows.sort(key=lambda row: row["state_tag"])
    assert [row["state_tag"] for row in rows] == list(range(first, final + 1))
    assert (rows[0]["cin_ri"], rows[-1]["cin_ri"]) == (baseline["cin_ri"], latest["cin_ri"])
    return rows


def check_outcome(outcome, rows, scenario, acknowledged_at):
    baseline, final = rows[0], rows[-1]
    assert outcome["ack_at"] == acknowledged_at
    assert seconds(baseline["observed_at"], acknowledged_at) >= 0
    assert (baseline["pm25"], baseline["co2"]) == (75, 1500)
    assert outcome["targets"]["pm25"] == 45 and outcome["targets"]["co2"] == 1200
    for key in ("pm25", "co2"):
        assert outcome["baseline"][key] == baseline[key] and outcome["latest"][key] == final[key]
        decrease = baseline[key] - final[key]
        assert isclose(outcome["change"][key]["decrease"], decrease, abs_tol=.01)
        assert isclose(outcome["change"][key]["percent"], 100 * decrease / baseline[key], abs_tol=.11)
    after = [row for row in rows if seconds(acknowledged_at, row["observed_at"]) > 0]
    assert after and all(isclose(row["airflow"], 1035) for row in after)
    in_target = [row for row in after if row["pm25"] <= 45 and row["co2"] <= 1200]
    assert final["co2"] == 720
    if scenario == trials.PERSISTENT:
        assert final["pm25"] == 60 and outcome["status"] == "outside_target"
        assert not in_target and outcome["first_target_at"] is None and outcome["time_to_target_seconds"] is None
        assert outcome["hold_seconds"] is None
        return
    first_target = in_target[0]
    assert outcome["first_target_at"] == first_target["observed_at"]
    assert outcome["first_target_sample"]["cin_ri"] == first_target["cin_ri"]
    assert isclose(outcome["time_to_target_seconds"], seconds(acknowledged_at, first_target["observed_at"]), abs_tol=.001)
    start, end = in_target[0]["observed_at"], in_target[-1]["observed_at"]
    assert seconds(start, end) > 0
    if scenario == trials.RECOVERY:
        assert final["pm25"] == 15 and outcome["status"] == "in_target"
        assert isclose(outcome["hold_seconds"], seconds(start, end), abs_tol=.001)
    else:
        assert final["pm25"] == 60 and outcome["status"] == "outside_target"
        assert outcome["hold_seconds"] is None
        assert isclose(outcome["last_hold_seconds"], seconds(start, end), abs_tol=.001)


def capture_case(api, cse, scenario):
    started = api.post("/api/demo/start", json={"facility_id": "food-a", "scenario": scenario, "autorun": True})
    run_id = started.raise_for_status().json()["run_id"]

    def complete():
        item = api.get("/api/runs/" + run_id).raise_for_status().json()
        return item if item["status"] == "completed" else None

    run = until("Observed final trial phase for " + scenario, complete, timeout=55)
    state = api.get("/api/state").raise_for_status().json()
    actions = [c for c in state["commands"] if c["run_id"] == run_id and c["action"] == "set_damper"]
    assert len(actions) == 1
    command = actions[0]
    outcome = command["air_quality_outcome"]
    native_cmd, command_data = read_cin(cse, command["cse_resource_id"])
    native_ack, ack_data = read_cin(cse, command["ack_source"]["cin_path"])
    assert command_data["run_id"] == run_id and command_data["id"] == ack_data["command_id"] == command["id"]
    assert native_ack["cin_ri"] == command["ack_source"]["cin_ri"]
    rows = measured_window(cse, outcome)
    check_outcome(outcome, rows, scenario, ack_data["ack_at"])
    return {"run_id": run_id, "scenario": scenario, "command_id": command["id"],
            "expected_behavior": run["expected_behavior"], "facility_id": "food-a", "zone_id": "cook",
            "command": {**native_cmd, "created_at": command_data["created_at"], "opening_pct": command_data["value"]},
            "ack": {**native_ack, "ack_at": ack_data["ack_at"], "opening_pct": ack_data["value"]},
            "outcome": outcome, "samples": rows}


def source_hashes():
    files = ["src/opensoom/ventilation_trials.py", "src/opensoom/core.py", "src/opensoom/app.py",
             "src/opensoom/policy.py", "scenarios/scenarios.json", "profiles/food-production.json",
             "scripts/air_quality_outcomes.py"]
    files.extend(str(p.relative_to(ROOT)) for p in sorted((ROOT/"src/opensoom").glob("*outcome*.py")))
    return {file: hashlib.sha256((ROOT / file).read_bytes()).hexdigest() for file in files}


def run():
    before = source_hashes()
    with ExitStack() as stack:
        folder = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="opensoom-air-outcome-")))
        cse_folder = folder / "cse"
        cse_folder.mkdir()
        processes = []
        stack.callback(lambda: [stop_process(p) for p in reversed(processes)])
        cse_url, _, version = start_cse(cse_folder, processes)
        port = available_port()
        api_url = f"http://127.0.0.1:{port}"
        env = {**child_env(), "OPENSOOM_CSE_URL": cse_url, "OPENSOOM_CSE_BASE": "cse-multiapp",
               "OPENSOOM_RUNTIME_DIR": str(folder/"operations"), "OPENSOOM_FACILITY_IDS": "food-a",
               "OPENSOOM_NOTIFY_URL": api_url + "/api/notify"}
        log = stack.enter_context((folder/"operations.log").open("w"))
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "opensoom.app:app", "--host", "127.0.0.1",
                                   "--port", str(port), "--no-access-log"], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                  stdout=log, stderr=subprocess.STDOUT)
        processes.append(server)
        api = stack.enter_context(httpx.Client(base_url=api_url, timeout=15, trust_env=False))
        until("Ordinary operations API", lambda: api.get("/api/health").raise_for_status().json()["cse_connected"])
        credentials = json.loads((folder/"operations/service-credentials.json").read_text())
        api.headers["Authorization"] = "Bearer " + credentials["operator_token"]
        with CSEClient(cse_url) as admin:
            operator = admin.retrieve("cse-multiapp/os-operator")["body"]["m2m:ae"]["aei"]
        cse = stack.enter_context(CSEClient(cse_url, operator))
        cases = {}
        for scenario in trials.SCENARIOS:
            print("Replaying", scenario, flush=True)
            cases[scenario] = capture_case(api, cse, scenario)
        assert before == source_hashes(), "Product changed while capturing the three runs; replay on stable source."
    return {"status": "passed", "captured_at": datetime.now(timezone.utc).isoformat(), "acme_version": version,
            "scope": "The normal operator API starts three trials with a virtual device sampled at real elapsed times. "
                     "Actual local ACME stores the command, device ACK and sensor CINs. Pollutant reductions describe "
                     "these simulated observations. Durations span observed acquisition times, and do not establish "
                     "physical exposure, causal effects or conditions between measurements.",
            "units": {"pm25": "µg/m³", "co2": "ppm", "airflow": "m³/h", "time": "seconds"},
            "cases": cases, "source_sha256": before}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: [v["outcome"]["time_to_target_seconds"], v["outcome"]["hold_seconds"],
                            v["outcome"]["last_hold_seconds"]] for key, v in report["cases"].items()}))
