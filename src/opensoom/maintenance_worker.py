"""Facility-scoped maintenance and sensor bridge applications for oneM2M."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import re
import signal
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

from .mec_sensor import EvidenceError, SensorService, percentage, timestamp
from .onem2m import CSEClient, CSEError

LOG = logging.getLogger(__name__)
IDENTITY = ("facility_id", "zone_id", "asset_id", "incident_id", "run_id", "source_cin_ri")
SEGMENT = re.compile(r"[a-zA-Z0-9._-]+")


def key(prefix, *parts):
    digest = hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()
    return prefix + "-" + digest[:32]


def read_content(resource):
    content = resource["con"]
    return json.loads(content) if isinstance(content, str) else content


def safe_rn(name):
    if not isinstance(name, str) or name in (".", "..") or not SEGMENT.fullmatch(name):
        raise EvidenceError("invalid_resource_name")
    return name


class MaintenanceWorker:
    def __init__(self, role, config):
        if role not in ("maintenance", "bridge"):
            raise ValueError("Unknown worker role")
        self.role, self.config = role, config
        self.facility = config["facility_id"]
        self.base = config["facility_path"].strip("/")
        if config["origin"] == "CAdmin" or not config["origin"]:
            raise ValueError("Use the role's non-administrator AE identity")
        token = os.environ.get("OPENSOOM_WORKER_CSE_TOKEN")
        self.cse = CSEClient(config["cse_url"], config["origin"], config.get("cse_ca"),
                             config.get("trace_path"), timeout=5, bearer_token=token)
        self.provider = None
        if role == "bridge":
            if config["bridge_mode"] == "mec046":
                self.provider = SensorService(config, os.environ.get("OPENSOOM_MEC_TOKEN"))
            elif config["bridge_mode"] != "local":
                raise ValueError("Expected local or mec046 bridge mode")
        self.inputs = ("outcomes", "sensor_responses") if role == "maintenance" else ("sensor_requests",)
        if self.provider and config.get("provider_registration"):
            self.inputs = ("provider_requests", "sensor_requests")
        self.seen = set()
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.health = {"role": role, "facility_id": self.facility, "scans": 0, "notifications": 0, "rejections": 0}

    def close(self):
        self.cse.close()
        if self.provider:
            self.provider.client.close()

    def children(self, stream):
        path = self.base + "/" + stream
        found = self.cse.discover(path, {"ty": 4, "drt": 1, "lvl": 1})
        for uri in found["body"].get("m2m:uril", []):
            name = safe_rn(uri.rsplit("/", 1)[-1])
            yield path + "/" + name

    def cin(self, path):
        return self.cse.retrieve(path)["body"]["m2m:cin"]

    def put(self, stream, name, payload):
        """A named CIN is the durable idempotency key, including across process restarts."""
        parent = self.base + "/" + stream
        try:
            result = self.cse.create(parent, 4, {"m2m:cin": {"rn": name, "cnf": "application/json:0",
                                     "con": json.dumps(payload, allow_nan=False, separators=(",", ":"))}})
            return result["body"]["m2m:cin"]
        except CSEError as exc:
            if exc.rsc != 4105:
                raise
            return self.cin(parent + "/" + name)

    def binding(self, event):
        if event.get("facility_id") != self.facility:
            raise EvidenceError("facility_mismatch")
        binding = self.config["assets"].get(event.get("zone_id"))
        if not binding or binding["asset_id"] != event.get("asset_id"):
            raise EvidenceError("unknown_asset_binding")
        return binding

    def work_order(self, event, source_ri, revision, priority, evidence_status, **details):
        work_id = "work-" + event["incident_id"]
        payload = {**{k: event[k] for k in IDENTITY}, "kind": "work_order", "work_order_id": work_id,
                   "command_id": event.get("command_id"), "observed_at": event["observed_at"],
                   "status": "open", "priority": priority, "evidence_status": evidence_status,
                   "revision": revision, **details}
        self.put("work_orders", key("order", work_id, source_ri, revision), payload)

    def outcome(self, event, resource):
        binding = self.binding(event)
        kind = event["kind"]
        if kind not in ("incident.opened", "command.unresolved_after_ack"):
            return
        prefix = self.base + "/" + safe_rn(event["zone_id"]) + "/observations/"
        path = event["source_cin_path"].strip("/")
        if not path.startswith(prefix):
            raise EvidenceError("observation_outside_zone")
        name = safe_rn(path[len(prefix):])
        if name in ("la", "ol"):
            raise EvidenceError("expected_immutable_observation")
        receipt = self.cse.retrieve(path)
        raw = receipt["body"]["m2m:cin"]
        obs = read_content(raw)
        if (raw["ri"] != event["source_cin_ri"] or obs.get("facility_id") != self.facility
                or obs.get("zone_id") != event["zone_id"] or timestamp(obs["observed_at"]) != timestamp(event["observed_at"])):
            raise EvidenceError("source_observation_mismatch")
        details = {"outcome_ri": resource["ri"], "observation_rqi": receipt["rqi"],
                   "airflow": obs.get("airflow"), "profile_version": event["profile_version"]}
        if kind == "incident.opened":
            self.work_order(event, resource["ri"], 1, "inspection", "awaiting_outcome", **details)
            return
        request_id = key("sensor", self.facility, event["incident_id"], event["command_id"])
        self.work_order(event, resource["ri"], 2, "inspection", "awaiting_independent_sample", request_id=request_id, **details)
        request = {**{k: event[k] for k in IDENTITY}, "kind": "shaft_position_lookup",
                   "request_id": request_id, "work_order_id": "work-" + event["incident_id"],
                   "sensor_id": binding["sensor_id"], "outcome_ri": resource["ri"],
                   "observed_at": event["observed_at"], "ack_at": event["ack_at"],
                   "airflow": obs.get("airflow"), "profile_version": event["profile_version"],
                   "command_id": event["command_id"], "requested_pct": percentage(event["requested_pct"])}
        self.put("sensor_requests", request_id, request)

    def local_sample(self, request):
        matches = []
        for path in self.children("independent_samples"):
            cin = self.cin(path)
            sample = read_content(cin)
            if all(sample.get(k) == request[k] for k in ("facility_id", "zone_id", "asset_id", "sensor_id")):
                matches.append((cin, sample))
        if not matches:
            raise EvidenceError("no_mapped_sensor_sample")
        # Select the most recently committed sample for this binding. Its clock
        # and unit are then validated, including when the producer clock is bad.
        cin, sample = max(matches, key=lambda item: (int(item[0].get("st", 0)), item[0]["ct"], item[0]["ri"]))
        return {k: sample.get(k) for k in ("sensor_id", "value", "unit", "source", "observed_at")}, {"sample_cin_ri": cin["ri"]}

    def check_sample(self, req, sample, at):
        if sample["source"] != "independent_position_sensor" or sample["sensor_id"] != req["sensor_id"]:
            raise EvidenceError("unverified_source")
        if sample["unit"] != "%":
            raise EvidenceError("unexpected_measurement_unit")
        observed = timestamp(sample["observed_at"])
        settled = timestamp(req["ack_at"]) + timedelta(seconds=self.config["settle_seconds"])
        if observed < settled:
            raise EvidenceError("before_actuator_settled")
        age = (at - observed).total_seconds()
        if age < 0 or age > self.config["freshness_seconds"]:
            raise EvidenceError("outside_freshness_window")
        return percentage(sample["value"])

    def serve_request(self, request, resource):
        binding = self.binding(request)
        request_id = safe_rn(request["request_id"])
        if (request.get("kind") != "shaft_position_lookup" or request["sensor_id"] != binding["sensor_id"]
                or resource["rn"] != request_id):
            raise EvidenceError("unapproved_sensor_request")
        success_name = key("measurement", resource["ri"])
        # A successful lookup remains immutable if the worker is restarted.
        try:
            self.cin(self.base + "/sensor_responses/" + success_name)
            return True
        except CSEError as exc:
            if exc.rsc != 4004:
                raise
        payload = {"kind": "sensor_result", "facility_id": self.facility, "request_id": request_id,
                   "request_ri": resource["ri"], "mode": self.config["bridge_mode"]}
        try:
            sample, receipt = self.provider.read(request) if self.provider else self.local_sample(request)
            self.check_sample(request, sample, datetime.now(timezone.utc))
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            reason = str(exc) if isinstance(exc, EvidenceError) else type(exc).__name__
            self.put("sensor_responses", key("unknown", resource["ri"], reason),
                     {**payload, "status": "unknown", "reason": reason})
            return False
        self.put("sensor_responses", success_name, {**payload, "status": "measured", "sample": sample, "provider_receipt": receipt})
        return True

    def commission(self, request, resource):
        request_id = safe_rn(request["request_id"])
        if request.get("facility_id") != self.facility or request_id != resource["rn"]:
            raise EvidenceError("provider_request_mismatch")
        name = key("provider", resource["ri"])
        try:
            self.cin(self.base + "/provider_responses/" + name)
            return True
        except CSEError as exc:
            if exc.rsc != 4004:
                raise
        now = datetime.now(timezone.utc)
        reply = {"kind": "provider.result", "facility_id": self.facility, "request_id": request_id,
                 "request_ri": resource["ri"], "provider_profile": request.get("provider_profile"),
                 "observed_at": now.isoformat()}
        try:
            fields = {"kind", "request_id", "facility_id", "provider_profile", "requested_at"}
            if (request.keys() != fields or request["kind"] != "provider.enable" or
                    request["provider_profile"] != self.config["provider_registration"]["profile"]):
                raise EvidenceError("unapproved_provider_profile")
            if not 0 <= (now - timestamp(request["requested_at"])).total_seconds() <= 300:
                raise EvidenceError("provider_request_expired")
            status, receipt = self.provider.registration(commission=True)
        except EvidenceError as exc:
            self.put("provider_responses", name, {**reply, "status": "denied", "reason": str(exc)})
            return True
        except httpx.HTTPError:
            # An unconfirmed write may already have applied. Re-read on retry.
            return False
        self.put("provider_responses", name, {**reply, "status": status, "provider_receipt": receipt})
        return True

    def current_setpoint(self, req):
        stream = safe_rn(req["zone_id"]) + "/acks"
        latest = self.cin(self.base + "/" + stream + "/la")
        ack = read_content(latest)
        if ack.get("device_state") != "damper_changed":
            # Administrative work can be acknowledged on the same zone stream.
            # Compare retained actuator acknowledgements by the CSE state tag.
            candidates = []
            for path in self.children(stream):
                cin = self.cin(path)
                item = read_content(cin)
                if item.get("device_state") == "damper_changed":
                    candidates.append(((int(cin.get("st", 0)), cin["ct"]), item))
            if not candidates:
                return False
            _, ack = max(candidates, key=lambda candidate: candidate[0])
        return (ack.get("facility_id") == self.facility and ack.get("zone_id") == req["zone_id"]
                and ack.get("command_id") == req["command_id"] and
                timestamp(ack["ack_at"]) == timestamp(req["ack_at"]))

    def response(self, response, resource):
        request_id = safe_rn(response["request_id"])
        req_resource = self.cin(self.base + "/sensor_requests/" + request_id)
        req = read_content(req_resource)
        binding = self.binding(req)
        if (response.get("kind") != "sensor_result" or response["request_ri"] != req_resource["ri"]
                or response.get("facility_id") != self.facility or req["sensor_id"] != binding["sensor_id"]):
            raise EvidenceError("sensor_response_mismatch")
        if not self.current_setpoint(req):
            self.health["superseded_responses"] = self.health.get("superseded_responses", 0) + 1
            return
        detail = {"request_id": request_id, "request_ri": req_resource["ri"], "response_ri": resource["ri"],
                  "outcome_ri": req["outcome_ri"], "mode": response.get("mode"),
                  "airflow": req.get("airflow"), "profile_version": req.get("profile_version")}
        if response.get("status") == "unknown":
            self.work_order(req, resource["ri"], 3, "inspection", "unknown", reason=response.get("reason"), **detail)
            return
        if response.get("status") != "measured":
            raise EvidenceError("unsupported_response")
        final_name = key("order", "work-" + req["incident_id"], resource["ri"], 4)
        try:
            self.cin(self.base + "/work_orders/" + final_name)
            return
        except CSEError as exc:
            if exc.rsc != 4004:
                raise
        try:
            value = self.check_sample(req, response["sample"], datetime.now(timezone.utc))
        except EvidenceError as exc:
            # An existing accepted revision survives delayed replay. New stale
            # inputs have a lower revision than fresh evidence for the same request.
            self.work_order(req, resource["ri"], 3, "inspection", "unknown", reason=str(exc), **detail)
            return
        mismatch = abs(value - req["requested_pct"]) > self.config["tolerance_pct"]
        priority = "inspect_actuator_feedback" if mismatch else "inspect_airflow_path"
        self.work_order(req, resource["ri"], 4, priority, "verified_independent_sample",
                        requested_pct=req["requested_pct"], sample=response["sample"],
                        provider_receipt=response["provider_receipt"], **detail)

    def scan(self):
        """Recover from missed callbacks by enumerating actual CINs under bound parents."""
        current = set()
        for stream in self.inputs:
            for path in self.children(stream):
                current.add(path)
                if path in self.seen:
                    continue
                try:
                    resource = self.cin(path)
                    value = read_content(resource)
                    if stream == "outcomes":
                        self.outcome(value, resource)
                    elif stream == "sensor_responses":
                        self.response(value, resource)
                    elif stream == "provider_requests":
                        if not self.commission(value, resource):
                            continue
                    elif not self.serve_request(value, resource):
                        continue
                except (KeyError, TypeError, ValueError, AttributeError) as exc:
                    self.health["rejections"] += 1
                    LOG.warning("Rejected %s resource %s (%s)", stream, path, type(exc).__name__)
                except CSEError as exc:
                    if exc.rsc == 4004:  # expired between discovery and retrieve
                        continue
                    raise
                self.seen.add(path)
        self.seen.intersection_update(current)
        self.health["scans"] += 1

    def run(self):
        server = ThreadingHTTPServer((self.config.get("listen_host", "127.0.0.1"),
                                      self.config.get("listen_port", 8080)), callback_handler(self))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            while not self.stop.is_set():
                self.wake.clear()
                try:
                    self.scan()
                    self.health["last_error"] = None
                except (CSEError, ValueError) as exc:
                    self.health["last_error"] = type(exc).__name__
                    LOG.warning("CSE reconciliation deferred (%s)", type(exc).__name__)
                self.wake.wait(self.config.get("poll_seconds", 5))
        finally:
            server.shutdown()
            server.server_close()


def callback_handler(worker):
    class Receiver(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/health":
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(worker.health).encode())

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if self.path != "/notify" or not 0 < length <= 65536:
                    raise ValueError
                if not isinstance(json.loads(self.rfile.read(length))["m2m:sgn"], dict):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                return self.send_error(400)
            # An untrusted callback can only wake reconciliation of configured CSE parents.
            worker.health["notifications"] += 1
            worker.wake.set()
            self.send_response(200)
            self.send_header("X-M2M-RSC", "2000")
            self.send_header("X-M2M-RI", self.headers.get("X-M2M-RI", ""))
            self.send_header("X-M2M-RVI", "4")
            self.end_headers()

        def log_message(self, *_):
            pass

    return Receiver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=["maintenance", "bridge"], nargs="?", default=os.getenv("OPENSOOM_WORKER_ROLE"))
    parser.add_argument("--config", type=Path, default=os.getenv("OPENSOOM_WORKER_CONFIG"))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    encoded = os.getenv("OPENSOOM_WORKER_CONFIG_B64")
    if args.config:
        config = json.loads(args.config.read_text())
    elif encoded:
        # The Sandbox scenario environment is comma-separated and splits on '='.
        config = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    elif os.getenv("OPENSOOM_WORKER_CONFIG_JSON"):
        config = json.loads(os.environ["OPENSOOM_WORKER_CONFIG_JSON"])
    else:
        parser.error("Supply --config, OPENSOOM_WORKER_CONFIG_JSON or OPENSOOM_WORKER_CONFIG_B64")
    if not args.role:
        parser.error("Supply a worker role")
    worker = MaintenanceWorker(args.role, config)
    def stop(*_):
        worker.stop.set()
        worker.wake.set()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        worker.scan() if args.once else worker.run()
    finally:
        worker.close()


if __name__ == "__main__":
    main()
