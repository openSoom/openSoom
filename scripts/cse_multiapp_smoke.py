#!/usr/bin/env python3
"""Run independent operations/maintenance apps against an isolated actual CSE.

No existing service, configured port, database or process record is modified.
All physical devices and measurements are simulated; no LLM API is called.
"""
from __future__ import annotations

import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from opensoom.onem2m import CSEClient, CSEError


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def hashes():
    paths = [Path(__file__).resolve(), ROOT / "src/opensoom/multiapp.py", ROOT / "src/opensoom/onem2m.py",
             ROOT / "src/opensoom/models.py", ROOT / "src/opensoom/policy.py", ROOT / "profiles/food-production.json",
             ROOT / "deploy/acme-single.ini", ROOT / "deploy/cse-requirements.txt"]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def existing_process_records():
    paths = [ROOT / ".runtime/service-process.json", ROOT / ".runtime/mqtt/process.json",
             ROOT / ".runtime/product-topology/processes.json", *sorted((ROOT / ".runtime").glob("cse-*/process.json"))]
    records = {}
    for path in paths:
        if not path.exists():
            continue
        raw = path.read_bytes()
        value = json.loads(raw)
        pids = [record["pid"] for record in (value if isinstance(value, list) else [value])]
        alive = {}
        for pid in pids:
            try:
                os.kill(pid, 0)
                alive[str(pid)] = True
            except ProcessLookupError:
                alive[str(pid)] = False
        records[str(path.relative_to(ROOT))] = {"sha256": hashlib.sha256(raw).hexdigest(), "pids_alive": alive}
    return records


