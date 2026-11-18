#!/usr/bin/env python3
"""Isolated real-ACME maintenance failover; never stops existing CSE profiles."""
from __future__ import annotations

import argparse
import configparser
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import httpx
from opensoom.handover import AuthorityStore, MaintenanceHandover, ServingCSE, timestamp
from opensoom.onem2m import CSEClient, CSEError


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stop_owned(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@contextmanager
def isolated_runtime(run_id, children):
    with tempfile.TemporaryDirectory(prefix=run_id + "-", dir=ROOT / "tmp") as folder:
        try:
            yield Path(folder)
        finally:
            # Stop writers before TemporaryDirectory removes CSE databases.
            for process in children:
                stop_owned(process)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", default="evidence/runtime/handover/acceptance.json", help="Successful alias; unique run JSON/trace files are always retained alongside it")
    parser.add_argument("--inject-target-write-failure", action="store_true", help="Inject exactly one pre-dispatch incident-write transport failure to test staged restoration retry")
    args = parser.parse_args()
    run_id = "handover-" + uuid.uuid4().hex[:10]
    alias = ROOT / args.evidence
    destination = alias.parent
    destination.mkdir(parents=True, exist_ok=True)
    cse_python = ROOT / "tmp/runtime/cse-venv/bin/python"
    if not cse_python.exists():
        raise SystemExit("Installed pinned ACME environment required; no installation is performed")
    watched = ["src/opensoom/handover.py", "src/opensoom/onem2m.py", "scripts/cse_handover_demo.py", "deploy/acme-single.ini"]
    hashes = lambda: {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in watched}
    evidence = {"run_id": run_id, "started_at": timestamp(), "kind": "actual_serving_CSE_maintenance_transition", "physical_device": "simulated", "source_sha256_before": hashes(), "checks": {}, "limitations": ["Two independent ACME IN-CSE processes on one host, using loopback HTTP and trusted claimed AE origins.", "Application-managed logical endpoint routing and new CSE-local AE mapping; not native AE-ID registration mobility.", "Controller and virtual device share one durable local SQLite authority/dedupe database; not distributed consensus or node-failure HA.", "Privileged provisioning rebuilds scoped ACPs and native subscriptions; ordinary operations use their registered role origins.", "No MEC hosting, MEC services, VM/process migration, physical ventilation or health outcome."]}
    raw_events = queue.Queue()
    received_events = []
    controller = None
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/notify":
                self.send_error(404)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 65536:
                    raise ValueError("Invalid notification length")
                payload = json.loads(self.rfile.read(size))
            except (ValueError, json.JSONDecodeError):
                self.send_error(400)
                return
            event = {"at": timestamp(), "rqi": self.headers.get("X-M2M-RI"), "body": payload}
            received_events.append(event)
            raw_events.put(event)
            self.send_response(200)
            self.send_header("X-M2M-RSC", "2000")
            self.send_header("X-M2M-RI", self.headers.get("X-M2M-RI", ""))
            self.send_header("X-M2M-RVI", "4")
            self.end_headers()

        def do_GET(self):
            if self.path != "/facility/maintenance-demo":
                self.send_error(404)
                return
            try:
                data, status = controller.logical_snapshot(), 200
            except (CSEError, AttributeError):
                data, status = {"status": "temporarily_unavailable"}, 503
            encoded = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logical_url = f"http://127.0.0.1:{server.server_port}/facility/maintenance-demo"
    clients, children, logs, ports = [], [], [], []
    monitored_before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / ".runtime").rglob("process.json")}
    checks = evidence["checks"]
    temp_parent = ROOT / "tmp"
    temp_parent.mkdir(exist_ok=True)
    exit_status, runtime_folder = 1, None
    try:
        version = subprocess.check_output([str(cse_python), "-c", "from importlib.metadata import version; print(version('acmecse'))"], text=True).strip()
        assert version == "2026.5.3", version
        evidence["cse_version"] = version
        with isolated_runtime(run_id, children) as folder:
            runtime_folder = folder
            targets = []
            for key in ("A", "B"):
                port = unused_port()
                while port in ports or port == server.server_port:
                    port = unused_port()
                ports.append(port)
                directory = folder / key
                directory.mkdir(mode=0o700)
                config = configparser.ConfigParser(interpolation=None)
                config.optionxform = str
                config.read(ROOT / "deploy/acme-single.ini")
                base, cse_id = "cse-ho-" + key.lower(), "opensoom-ho-" + key.lower() + "-" + run_id[-10:]
                config["basic.config"].update(cseName=base, cseID=cse_id, httpPort=str(port), secret=secrets.token_urlsafe(32))
                with (directory / "acme.ini").open("w") as output:
                    config.write(output)
                (directory / "acme.ini").chmod(0o600)
                log = (directory / "stdout.log").open("w")
                logs.append(log)
                process = subprocess.Popen([str(cse_python), "-m", "acmecse", "--base-directory", str(directory), "--headless"], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                children.append(process)
                client = CSEClient(f"http://127.0.0.1:{port}", timeout=0.5, trace_path=folder / (key + "-requests.jsonl"))
                clients.append(client)
                targets.append(ServingCSE(key, client.base_url, base, "/" + cse_id, client))
            for process, target in zip(children, targets):
                deadline = time.monotonic() + 45
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Owned ACME exited before readiness")
                    try:
                        checks["cse_" + target.key] = target.client.retrieve(target.base)
                        break
                    except CSEError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Isolated ACME readiness timed out")
                        time.sleep(0.15)
            assert checks["cse_A"]["body"]["m2m:cb"]["csi"] != checks["cse_B"]["body"]["m2m:cb"]["csi"]
            store = AuthorityStore(folder / "authority.sqlite")
            controller = MaintenanceHandover(targets, store, "ho" + run_id[-10:], f"http://127.0.0.1:{server.server_port}/notify")
            incident = {"id": "incident-" + run_id, "status": "open", "reason": "Planned ventilation controller maintenance; diagnosis must continue", "created_at": timestamp()}
            state = {"facility_id": "maintenance-demo", "profile_id": "food-production-maintenance", "profile_version": 1, "command_ttl_seconds": 60, "last_sequence": 0, "last_observation": None, "incident": incident, "pending_command": None, "simulated": True}
            checks["initial_provisioning"] = controller.initialize(state)
            injected = []
            if args.inject_target_write_failure:
                original_create = targets[1].client.create
                def create_with_one_failure(parent, ty, resource, origin=None):
                    if not injected and parent.endswith("/incident") and ty == 4:
                        fault = {"at": timestamp(), "kind": "synthetic_pre_dispatch_transport_failure", "parent": parent, "authority_at_fault": store.get("authority")}
                        injected.append(fault)
                        raise CSEError("One-shot target incident-write fault injection", {"rsc": 0, "rqi": "injected-target-write", "body": {"error": "injected_before_HTTP_dispatch"}, "http_status": 0})
                    return original_create(parent, ty, resource, origin=origin)
                targets[1].client.create = create_with_one_failure

            def drain_until(sequence, timeout=6):
                deadline = time.monotonic() + timeout
                while store.get("snapshot")["last_sequence"] < sequence and time.monotonic() < deadline:
                    try:
                        controller.accept_notification(raw_events.get(timeout=0.1))
                    except queue.Empty:
                        pass
                assert store.get("snapshot")["last_sequence"] == sequence

            baseline = []
            for sequence in (1, 2, 3):
                observation = {"facility_id": "maintenance-demo", "sequence": sequence, "observed_at": timestamp(), "airflow_m3_h": 360, "fan_running": True, "simulated": True}
                written = controller.publish_observation(observation)
                drain_until(sequence)
                baseline.append({"write": written, "notification": controller.notifications[-1]})
            checks["baseline_subscription_observations"] = baseline
            expires = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
            checks["pending_at_A"] = controller.queue_command(run_id + ":pending", 100.0, expires)
            source_command = controller.read_command(targets[0])
            saved_snapshot = store.get("snapshot")
            with httpx.Client(timeout=3, trust_env=False) as logical:
                before = logical.get(logical_url)
                assert before.status_code == 200
                before_read = time.monotonic()
                before_at = timestamp()
                checks["logical_endpoint_before"] = before.json()
                stop_at = timestamp()
                stop_owned(children[0])
                attempts = []
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    event = controller.tick()
                    response = logical.get(logical_url)
                    attempts.append({"at": timestamp(), "status": response.status_code, "health": event["kind"]})
                    if event["kind"] == "target_restore_pending":
                        assert store.get("authority")["target"] == "A" and response.status_code == 503
                        checks["partial_target_write_failure"] = {"fault": injected, "authority_retained": store.get("authority"), "restore_pending": store.get("restore_pending"), "actual_prepared_B_state": targets[1].client.retrieve(targets[1].root + "/state/la", origin=targets[1].roles["controller"]), "stable_endpoint_status": response.status_code}
                    if response.status_code == 200 and response.json()["serving_cse_id"] == targets[1].cse_id:
                        after_read, after_at = time.monotonic(), timestamp()
                        checks["logical_endpoint_after"] = response.json()
                        break
                    time.sleep(0.1)
                else:
                    raise TimeoutError("Automatic availability-driven serving-CSE switch did not complete")
            assert controller.active.key == "B" and store.get("authority")["epoch"] == 2
            assert store.get("restore_pending") is None
            if args.inject_target_write_failure:
                assert len(injected) == 1 and checks["partial_target_write_failure"]["restore_pending"]["target"] == "B"
                assert controller.history[-1]["resumed_after_failures"] == 1
            assert json.loads(checks["logical_endpoint_after"]["incident"]["body"]["m2m:cin"]["con"]) == incident
            rebuilt = json.loads(checks["logical_endpoint_after"]["state"]["body"]["m2m:cin"]["con"])
            assert rebuilt["facility_id"] == saved_snapshot["facility_id"] and rebuilt["last_observation"] == saved_snapshot["last_observation"] and rebuilt["profile_version"] == saved_snapshot["profile_version"]
            assert rebuilt["pending_command"]["command_id"] == saved_snapshot["pending_command"]["command_id"]
            checks["automatic_transition"] = {"history": controller.history, "stable_logical_url": logical_url, "attempts": attempts, "last_success_A_at": before_at, "source_stop_requested_at": stop_at, "first_success_B_at": after_at, "observed_read_interruption_seconds": round(after_read - before_read, 6), "measure": "Time from the last successful A-backed stable endpoint read to its first successful B-backed read, including stop and rebuild; one run, not an SLA."}
            checks["stale_source_command_fenced"] = controller.apply_virtual(source_command, targets[0])
            assert checks["stale_source_command_fenced"]["code"] == "stale_authority"
            forged_source = json.loads(source_command["body"]["m2m:cin"]["con"])
            forged_source.update(target="B", epoch=2)
            checks["old_source_cannot_claim_new_epoch"] = store.execute_virtual(forged_source, targets[0].cse_id)
            assert checks["old_source_cannot_claim_new_epoch"]["code"] == "stale_authority"
            target_command = controller.read_command()
            first = controller.apply_virtual(target_command, targets[1])
            restarted_store = AuthorityStore(folder / "authority.sqlite")
            controller.store = restarted_store
            replay = controller.apply_virtual(target_command, targets[1])
            assert first["status"] == "applied" and replay["status"] == "duplicate" and restarted_store.execution_count() == 1
            checks["target_pending_command_deduped"] = {"actual_command_read": target_command, "first": first, "after_reopened_database": replay, "execution_count": restarted_store.execution_count(), "ack_read": targets[1].client.retrieve(targets[1].root + "/acks/la", origin=targets[1].roles["controller"])}
            denied = None
            try:
                targets[1].client.create(targets[1].root + "/commands", 4, {"m2m:cin": {"con": "unauthorized"}}, origin=targets[1].roles["observer"])
            except CSEError as error:
                denied = error.result
            assert denied and denied["rsc"] == 4103
            checks["rebuilt_target_acp_denied_writer"] = denied
            old_writer_denied = None
            try:
                targets[1].client.create(targets[1].root + "/commands", 4, {"m2m:cin": {"con": "old-controller"}}, origin=targets[0].roles["controller"])
            except CSEError as error:
                old_writer_denied = error.result
            assert old_writer_denied and old_writer_denied["rsc"] == 4103
            checks["old_cse_controller_not_authorized_at_target"] = old_writer_denied
            controller.publish_observation({"facility_id": "maintenance-demo", "sequence": 4, "observed_at": timestamp(), "airflow_m3_h": 365, "fan_running": True, "simulated": True})
            drain_until(4)
            latest = controller.notifications[-1]
            assert latest["authority"]["target"] == "B" and latest["sequence"] == 4
            checks["post_switch_native_subscription"] = latest
            checks["native_subscription_verification_callbacks"] = [e for e in received_events if e["body"].get("m2m:sgn", {}).get("vrq")]
            assert len(checks["native_subscription_verification_callbacks"]) >= 2
            checks["observation_sequence"] = {"injected": [1, 2, 3, 4], "accepted_from_native_callbacks": [n["sequence"] for n in controller.notifications], "meaning": "Four discrete injected samples, no missing injected sample. Not an asynchronous packet-loss or complete-history-replication claim."}
            assert checks["observation_sequence"]["accepted_from_native_callbacks"] == [1, 2, 3, 4]
            evidence["source_sha256_after"] = hashes()
            assert evidence["source_sha256_before"] == evidence["source_sha256_after"]
            evidence["request_traces"] = {}
            for target in targets:
                trace = folder / (target.key + "-requests.jsonl")
                if trace.exists():
                    output = destination / (run_id + "-" + target.key + "-requests.jsonl")
                    output.write_bytes(trace.read_bytes())
                    evidence["request_traces"][target.key] = {"path": str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "records": len(output.read_text().splitlines())}
            evidence["result"] = "PASS_REAL_SERVING_CSE_MAINTENANCE_HANDOVER"
            exit_status = 0
    except Exception as error:
        evidence["result"] = "FAIL"
        evidence["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
    finally:
        for process in children:
            stop_owned(process)
        for client in clients:
            client.close()
        server.shutdown()
        server.server_close()
        for log in logs:
            log.close()
        evidence["cleanup"] = {"owned_children_exited": all(p.poll() is not None for p in children), "temporary_cse_directories_removed": runtime_folder is None or not runtime_folder.exists(), "existing_process_records_unchanged": all((ROOT / p).exists() and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in monitored_before.items()), "ports": ports, "listeners_closed": []}
        for port in ports + [server.server_port]:
            with socket.socket() as sock:
                sock.settimeout(0.3)
                evidence["cleanup"]["listeners_closed"].append({"port": port, "closed": sock.connect_ex(("127.0.0.1", port)) != 0})
        evidence["completed_at"] = timestamp()
        assert evidence["cleanup"]["owned_children_exited"] and all(x["closed"] for x in evidence["cleanup"]["listeners_closed"])
        (destination / (run_id + ".json")).write_text(json.dumps(evidence, indent=2) + "\n")
        if exit_status == 0:
            alias.write_text(json.dumps(evidence, indent=2) + "\n")
        output = destination / (run_id + ".json")
        print(json.dumps({"result": evidence["result"], "run_id": run_id, "evidence": str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output), "cleanup": evidence["cleanup"]}))
    return exit_status


if __name__ == "__main__":
    raise SystemExit(main())
