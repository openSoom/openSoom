"""Independent CSE applications for a virtual ventilation/maintenance scenario.

These workers communicate only through oneM2M resources. The provisioning
runner assigns identities and subscriptions; an application never uses CAdmin.
This loopback example uses claimed AE origins, not cryptographic AE identity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import re
import signal
import threading
import time
from typing import Any

from .models import Observation, utcnow
from .onem2m import CSEClient, CSEError
from .policy import diagnose


def content(result: dict) -> dict:
    value = result["body"]["m2m:cin"]["con"]
    return json.loads(value) if isinstance(value, str) else value


def observation_from_event(event: dict, config: dict) -> Observation:
    """Keep profile, scope and simulation authorization outside incoming data."""
    if event.get("schema_version") != 1 or event.get("event_id") != config["event_id"]:
        raise ValueError("Unconfigured event or schema")
    if event.get("asset_id") != config["asset_id"]:
        raise ValueError("Unconfigured asset")
    observation = Observation.model_validate(event["observation"])
    if observation.facility_id != config["facility_id"] or observation.zone_id not in config["zones"]:
        raise ValueError("Observation scope mismatch")
    return observation


def command_is_allowed(command: dict, config: dict, now: datetime | None = None) -> bool:
    """The virtual adapter enforces configuration independently of the operator."""
    now = now or datetime.now(timezone.utc)
    try:
        issued, expires = (datetime.fromisoformat(command[key]) for key in ("issued_at", "expires_at"))
        return bool(
            config.get("simulation_only") is True
            and config.get("controls_enabled") is True
            and command.get("event_id") == config["event_id"]
            and command.get("facility_id") == config["facility_id"]
            and command.get("zone_id") == config["target_zone"]
            and command.get("asset_id") == config["asset_id"]
            and command.get("profile_id") == config["profile"]["id"]
            and command.get("profile_version") == config["profile"]["schema_version"]
            and command.get("action") == "set_damper"
            and command["action"] in config["profile"]["allowed_actions"]
            and command.get("value") == 100
            and issued.tzinfo is not None and expires.tzinfo is not None
            and issued <= now < expires
            and 0 < (expires - issued).total_seconds() <= config["profile"]["command_ttl_seconds"]
        )
    except (KeyError, TypeError, ValueError):
        return False


class Application:
    """One process, one role, one CSE client, and a durable local checkpoint."""

    def __init__(self, role: str, config: dict, state_path: Path, trace_path: Path):
        if role not in ("operations", "maintenance", "device"):
            raise ValueError("Unknown application")
        if config.get("simulation_only") is not True:
            raise ValueError("This example accepts simulated equipment only")
        self.role, self.config, self.path = role, config, state_path
        if config["origin"] == "CAdmin":
            raise ValueError("Applications require their own non-administrator AE")
        self.client = CSEClient(config["url"], origin=config["origin"], trace_path=trace_path, timeout=3)
        self.events: queue.Queue[dict] = queue.Queue()
        self.stop = threading.Event()
        self.state = json.loads(state_path.read_text()) if state_path.exists() else {
            "role": role, "ae_origin": config["origin"], "event_id": config["event_id"],
            "seen": [], "receipts": [], "transitions": [], "status": "waiting", "errors": [],
        }
        if self.state["event_id"] != config["event_id"] or self.state["role"] != role:
            raise ValueError("Checkpoint belongs to another event/application")
        self.server: ThreadingHTTPServer | None = None

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".new")
        temporary.write_text(json.dumps(self.state, indent=2) + "\n")
        temporary.replace(self.path)

    def publish(self, name: str, value: dict) -> dict:
        result = self.client.create(self.config["paths"][name], 4, {
            "m2m:cin": {"con": json.dumps(value), "cnf": "application/json:0"},
        })
        return result

    def transition(self, status: str, **details):
        value = {"at": utcnow(), "application": self.role, "event_id": self.config["event_id"],
                 "asset_id": self.config["asset_id"], "facility_id": self.config["facility_id"],
                 "zone_id": self.config["target_zone"], "status": status, "simulated": True, **details}
        self.state.update(status=status)
        self.state["transitions"].append(value)
        if self.role != "device":
            name = "operations_reports" if self.role == "operations" else "work_orders"
            self.state["output"] = self.publish(name, value)
        self.save()

    def start_receiver(self):
        app = self

        class Receiver(BaseHTTPRequestHandler):
            def do_POST(self):
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if self.path != "/notify" or not 0 < size <= 65536:
                        raise ValueError("Invalid notification request")
                    payload = json.loads(self.rfile.read(size))
                    if not isinstance(payload, dict) or not isinstance(payload.get("m2m:sgn"), dict):
                        raise ValueError("Invalid oneM2M notification")
                    app.events.put({"received_at": utcnow(), "rqi": self.headers.get("X-M2M-RI"), "body": payload})
                    self.send_response(200)
                    self.send_header("X-M2M-RSC", "2000")
                    self.send_header("X-M2M-RI", self.headers.get("X-M2M-RI", ""))
                    self.send_header("X-M2M-RVI", "4")
                    self.end_headers()
                except (ValueError, KeyError, TypeError):
                    self.send_error(400)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.state.update(endpoint=f"http://127.0.0.1:{self.server.server_port}/notify", running=True)
        self.save()

    def authoritative(self, signal_body: dict) -> tuple[str, dict]:
        """Notification is a hint. Fetch that exact CIN under a configured parent."""
        hinted = signal_body["nev"]["rep"]["m2m:cin"]
        parent = next((name for name, ri in self.config["container_ids"].items() if ri == hinted.get("pi")), None)
        if parent is None or not re.fullmatch(r"[A-Za-z0-9_.-]+", hinted.get("rn", "")) or hinted["rn"] in (".", ".."):
            raise ValueError("Notification parent/name is outside configured resources")
        result = self.client.retrieve(self.config["paths"][parent] + "/" + hinted["rn"])
        resource = result["body"]["m2m:cin"]
        if resource["ri"] != hinted.get("ri") or resource["pi"] != hinted["pi"]:
            raise ValueError("Notification does not match authoritative CSE state")
        return parent, result

    def receive(self, event: dict):
        self.state["receipts"].append(event)
        sgn = event["body"]["m2m:sgn"]
        if sgn.get("vrq"):
            self.save()
            return
        parent, result = self.authoritative(sgn)
        ri = result["body"]["m2m:cin"]["ri"]
        if ri in self.state["seen"]:
            return
        value = content(result)
        if parent.startswith("observations_"):
            observation = observation_from_event(value, self.config)
            if observation.zone_id != self.config["target_zone"]:
                raise ValueError("Unexpected subscription zone")
            if self.role == "operations":
                self.operations_observation(observation, result)
            elif self.role == "maintenance":
                self.maintenance_observation(observation, result)
        elif parent == "acks" and self.role == "operations":
            self.operations_ack(value, result)
        elif parent == "commands" and self.role == "device":
            self.device_command(value, result)
        else:
            raise ValueError("Subscription does not match this application")
        self.state["seen"].append(ri)
        self.save()

    def operations_observation(self, observation: Observation, result: dict):
        cfg = self.config
        if self.state["status"] == "awaiting_ack":
            # The ACK and samples arrive on distinct subscriptions. Keep invalid
            # samples as well: they break a streak when replayed after the ACK.
            pending = self.state.setdefault("pending_observations", [])
            pending.append(result)
            del pending[: -cfg["profile"]["recovery_samples"] * 4]
            return
        diagnosis = diagnose(observation, cfg["zones"][observation.zone_id], cfg["profile"])
        if diagnosis["status"] in ("stale", "missing"):
            if self.state["status"] == "awaiting_outcome":
                self.state.update(recovery_samples=0, unresolved_samples=0)
            self.state.setdefault("rejected_observations", []).append({"diagnosis": diagnosis, "source": result})
            self.save()
            return
        if not self.state.get("command") and diagnosis["status"] == "critical":
            # The CSE performs membership traversal and permission checks.
            group = self.client.group_read(cfg["paths"]["observation_group"])
            members = group["body"]["m2m:agr"]["m2m:rsp"]
            if len(members) != len(cfg["zones"]) or any(item["rsc"] != 2000 for item in members):
                raise ValueError("Incomplete facility group context")
            snapshots = {}
            for zone in cfg["zones"]:
                latest = self.client.retrieve(cfg["paths"]["observations_" + zone] + "/la")
                item = observation_from_event(content(latest), cfg)
                if item.zone_id != zone:
                    raise ValueError("Group observation scope mismatch")
                status = diagnose(item, cfg["zones"][zone], cfg["profile"])
                if status["status"] in ("stale", "missing"):
                    raise ValueError("Facility group context is not fresh")
                snapshots[zone] = {"diagnosis": status, "source": latest}
            issued = datetime.now(timezone.utc)
            command = {"schema_version": 1, "event_id": cfg["event_id"], "command_id": "command-" + cfg["event_id"],
                       "facility_id": cfg["facility_id"], "zone_id": cfg["target_zone"], "asset_id": cfg["asset_id"],
                       "profile_id": cfg["profile"]["id"], "profile_version": cfg["profile"]["schema_version"],
                       "action": "set_damper", "value": 100, "simulated": True,
                       "issued_at": issued.isoformat(), "expires_at": (issued + timedelta(seconds=cfg["ack_wait_seconds"])).isoformat(),
                       "source_observation_ri": result["body"]["m2m:cin"]["ri"]}
            if not command_is_allowed(command, cfg):
                raise ValueError("Configured controls do not authorize this command")
            created = self.publish("commands", command)
            self.state.update(command=command, command_creation=created, recovery_samples=0, unresolved_samples=0)
            self.transition("awaiting_ack", source=result, diagnosis=diagnosis, native_group=group, facility_context=snapshots,
                            command_id=command["command_id"], command_creation_rqi=created["rqi"])
        elif self.state.get("ack") and self.state["status"] == "awaiting_outcome":
            if datetime.fromisoformat(observation.observed_at) <= datetime.fromisoformat(self.state["ack"]["ack_at"]):
                return
            key = "recovery_samples" if diagnosis["status"] == "nominal" else "unresolved_samples"
            self.state[key] += 1
            self.state["unresolved_samples" if key == "recovery_samples" else "recovery_samples"] = 0
            if self.state[key] >= cfg["profile"]["recovery_samples"]:
                self.transition("verified_recovery" if key == "recovery_samples" else "unresolved_after_ack",
                                command_id=self.state["command"]["command_id"], ack=self.state["ack"],
                                source=result, diagnosis=diagnosis, post_ack_samples=self.state[key])

    def operations_ack(self, ack: dict, result: dict):
        command = self.state.get("command")
        if not command or self.state["status"] != "awaiting_ack":
            return
        if (ack.get("event_id") != command["event_id"] or ack.get("command_id") != command["command_id"]
                or ack.get("command_ri") != self.state["command_creation"]["body"]["m2m:cin"]["ri"]
                or ack.get("simulated") is not True or ack.get("device_state") != "damper_changed"):
            raise ValueError("ACK correlation mismatch")
        ack_time = datetime.fromisoformat(ack["ack_at"])
        if not datetime.fromisoformat(command["issued_at"]) <= ack_time < datetime.fromisoformat(command["expires_at"]):
            raise ValueError("ACK outside command lifetime")
        self.state["ack"] = ack
        self.transition("awaiting_outcome", source=result, command_id=command["command_id"], ack=ack)
        pending = self.state.pop("pending_observations", [])
        for source in sorted(pending, key=lambda item: content(item)["observation"]["observed_at"]):
            self.operations_observation(observation_from_event(content(source), self.config), source)

    def maintenance_observation(self, observation: Observation, result: dict):
        cfg = self.config
        diagnosis = diagnose(observation, cfg["zones"][observation.zone_id], cfg["profile"])
        if diagnosis["status"] in ("stale", "missing"):
            return
        if not self.state.get("work_order_id") and diagnosis["status"] == "critical":
            self.state["work_order_id"] = "work-order-" + cfg["event_id"]
            self.transition("inspection_required", work_order_id=self.state["work_order_id"],
                            action="Inspect exhaust fan, damper and capture path; verify airflow with facility procedure",
                            reason=diagnosis["reason"], source=result)
        elif self.state.get("work_order_id"):
            status = "observations_recovered_inspection_pending" if diagnosis["status"] == "nominal" else "inspection_required"
            self.transition(status, work_order_id=self.state["work_order_id"], source=result,
                            action="Retain work order until an authorized inspection; simulated recovery cannot close physical maintenance")

    def device_publish(self, zone_id: str, critical: bool, sequence: int):
        cfg = self.config
        zone = cfg["zones"][zone_id]
        observation = Observation(facility_id=cfg["facility_id"], zone_id=zone_id, observed_at=utcnow(),
                                  adapter="vendor-a", airflow=zone["minimum_airflow"] * (0.4 if critical else 1.2),
                                  pm25=zone["pm25_warning"] * (1.5 if critical else 0.5),
                                  co2=zone["co2_warning"] * 0.6, fan_running=True, damper_pct=35 if critical else 100)
        value = {"schema_version": 1, "event_id": cfg["event_id"], "asset_id": cfg["asset_id"],
                 "sequence": sequence, "observation": observation.model_dump()}
        result = self.publish("observations_" + zone_id, value)
        self.state.setdefault("observations", []).append(result)
        self.save()

    def device_command(self, command: dict, result: dict):
        if not command_is_allowed(command, self.config):
            self.transition("command_rejected", source=result)
            return
        self.state.update(received_command=command, command_retrieval=result)
        if self.config["scenario"] == "missing_ack":
            self.transition("simulated_no_ack", source=result)
            return
        ack = {"event_id": command["event_id"], "command_id": command["command_id"],
               "command_ri": result["body"]["m2m:cin"]["ri"], "ack_at": utcnow(),
               "simulated": True, "device_state": "damper_changed", "value": command["value"]}
        self.state["ack_creation"] = self.publish("acks", ack)
        self.transition("simulated_ack_written", ack=ack)
        # Independent observed samples are required; ACK alone is never recovery.
        for sequence in range(2, self.config["profile"]["recovery_samples"] + 2):
            if self.stop.wait(0.15):
                return
            self.device_publish(self.config["target_zone"], self.config["scenario"] == "no_recovery", sequence)

    def tick(self):
        command = self.state.get("command")
        if self.role != "operations" or not command:
            return
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(command["expires_at"])
        if now >= expires and self.state["status"] == "awaiting_ack":
            self.transition("ack_timed_out", command_id=command["command_id"], ack=None,
                            outcome="CSE accepted the command; no device acknowledgement was observed")
        elif now >= expires + timedelta(seconds=self.config["ack_wait_seconds"]) and self.state["status"] == "awaiting_outcome":
            self.transition("outcome_unverified", command_id=command["command_id"], ack=self.state.get("ack"))

    def run(self):
        self.start_receiver()
        try:
            if self.role == "device":
                # Startup coordination only. All operating data goes through CSE.
                while not Path(self.config["start_signal"]).exists():
                    if self.stop.wait(0.05):
                        return
                # The runner starts this publisher after both consumers subscribe.
                for zone in self.config["zones"]:
                    if zone != self.config["target_zone"]:
                        self.device_publish(zone, False, 1)
                self.device_publish(self.config["target_zone"], True, 1)
            while not self.stop.is_set():
                try:
                    self.receive(self.events.get(timeout=0.05))
                except queue.Empty:
                    pass
                except (CSEError, ValueError, KeyError, TypeError) as error:
                    self.state["errors"].append({"at": utcnow(), "error": type(error).__name__, "message": str(error)})
                    self.save()
                self.tick()
        finally:
            self.state["running"] = False
            self.save()
            if self.server:
                self.server.shutdown()
                self.server.server_close()
            self.client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", choices=["operations", "maintenance", "device"], required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    app = Application(args.role, json.loads(args.config.read_text()), args.state, args.trace)
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: app.stop.set())
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