def wait_for(check, *, processes=(), seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("Owned child exited before the expected state; inspect the private runtime log")
        try:
            value = check()
            if value:
                return value
        except (CSEError, OSError, ValueError):
            pass
        time.sleep(0.05)
    raise TimeoutError("Bounded multi-application wait expired")


def read_state(path):
    return json.loads(path.read_text()) if path.exists() else {}


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    return process.returncode


def child_env():
    # These deterministic workers have no model/network credential requirement.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("OPENSOOM_") and not any(word in key.upper() for word in ("API_KEY", "TOKEN", "PASSWORD", "SECRET"))}
    env["PYTHONPATH"] = str(ROOT / "src")
    return env


def start_cse(folder, processes):
    python = ROOT / "tmp/runtime/cse-venv/bin/python"
    if not python.exists():
        raise RuntimeError("Pinned CSE runtime missing. Run: python3 scripts/cse_runtime.py install")
    version = subprocess.run([str(python), "-c", 'import importlib.metadata; print(importlib.metadata.version("acmecse"))'],
                             cwd=ROOT, env=child_env(), capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    if version != "2026.5.3":
        raise RuntimeError("CSE runtime must match pinned ACME 2026.5.3; rerun scripts/cse_runtime.py install")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read(ROOT / "deploy/acme-single.ini")
    config["basic.config"].update(cseName="cse-multiapp", cseID="opensoom-multiapp", httpPort=str(port), secret=secrets.token_urlsafe(32))
    config_path = folder / "acme.ini"
    with config_path.open("w") as stream:
        config.write(stream)
    config_path.chmod(0o600)
    with (folder / "cse.log").open("w") as log:
        process = subprocess.Popen([str(python), "-m", "acmecse", "--base-directory", str(folder), "--headless", "--db-reset"],
                                   cwd=ROOT, env=child_env(), stdin=subprocess.DEVNULL, stdout=log, stderr=log)
    processes.append(process)
    url = f"http://127.0.0.1:{port}"
    client = CSEClient(url, timeout=1)
    wait_for(lambda: client.retrieve("cse-multiapp"), processes=[process], seconds=45)
    client.close()
    return url, process, version


def provision(client, scenario, event_id):
    base = "cse-multiapp"
    namespace = "multiapp-" + event_id
    root = base + "/" + namespace
    identities, registrations = {}, {}
    for role in ("operations", "maintenance", "device", "outsider"):
        result = client.create(base, 2, {"m2m:ae": {"rn": namespace + "-" + role, "api": "N.org.opensoom." + role,
                                                  "rr": False, "srv": ["4"]}}, origin="C" + role + event_id.replace("-", ""))
        identities[role] = result["body"]["m2m:ae"]["aei"]
        registrations[role] = result
    client.create(base, 2, {"m2m:ae": {"rn": namespace, "api": "N.org.opensoom.multiapp.provisioning", "rr": False, "srv": ["4"]}},
                  origin="Cprovision" + event_id.replace("-", ""))
    admin = {"acor": ["CAdmin"], "acop": 63}
    readers = {"acor": [identities[role] for role in ("operations", "maintenance", "device")], "acop": 34}
    policies, policy_results = {}, {}
    for kind, writer in (("structure", None), ("observations", "device"), ("commands", "operations"),
                         ("acks", "device"), ("operations_reports", "operations"), ("work_orders", "maintenance")):
        rules = [admin, readers]
        if writer:
            rules.append({"acor": [identities[writer]], "acop": 1, "acod": [{"chty": [4]}]})
        result = client.create(root, 1, {"m2m:acp": {"rn": "policy-" + kind, "pv": {"acr": rules}, "pvs": {"acr": [admin]}}})
        policies[kind] = result["body"]["m2m:acp"]["ri"]
        policy_results[kind] = result
    client.update(root, {"m2m:ae": {"acpi": [policies["structure"]]}}, origin="Cprovision" + event_id.replace("-", ""))
    paths, container_ids = {}, {}
    for name in ("observations_cook", "observations_wash", "commands", "acks", "operations_reports", "work_orders"):
        kind = "observations" if name.startswith("observations_") else name
        result = client.create(root, 3, {"m2m:cnt": {"rn": name, "mni": 100, "acpi": [policies[kind]],
                                                   "lbl": ["opensoom:multiapp", "stream:" + name, "event:" + event_id]}})
        paths[name], container_ids[name] = root + "/" + name, result["body"]["m2m:cnt"]["ri"]
    group = client.create(root, 9, {"m2m:grp": {"rn": "zone-observations", "mt": 3, "mnm": 2,
                                              "mid": [container_ids["observations_cook"], container_ids["observations_wash"]],
                                              "acpi": [policies["structure"]]}})
    paths["observation_group"] = root + "/zone-observations"
    profile = json.loads((ROOT / "profiles/food-production.json").read_text())
    cfg = {"schema_version": 1, "scenario": scenario, "event_id": event_id, "root": root,
           "facility_id": "food-a", "target_zone": "cook", "asset_id": "cook-exhaust-01",
           "simulation_only": True, "controls_enabled": True, "ack_wait_seconds": 3,
           "profile": profile, "zones": {zone["id"]: zone for zone in profile["zones"] if zone["id"] in ("cook", "wash")},
           "paths": paths, "container_ids": container_ids}
    return cfg, {"ae_registrations": registrations, "role_origins": identities, "access_policies": policy_results, "native_group": group}


def start_app(role, cfg, identity, folder, processes):
    path = folder / role
    path.mkdir()
    config = {**cfg, "origin": identity, "start_signal": str(folder / "start-device")}
    (path / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    state, trace = path / "state.json", path / "requests.jsonl"
    with (path / "process.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "opensoom.multiapp", "--role", role, "--config", str(path / "config.json"),
                                    "--state", str(state), "--trace", str(trace)], cwd=ROOT, env=child_env(), stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log)
    processes.append(process)
    wait_for(lambda: read_state(state).get("endpoint"), processes=[process])
    return {"process": process, "state": state, "trace": trace}


def subscribe(client, cfg, stream, app, name):
    endpoint = read_state(app["state"])["endpoint"]
    return client.create(cfg["paths"][stream], 23, {"m2m:sub": {"rn": name, "nu": [endpoint], "enc": {"net": [3], "chty": [4]}, "nct": 1}})


def denied(action):
    try:
        action()
    except CSEError as error:
        if error.rsc == 4103:
            return error.result
        raise
    raise AssertionError("Expected unprivileged CSE ACP denial")


def run_scenario(client, url, runtime, destination, run_id, scenario, owned):
    event_id = run_id + "-" + scenario.replace("_", "-")
    folder = runtime / scenario
    folder.mkdir()
    cfg, evidence = provision(client, scenario, event_id)
    cfg["url"] = url
    evidence.update(event_id=event_id, scenario=scenario, started_at=now())
    apps = {}
    try:
        for role in ("operations", "maintenance"):
            apps[role] = start_app(role, cfg, evidence["role_origins"][role], folder, owned)
        subscriptions = {
            "operations_observation": subscribe(client, cfg, "observations_cook", apps["operations"], "operations-watch"),
            "operations_ack": subscribe(client, cfg, "acks", apps["operations"], "ack-watch"),
            "maintenance_observation": subscribe(client, cfg, "observations_cook", apps["maintenance"], "maintenance-watch"),
        }
        apps["device"] = start_app("device", cfg, evidence["role_origins"]["device"], folder, owned)
        subscriptions["device_command"] = subscribe(client, cfg, "commands", apps["device"], "device-watch")
        evidence["subscriptions"] = subscriptions
        (folder / "start-device").touch()
        expected = {"recovery": "verified_recovery", "missing_ack": "ack_timed_out", "no_recovery": "unresolved_after_ack"}[scenario]
        def finished():
            states = {role: read_state(app["state"]) for role, app in apps.items()}
            maintenance = states["maintenance"]
            return states if states["operations"].get("status") == expected and maintenance.get("work_order_id") and (
                scenario != "recovery" or maintenance.get("status") == "observations_recovered_inspection_pending") else None
        states = wait_for(finished, processes=[app["process"] for app in apps.values()], seconds=20)
        assert all(not state["errors"] for state in states.values()), {role: state["errors"] for role, state in states.items()}
        operations, maintenance = states["operations"], states["maintenance"]
        assert operations["ae_origin"] != maintenance["ae_origin"]
        first_op, first_maint = operations["transitions"][0], maintenance["transitions"][0]
        common_ri = first_op["source"]["body"]["m2m:cin"]["ri"]
        assert common_ri == first_maint["source"]["body"]["m2m:cin"]["ri"]
        assert first_op["source"]["rqi"] != first_maint["source"]["rqi"]
        maintenance_actor = evidence["role_origins"]["maintenance"]
        evidence["access_checks"] = {
            "maintenance_control_denied": denied(lambda: client.create(cfg["paths"]["commands"], 4, {"m2m:cin": {"con": "forbidden"}}, origin=maintenance_actor)),
            "maintenance_cannot_forge_observation": denied(lambda: client.create(cfg["paths"]["observations_cook"], 4, {"m2m:cin": {"con": "forbidden"}}, origin=maintenance_actor)),
            "outsider_observation_denied": denied(lambda: client.retrieve(cfg["paths"]["observations_cook"] + "/la", origin=evidence["role_origins"]["outsider"])),
            "operations_cannot_write_work_order": denied(lambda: client.create(cfg["paths"]["work_orders"], 4, {"m2m:cin": {"con": "forbidden"}}, origin=evidence["role_origins"]["operations"])),
            "maintenance_cannot_write_operations_report": denied(lambda: client.create(cfg["paths"]["operations_reports"], 4, {"m2m:cin": {"con": "forbidden"}}, origin=maintenance_actor)),
            "device_cannot_register_subscription": denied(lambda: client.create(cfg["paths"]["observations_cook"], 23, {"m2m:sub": {"rn": "forbidden", "nu": ["http://127.0.0.1:1/unused"], "enc": {"net": [3]}}}, origin=evidence["role_origins"]["device"])),
        }
        evidence["independent_CSE_readback"] = {
            "operations_report": client.retrieve(cfg["paths"]["operations_reports"] + "/la", origin=evidence["role_origins"]["operations"]),
            "maintenance_work_order": client.retrieve(cfg["paths"]["work_orders"] + "/la", origin=maintenance_actor),
            "command_count": client.retrieve(cfg["paths"]["commands"], origin=evidence["role_origins"]["operations"]),
            "ack_count": client.retrieve(cfg["paths"]["acks"], origin=evidence["role_origins"]["operations"]),
        }
        assert content(evidence["independent_CSE_readback"]["operations_report"])["status"] == expected
        assert content(evidence["independent_CSE_readback"]["maintenance_work_order"])["work_order_id"] == maintenance["work_order_id"]
        assert evidence["independent_CSE_readback"]["command_count"]["body"]["m2m:cnt"]["cni"] == 1
        assert evidence["independent_CSE_readback"]["ack_count"]["body"]["m2m:cnt"]["cni"] == (0 if scenario == "missing_ack" else 1)
        evidence["same_source_event"] = {"event_id": event_id, "source_observation_ri": common_ri,
                                         "operations_read_rqi": first_op["source"]["rqi"], "maintenance_read_rqi": first_maint["source"]["rqi"]}
        evidence["applications"] = {role: {"pid": app["process"].pid, "module": "opensoom.multiapp", "role": role,
                                          "ae_origin": states[role]["ae_origin"], "state_path": f"{scenario}/{role}-state.json",
                                          "request_trace": f"{scenario}/{role}-requests.jsonl"} for role, app in apps.items()}
        assert len({entry["pid"] for entry in evidence["applications"].values()}) == 3
        evidence["result"] = "PASS_INDEPENDENT_APPLICATIONS_" + scenario.upper()
    finally:
        for role, app in apps.items():
            stop_process(app["process"])
            out = destination / scenario
            out.mkdir(parents=True, exist_ok=True)
            if app["state"].exists():
                (out / (role + "-state.json")).write_bytes(app["state"].read_bytes())
            if app["trace"].exists():
                trace = app["trace"].read_bytes()
                requests = [json.loads(line) for line in trace.splitlines()]
                assert requests and all(request["origin"] == evidence["role_origins"][role] for request in requests)
                (out / (role + "-requests.jsonl")).write_bytes(trace)
        evidence["completed_at"] = now()
        (destination / scenario / "result.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


def content(result):
    value = result["body"]["m2m:cin"]["con"]
    return json.loads(value) if isinstance(value, str) else value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=ROOT / "evidence/runtime/multiapp")
    args = parser.parse_args()
    destination = args.evidence.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    (ROOT / ".runtime").mkdir(exist_ok=True)
    runtime = Path(tempfile.mkdtemp(prefix="multiapp-", dir=ROOT / ".runtime"))
    runtime.chmod(0o700)
    run_id = "ma-" + secrets.token_hex(5)
    processes, client = [], None
    evidence = {"run_id": run_id, "started_at": now(), "kind": "actual_CSE_independent_application_processes",
                "cse": "ACME 2026.5.3", "physical_devices": "simulated", "transport": "HTTP_loopback",
                "source_sha256_before": hashes(), "scenarios": {}, "result": "FAIL_INCOMPLETE",
                "existing_process_records_before": existing_process_records(),
                "limitations": ["Three application processes and one actual CSE run on one host; no MEC, handover or physical deployment claim.",
                                "AE originators and ACPs are exercised on trusted loopback; no cryptographic identity binding is claimed.",
                                "OneM2M subscriptions are provisioned by an administrator; workers use only their own assigned non-admin origins.",
                                "Facility-specific bundled simulation targets govern the virtual example; no ventilation safety or health outcome is established.",
                                "Maintenance work orders remain open pending authorized inspection, including after simulated recovery."]}
    try:
        url, cse, version = start_cse(runtime, processes)
        evidence["runtime"] = {"isolated_cse_pid": cse.pid, "url": url, "base": "cse-multiapp", "installed_acmecse_version": version,
                               "existing_runtime_modified": False}
        client = CSEClient(url, trace_path=runtime / "provisioning-requests.jsonl", timeout=5)
        for scenario in ("recovery", "missing_ack", "no_recovery"):
            result = run_scenario(client, url, runtime, destination, run_id, scenario, processes)
            evidence["scenarios"][scenario] = {"result": result["result"], "event_id": result["event_id"], "evidence": scenario + "/result.json"}
        evidence["result"] = "PASS_ACTUAL_CSE_MULTI_APPLICATION"
    except Exception as error:
        evidence["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        if client:
            client.close()
        evidence["cleanup"] = {"owned_processes": [{"pid": process.pid, "returncode": stop_process(process)} for process in reversed(processes)]}
        evidence["cleanup"]["all_owned_processes_stopped"] = all(process.poll() is not None for process in processes)
        evidence["existing_process_records_after"] = existing_process_records()
        evidence["existing_process_records_preserved"] = evidence["existing_process_records_before"] == evidence["existing_process_records_after"]
        evidence["source_sha256_after"] = hashes()
        evidence["source_unchanged_during_run"] = evidence["source_sha256_before"] == evidence["source_sha256_after"]
        evidence["completed_at"] = now()
        retained = sorted(destination.glob("*/*"))
        evidence["artifact_sha256"] = {str(path.relative_to(destination)): hashlib.sha256(path.read_bytes()).hexdigest() for path in retained if path.is_file()}
        (destination / "index.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"result": evidence["result"], "run_id": run_id, "evidence": str(destination / "index.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
