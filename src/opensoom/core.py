from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema

from . import scenario_authoring
from . import maintenance
from .adapters import encode_virtual, normalize
from .models import ActionRequest, Observation, utcnow
from .onem2m import CSEClient, CSEError, MQTTCSEClient
from .policy import diagnose
from .store import Store

ROOT = Path(__file__).resolve().parents[2]
UNITS = {"pm25": "µg/m³", "co2": "ppm", "airflow": "m³/h", "fan_running": "boolean", "damper_pct": "%"}


class OperationError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class Core:
    def __init__(self, runtime: Path | None = None, cse: CSEClient | None = None):
        self.runtime = runtime or Path(os.environ.get("OPENSOOM_RUNTIME_DIR", str(ROOT / ".runtime")))
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.store = Store(self.runtime / "operations.sqlite")
        self.lock = threading.RLock()
        self.cse = cse or CSEClient(os.environ.get("OPENSOOM_CSE_URL", "http://127.0.0.1:8080"), ca_file=os.environ.get("OPENSOOM_CSE_CA"), trace_path=self.runtime / "cse-requests.jsonl")
        self.base = os.environ.get("OPENSOOM_CSE_BASE", "cse-in").strip("/")
        self.root = self.base + "/opensoom"
        self.notify_url = os.environ.get("OPENSOOM_NOTIFY_URL", "http://127.0.0.1:8090/api/notify")
        self.profiles = self.load_profiles()
        self.registry = self.load_registry(self.profiles)
        self.connected = False
        self.last_error: str | None = None
        self.identities = self.store.get("config", "identities", {})
        self.mqtt = None
        self.stop_event = threading.Event()

    @staticmethod
    def load_profiles():
        schema = json.loads((ROOT / "schemas/facility-profile.schema.json").read_text())
        profiles = {}
        for path in sorted((ROOT / "profiles").glob("*.json")):
            profile = json.loads(path.read_text())
            jsonschema.validate(profile, schema)
            if len({z["id"] for z in profile["zones"]}) != len(profile["zones"]):
                raise ValueError("Duplicate zone identity")
            profiles[profile["id"]] = profile
        return profiles

    @staticmethod
    def load_registry(profiles):
        configuration = json.loads((ROOT / "config/facilities.json").read_text())
        jsonschema.validate(configuration, json.loads((ROOT / "schemas/facilities.schema.json").read_text()))
        entries = configuration["facilities"]
        if len({item["id"] for item in entries}) != len(entries):
            raise ValueError("Duplicate facility identity")
        if any(item["profile"] not in profiles for item in entries):
            raise ValueError("Configured facility references an unknown profile")
        for item in entries:
            assets = item.get("maintenance", {}).get("assets", {})
            zones = {zone["id"] for zone in profiles[item["profile"]]["zones"]}
            if assets.keys() - zones:
                raise ValueError("Maintenance asset refers to an unknown zone")
            for field in ("asset_id", "sensor_id"):
                if len({mapping[field] for mapping in assets.values()}) != len(assets):
                    raise ValueError("Ambiguous maintenance sensor-to-asset assignment")
        selected = os.environ.get("OPENSOOM_FACILITY_IDS")
        if selected:
            identifiers = {value.strip() for value in selected.split(",")}
            if identifiers - {item["id"] for item in entries}:
                raise ValueError("Selected facility is not configured")
            entries = [item for item in entries if item["id"] in identifiers]
        return {item["id"]: item for item in entries}

    def actor_facilities(self, role):
        return [fid for fid, item in self.registry.items() if role != "observer" or role in item["read_only_roles"]]

    def log(self, kind, message, facility_id=None, zone_id=None, run_id=None, **data):
        return self.store.event({"timestamp": utcnow(), "type": kind, "message": message, "facility_id": facility_id, "zone_id": zone_id, "run_id": run_id, "data": data})

    def ensure(self, parent, ty, tag, attrs):
        path = parent.rstrip("/") + "/" + attrs["rn"]
        try:
            result = self.cse.create(parent, ty, {tag: attrs}, origin="C" + attrs["rn"].replace("-", "") if ty == 2 else None)
        except CSEError as exc:
            if exc.rsc not in (4105, 4117):
                raise
            result = self.cse.retrieve(path)
        return path, next(iter(result["body"].values())), result

    def bootstrap(self):
        with self.lock:
            self.cse.retrieve(self.base)
            self.ensure(self.base, 2, "m2m:ae", {"rn": "opensoom", "api": "N.org.opensoom.core", "rr": False, "srv": ["4"], "lbl": ["opensoom", "operations-core"]})
            for role in ("adapter", "diagnostic", "operator", "maintenance", "observer"):
                _, ae, _ = self.ensure(self.base, 2, "m2m:ae", {"rn": "os-" + role, "api": "N.org.opensoom." + role, "rr": False, "srv": ["4"], "lbl": ["opensoom", role]})
                self.identities[role] = ae["aei"]
            self.store.put("config", "identities", self.identities)
            self.ensure(self.root, 3, "m2m:cnt", {"rn": "facilities", "lbl": ["opensoom:facilities"]})
            previous_sites = [key.split(":", 1)[1] for key in self.identities if key.startswith("maintenance:")]
            for fid in previous_sites:
                if fid not in self.registry:
                    maintenance.disable_streams(self, fid)
            for fid, item in self.registry.items():
                self.setup_facility(fid, item["name"], item["profile"], item["adapter"])
            self.store.put("config", "identities", self.identities)
            if os.environ.get("OPENSOOM_MQTT_HOST") and self.mqtt is None:
                self.mqtt = MQTTCSEClient(os.environ["OPENSOOM_MQTT_HOST"], os.environ.get("OPENSOOM_MQTT_CSE_ID", "opensoom-secure"), self.identities["adapter"], os.environ["OPENSOOM_CSE_CA"], port=int(os.environ.get("OPENSOOM_MQTT_PORT", "8883")), trace_path=self.runtime / "mqtt-requests.jsonl")
            self.connected = True
            self.last_error = None
            self.log("runtime", "Actual oneM2M CSE connected; facility resources are ready")
            return self.doctor()

    def setup_facility(self, fid, name, profile_id, adapter):
        profile = self.profiles[profile_id]
        # Local CSE transport trusts this service; ACP still enforces distinct AEs.
        all_readers = [self.identities[r] for r in ("adapter", "diagnostic", "operator", "maintenance")]
        central_origin = os.environ.get("OPENSOOM_CENTRAL_ORIGIN")
        if central_origin:
            all_readers.append(central_origin)
        if "observer" in self.registry[fid]["read_only_roles"]:
            all_readers.append(self.identities["observer"])
        workers = maintenance.register_workers(self, fid) if "maintenance" in self.registry[fid] else {}
        policies = {}
        for kind, writers, permissions in (("structure", [], 0), ("observations", [self.identities["adapter"]], 5), ("commands", [self.identities["operator"]], 1), ("acks", [self.identities["adapter"]], 1)):
            readers = list(all_readers)
            if workers and kind == "observations":
                readers.append(workers["maintenance"])
            rules = [{"acor": readers, "acop": 34}]
            if writers:
                rules.append({"acor": writers, "acop": permissions})
            policies[kind] = maintenance.create_policy(self, fid, kind, rules)
        acp = {"ri": policies["structure"]}
        fpath, _, _ = self.ensure(self.root + "/facilities", 3, "m2m:cnt", {"rn": fid, "acpi": [acp["ri"]], "lbl": ["opensoom:facility", "facility:" + fid, "profile:" + profile_id]})
        if workers:
            maintenance.provision_streams(self, fid, fpath, workers)
        elif "maintenance:" + fid in self.identities:
            maintenance.disable_streams(self, fid)
        zones = []
        members = []
        for zone in profile["zones"]:
            zpath, _, _ = self.ensure(fpath, 3, "m2m:cnt", {"rn": zone["id"], "acpi": [acp["ri"]], "lbl": ["opensoom:zone", "zone:" + zone["id"]]})
            for container in ("observations", "commands", "acks"):
                path, res, _ = self.ensure(zpath, 3, "m2m:cnt", {"rn": container, "mni": 250, "acpi": [policies[container]], "lbl": ["opensoom:" + container, "facility:" + fid]})
                if res.get("acpi") != [policies[container]]:
                    self.cse.update(path, {"m2m:cnt": {"acpi": [policies[container]]}})
                if container == "observations":
                    members.append(res["ri"])
                    self.ensure(path, 23, "m2m:sub", {"rn": "diagnosis", "nu": [self.notify_url], "enc": {"net": [3]}, "nct": 1})
            standard_path, _, _ = self.ensure(self.root, 28, "cod:aiQSr", {"rn": fid + "-" + zone["id"] + "-air", "cnd": "org.onem2m.common.moduleclass.airQualitySensor", "acpi": [policies["observations"]], "lbl": ["opensoom:sdt", "facility:" + fid, "zone:" + zone["id"], "unobserved"]})
            zones.append({**zone, "path": zpath, "standard_path": standard_path})
        self.ensure(self.root, 9, "m2m:grp", {"rn": fid + "-zone-observations", "mt": 3, "mnm": len(members), "mid": members, "acpi": [acp["ri"]], "lbl": ["facility:" + fid]})
        previous = self.store.get("facilities", fid, {})
        self.store.put("facilities", fid, {"id": fid, "name": name, "profile": profile_id, "profile_version": profile["schema_version"], "adapter": adapter, "path": fpath, "zones": zones, "scenario": previous.get("scenario", "normal"), "active_run": previous.get("active_run"), "simulated": True, "controls_enabled": True})

    def facility(self, fid):
        value = self.store.get("facilities", fid)
        if fid not in self.registry or not value:
            raise OperationError("unknown_facility", "Facility is not configured", 404)
        return value

    def zone(self, facility, zid):
        for zone in facility["zones"]:
            if zone["id"] == zid:
                return zone
        raise OperationError("unknown_zone", "Zone is not configured", 404)

    def authorize(self, principal, fid=None, action=None):
        role = principal["role"]
        if fid and fid not in principal["facilities"] and role != "admin":
            raise OperationError("facility_denied", "This identity cannot access the requested facility", 403)
        if action and role not in ("operator", "maintenance", "admin"):
            raise OperationError("action_denied", "This identity is read-only", 403)
        if action == "set_damper" and role == "maintenance":
            raise OperationError("action_denied", "Maintenance identity cannot change dampers", 403)

    def create_content(self, path, content, origin):
        client = self.mqtt if self.mqtt and origin == self.identities.get("adapter") else self.cse
        return client.create(path, 4, {"m2m:cin": {"con": json.dumps(content, ensure_ascii=False), "cnf": "application/json:0"}}, origin=origin)

    def publish(self, observation: Observation):
        facility = self.facility(observation.facility_id)
        zone = self.zone(facility, observation.zone_id)
        result = self.create_content(zone["path"] + "/observations", observation.model_dump(), self.identities["adapter"])
        if observation.pm25 is not None:
            # TS-0023 v5.6.0 airQualitySensor.pm25 is integer µg/m³.
            # Its co2 is mg/m³: never insert our ppm into that attribute.
            client = self.mqtt or self.cse
            client.update(zone["standard_path"], {"cod:aiQSr": {"pm25": round(observation.pm25), "lbl": ["opensoom:sdt", "facility:" + facility["id"], "zone:" + zone["id"], "simulated"]}}, origin=self.identities["adapter"])
        # Re-read authoritative CSE state. Notifications also trigger this path.
        self.refresh_observation(facility["id"], zone["id"])
        return result

    def refresh_observation(self, fid, zid):
        # Serialize the CSE read as well as the commit. A delayed callback must
        # not replace a newer observation retrieved by a concurrent publisher.
        with self.lock:
            return self._refresh_observation(fid, zid)

    def _refresh_observation(self, fid, zid):
        facility = self.facility(fid)
        zone = self.zone(facility, zid)
        result = self.cse.retrieve(zone["path"] + "/observations/la", origin=self.identities["diagnostic"])
        cin = result["body"]["m2m:cin"]
        content = json.loads(cin["con"]) if isinstance(cin["con"], str) else cin["con"]
        observation = Observation.model_validate(content)
        if observation.facility_id != fid or observation.zone_id != zid:
            raise OperationError("observation_identity_mismatch", "CSE observation identity does not match its resource", 409)
        with self.store.transaction():
            previous = self.store.get("observations", fid + ":" + zid)
            if previous and previous.get("cin_id") == cin["ri"]:
                return previous
            record = {"observation": observation.model_dump(), "cin_id": cin["ri"], "source_cin_path": zone["path"] + "/observations/" + cin["rn"], "rqi": result["rqi"], "cse_path": zone["path"] + "/observations/la"}
            self.store.put("observations", fid + ":" + zid, record)
            self.evaluate(observation, facility, zone, result["rqi"])
            return record

    def notification(self, payload):
        signal = payload.get("m2m:sgn", {})
        if signal.get("vrq"):
            return
        try:
            cin = signal["nev"]["rep"]["m2m:cin"]
            content = json.loads(cin["con"]) if isinstance(cin["con"], str) else cin["con"]
            # Payload is only a hint. Validate configured identities and fetch from CSE.
            observation = Observation.model_validate(content)
            self.refresh_observation(observation.facility_id, observation.zone_id)
            self.store.put("config", "last_notification", {"at": utcnow(), "subscription": signal.get("sur"), "cin_id": cin.get("ri")})
        except (KeyError, ValueError, OperationError, CSEError):
            self.log("notification_rejected", "Notification could not be corroborated with CSE observation")

    def evaluate(self, observation, facility, zone, rqi):
        profile = self.profiles[facility["profile"]]
        diagnosis = diagnose(observation, zone, profile)
        key = facility["id"] + ":" + zone["id"]
        incident = self.store.get("incidents", key)
        run_id = facility.get("active_run")
        if diagnosis["status"] != "nominal":
            if not incident or incident["status"] == "resolved":
                incident = {"id": "incident-" + uuid.uuid4().hex[:10], "facility_id": facility["id"], "zone_id": zone["id"], "title": "Verify " + zone["name"].lower() + " ventilation", "status": "open", "created_at": utcnow(), "recovery_count": 0}
                self.log("incident_opened", diagnosis["reason"], facility["id"], zone["id"], run_id, rqi=rqi)
            if diagnosis["status"] == "critical" and not incident.get("maintenance_opened"):
                incident["maintenance_opened"] = maintenance.queue_outcome(self, "incident.opened", incident, observation, facility, zone, rqi)
            incident.update(reason=diagnosis["reason"], severity=diagnosis["status"], recovery_count=0, updated_at=utcnow(), latest_rqi=rqi)
            self.store.put("incidents", key, incident)
            if diagnosis["status"] == "critical":
                for command in self.store.list("commands"):
                    if command.get("incident_id") == incident["id"] and command.get("ack_at") and command["action"] == "set_damper" and datetime.fromisoformat(observation.observed_at) > datetime.fromisoformat(command["ack_at"]):
                        command["unresolved_samples"] = command.get("unresolved_samples", 0) + 1
                        if command["unresolved_samples"] >= profile["recovery_samples"]:
                            if command.get("observed_result") != "unresolved":
                                maintenance.queue_outcome(self, "command.unresolved_after_ack", incident, observation, facility, zone, rqi, command)
                            command.update(status="unresolved", observed_result="unresolved", verification_rqi=rqi)
                        self.store.put("commands", command["id"], command)
        elif incident and incident["status"] != "resolved":
            acknowledged = [c for c in self.store.list("commands") if c["facility_id"] == facility["id"] and c["zone_id"] == zone["id"] and c.get("ack") and c["action"] == "set_damper" and c.get("incident_id") == incident["id"] and datetime.fromisoformat(observation.observed_at) > datetime.fromisoformat(c["ack_at"])]
            if acknowledged:
                incident["recovery_count"] += 1
                incident["status"] = "recovering"
                if incident["recovery_count"] >= profile["recovery_samples"]:
                    incident.update(status="resolved", resolved_at=utcnow(), reason="Two fresh post-ACK samples meet this profile's simulated operating targets")
                    for command in acknowledged:
                        command.update(status="verified", observed_result="recovered", verified_at=utcnow(), verification_rqi=rqi)
                        self.store.put("commands", command["id"], command)
                    self.log("recovery_verified", "Fresh observations verify recovery after device acknowledgement", facility["id"], zone["id"], run_id, rqi=rqi)
                self.store.put("incidents", key, incident)

    def tool(self, name, arguments, principal, run_id=None):
        args = dict(arguments)
        fid = args.get("facility_id")
        self.authorize(principal, fid)
        if run_id:
            run = self.store.get("runs", run_id)
            if not run or (fid and run["facility_id"] != fid):
                raise OperationError("run_scope", "Run does not match the requested facility", 403)
            if run.get("principal_role") != principal["role"]:
                raise OperationError("run_owner_required", "Only the owning identity can append operations to this run", 403)
        if name in ("save_scenario", "run_scenario", "read_scenario_run"):
            result = scenario_authoring.dispatch(self, name, args, principal, run_id, OperationError)
        elif name in ("commission_provider", "read_provider_result"):
            if principal["role"] != "admin":
                raise OperationError("admin_required", "Sensor provider commissioning requires the site administrator", 403)
            result = maintenance.commission(self, name, args, OperationError)
        elif name == "doctor":
            result = self.doctor()
        elif name == "prepare_setup":
            profile_id = args.get("profile_id", "food-production")
            if profile_id not in self.profiles:
                raise OperationError("unknown_profile", "Choose a bundled profile", 404)
            result = {"profile": self.profiles[profile_id], "configured_facilities": [fid for fid, item in self.registry.items() if item["profile"] == profile_id and fid in principal["facilities"]], "mode": "virtual", "activation_requires": "administrator", "runtime": self.doctor()}
        elif name == "apply_setup":
            if principal["role"] != "admin":
                raise OperationError("admin_required", "Profile activation requires the configured administrator", 403)
            profile_id = args.get("profile_id")
            if profile_id not in self.profiles:
                raise OperationError("unknown_profile", "Choose a bundled profile", 404)
            targets = [(fid, item) for fid, item in self.registry.items() if item["profile"] == profile_id]
            if not targets:
                raise OperationError("setup_required", "Assign this profile in config/facilities.json before activation", 409)
            for fid, item in targets:
                self.setup_facility(fid, item["name"], profile_id, item["adapter"])
            result = {"profile_id": profile_id, "activated_facilities": [fid for fid, _ in targets], "runtime": self.doctor()}
        elif name == "discover":
            items = [f for f in self.store.list("facilities") if f["id"] in self.registry and
                     (principal["role"] == "admin" or f["id"] in principal["facilities"])]
            if fid:
                items = [self.facility(fid)]
            origin = self.identities.get(principal["role"], "CAdmin")
            queries = [self.cse.discover(f["path"], {"ty": 3}, origin=origin) for f in items]
            standards = [self.cse.discover(self.root, {"ty": 28, "lbl": "facility:" + f["id"]}, origin=origin) for f in items]
            result = {"facilities": [{"id": f["id"], "name": f["name"], "profile": f["profile"], "zones": [{"id": z["id"], "name": z["name"]} for z in f["zones"]]} for f in items], "cse_discovery": queries, "standard_model_discovery": standards}
        elif name == "read_group":
            facility = self.facility(fid)
            origin = self.identities.get(principal["role"], "CAdmin")
            try:
                group = self.cse.retrieve(self.root + "/" + fid + "-zone-observations/fopt/la", origin=origin)
                result = {"facility_id": fid, "group": group, "status": "ok", "note": "Native fan-out returns latest observations; CSE results do not prove device execution."}
            except CSEError as exc:
                # ACME can abort a fan-out on one denied member. Retain native
                # error and label separate diagnostic reads rather than inventing
                # native per-member success or treating group failure as empty.
                members = []
                for zone in facility["zones"]:
                    try:
                        check = self.cse.retrieve(zone["path"] + "/observations/la", origin=origin)
                    except CSEError as member_error:
                        check = member_error.result
                    members.append({"zone_id": zone["id"], "response": check})
                result = {"facility_id": fid, "status": "group_not_confirmed", "group_error": exc.result, "individual_diagnostic_reads": members, "note": "Separate reads after native group failure; not a fabricated fan-out aggregate."}
        elif name == "read_evidence":
            facility = self.facility(fid)
            zid = args.get("zone_id")
            zones = [self.zone(facility, zid)] if zid else facility["zones"]
            for zone in zones:
                try:
                    self.refresh_observation(fid, zone["id"])
                except CSEError as exc:
                    if exc.rsc != 4004:
                        raise
            result = self.facility_view(facility)
            result["incidents"] = [i for i in self.store.list("incidents") if i["facility_id"] == fid]
            result["commands"] = [c for c in self.store.list("commands") if c["facility_id"] == fid and c.get("run_id") == (run_id or facility.get("active_run"))][-10:]
            result["current_run_id"] = run_id or facility.get("active_run")
            result["evidence_scope"] = {
                "incidents": "All stored incidents for this facility, across runs.",
                "commands": {"run_id": result["current_run_id"], "limit": 10,
                             "complete_facility_history": False,
                             "meaning": "Only the latest 10 stored commands belonging to this run. An empty list does not rule out actions or ACKs in other runs."},
                "recovery_count": {"unit": "consecutive_qualifying_post_ack_observations",
                                   "scope": "incident", "required": self.profiles[facility["profile"]]["recovery_samples"],
                                   "counts_action_attempts": False,
                                   "meaning": "Consecutive qualifying healthy observations after an acknowledged command; resets to zero for a non-nominal observation, including critical, stale or missing. This is not a count of attempted actions, ACKs or recovered incidents."},
                "diagnosis": "Use each zone's reason and configured targets: deficient airflow is below its minimum; excessive PM2.5 and CO2 are above their limits. These are simulation targets, not certified safety limits.",
            }
            result["standard_models"] = []
            for zone in zones:
                model = self.cse.retrieve(zone["standard_path"], origin=self.identities.get(principal["role"], "CAdmin"))
                attributes = model["body"].get("cod:aiQSr", {})
                result["standard_models"].append({"zone_id": zone["id"], "cnd": attributes.get("cnd"), "pm25": attributes.get("pm25"), "unit": "µg/m³", "specification": "oneM2M TS-0023 v5.6.0 5.3.1.6", "rqi": model["rqi"], "note": "Integer rounded value; full precision is retained in observations. CO₂ ppm is not mapped to the SDT mg/m³ field."})
        elif name == "request_action":
            request = ActionRequest.model_validate(args)
            result = self.request_action(request, principal, run_id)
        elif name == "verify_result":
            result = self.verify(args.get("command_id"), principal, fid, run_id)
        else:
            raise OperationError("unknown_tool", "Unknown operation", 404)
        self.log("tool_completed", name.replace("_", " "), fid, args.get("zone_id"), run_id, tool=name)
        if run_id:
            run = self.store.get("runs", run_id)
            entry = {"name": name, "at": utcnow(), "arguments": args, "result_status": result.get("status", "ok")}
            if name in ("save_scenario", "run_scenario", "read_scenario_run"):
                entry["scenario_receipt"] = {key: result[key] for key in ("version", "execution_id") if key in result}
                if result.get("readback"):
                    entry["scenario_receipt"]["readback_rqi"] = result["readback"]["rqi"]
            run["tool_calls"] = run.get("tool_calls", []) + [entry]
            self.store.put("runs", run_id, run)
        return result

    def request_action(self, request, principal, run_id=None):
        self.authorize(principal, request.facility_id, request.action)
        facility = self.facility(request.facility_id)
        zone = self.zone(facility, request.zone_id)
        profile = self.profiles[facility["profile"]]
        if not facility["simulated"] or not facility["controls_enabled"]:
            raise OperationError("observe_only", "This facility has no enabled control profile", 403)
        if request.action not in profile["allowed_actions"]:
            raise OperationError("action_denied", "Action is outside the activated profile", 403)
        with self.lock:
            for command in self.store.list("commands"):
                if command["request_id"] == request.request_id:
                    if command.get("run_id") != (run_id or facility.get("active_run")):
                        raise OperationError("request_scope", "Request ID belongs to another run; use this run's unique intent ID", 409)
                    comparable = {k: command.get(k) for k in ("facility_id", "zone_id", "action", "value", "reason")}
                    if comparable != request.model_dump(include=set(comparable)):
                        raise OperationError("idempotency_conflict", "Request ID already belongs to different action arguments", 409)
                    return command
            if request.action == "set_damper":
                if request.value is None:
                    raise OperationError("missing_value", "Damper percentage is required")
                record = self.refresh_observation(facility["id"], zone["id"])
                diagnosis = diagnose(Observation.model_validate(record["observation"]), zone, profile)
                if diagnosis["status"] in ("stale", "missing"):
                    raise OperationError("evidence_not_current", diagnosis["reason"], 409)
            command_id = "cmd-" + uuid.uuid4().hex[:12]
            now = datetime.now(timezone.utc)
            incident = self.store.get("incidents", facility["id"] + ":" + zone["id"], {})
            command = {**request.model_dump(), "id": command_id, "status": "requested", "ack": False, "created_at": now.isoformat(), "expires_at": (now + timedelta(seconds=profile["command_ttl_seconds"])).isoformat(), "profile_version": profile["schema_version"], "run_id": run_id or facility.get("active_run"), "incident_id": incident.get("id"), "observed_result": "pending"}
            result = self.create_content(zone["path"] + "/commands", command, self.identities["operator"])
            command.update(cse_rqi=result["rqi"], cse_resource_id=result["body"]["m2m:cin"]["ri"])
            self.store.put("commands", command_id, command)
            self.log("command_requested", "Maintenance requested" if request.action == "request_maintenance" else f"Damper adjustment requested: {request.value:g}%", facility["id"], zone["id"], command["run_id"], command_id=command_id, rqi=result["rqi"])
            return command

    def verify(self, command_id, principal, fid=None, run_id=None):
        command = self.store.get("commands", command_id)
        if not command:
            raise OperationError("unknown_command", "Command was not found", 404)
        self.authorize(principal, command["facility_id"])
        if fid and command["facility_id"] != fid:
            raise OperationError("command_scope", "Command belongs to another facility", 403)
        if run_id and command.get("run_id") != run_id:
            raise OperationError("command_scope", "Command belongs to another run", 409)
        self.refresh_observation(command["facility_id"], command["zone_id"])
        command = self.store.get("commands", command_id)
        if not command["ack"] and datetime.fromisoformat(command["expires_at"]) < datetime.now(timezone.utc):
            command.update(status="timed_out", observed_result="unresolved")
            self.store.put("commands", command_id, command)
        facility = self.facility(command["facility_id"])
        observation = next(z for z in self.facility_view(facility)["zones"] if z["id"] == command["zone_id"])
        return {**command, "command_id": command["id"], "complete": command["status"] == "verified", "outcome": "recovered" if command["status"] == "verified" else ("unresolved" if command["observed_result"] == "unresolved" or command["status"] in ("timed_out", "maintenance_recorded") else "pending"), "observations": observation["observations"], "message": "Result verified from later CSE observations" if command["status"] == "verified" else "CSE acceptance/ACK alone does not establish recovery"}

    def acknowledge_pending(self, facility, only_command_id=None):
        for command in self.store.list("commands"):
            if only_command_id and command["id"] != only_command_id:
                continue
            if command["facility_id"] != facility["id"] or command["status"] != "requested":
                continue
            if datetime.fromisoformat(command["expires_at"]) < datetime.now(timezone.utc):
                command.update(status="timed_out", observed_result="unresolved")
                self.store.put("commands", command["id"], command)
                continue
            if only_command_id is None and facility["scenario"] == "missing_ack":
                continue
            zone = self.zone(facility, command["zone_id"])
            # Virtual adapter reads the actual CSE command before acting.
            result = self.cse.retrieve(command["cse_resource_id"], origin=self.identities["adapter"])
            raw = result["body"]["m2m:cin"]["con"]
            actual = json.loads(raw) if isinstance(raw, str) else raw
            if actual["id"] != command["id"] or actual["profile_version"] != facility["profile_version"]:
                continue
            ack = {"command_id": command["id"], "facility_id": facility["id"], "zone_id": command["zone_id"], "ack_at": utcnow(), "simulated": True, "device_state": "maintenance_recorded" if command["action"] == "request_maintenance" else "damper_changed", "value": command["value"]}
            ack_result = self.create_content(zone["path"] + "/acks", ack, self.identities["adapter"])
            command.update(ack=True, ack_at=ack["ack_at"], ack_rqi=ack_result["rqi"], status="acknowledged", observed_result="awaiting_observations")
            if command["action"] == "request_maintenance":
                command.update(status="maintenance_recorded", observed_result="unresolved")
            self.store.put("commands", command["id"], command)
            self.log("device_ack", "Virtual device acknowledged; recovery still requires observations", facility["id"], zone["id"], command.get("run_id"), command_id=command["id"], rqi=ack_result["rqi"])

    def sample_facility(self, facility):
        self.acknowledge_pending(facility)
        scenario = facility["scenario"]
        commands = self.store.list("commands")
        for index, zone in enumerate(facility["zones"]):
            faulty = index == 0 and scenario != "normal"
            started_at = self.store.get("runs", facility.get("active_run"), {}).get("started_at", "9999")
            applied = [c for c in commands if c["facility_id"] == facility["id"] and c["zone_id"] == zone["id"] and c["action"] == "set_damper" and c.get("ack") and c["created_at"] >= started_at]
            damper = float(applied[-1]["value"]) if applied else (35.0 if faulty else 70.0)
            # Deterministic device model, not a physical airflow equation:
            # an acknowledged setpoint must become the reported device state.
            # Partial/closed requests cannot borrow a full-open recovery.
            flow_ratio = 1.15 * damper / 100 if applied else (0.4 if faulty else 1.15)
            if faulty and scenario == "no_recovery":
                flow_ratio = min(flow_ratio, 0.4)
            deficient = flow_ratio < 1
            values = {"observed_at": utcnow(), "pm25": 62.0 if deficient else 12.0, "co2": 1450.0 if deficient else 620.0, "airflow": zone["minimum_airflow"] * flow_ratio, "fan_running": True, "damper_pct": damper}
            if index == 0 and scenario == "stale":
                values["observed_at"] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            if index == 0 and scenario == "missing":
                values["airflow"] = None
            observation = normalize(encode_virtual(values, facility["adapter"]), facility["adapter"], facility["id"], zone["id"])
            self.publish(observation)

    def tick(self):
        for facility in self.store.list("facilities"):
            if facility["id"] not in self.registry or not facility.get("active_run"):
                continue
            try:
                self.sample_facility(facility)
                self.finish_demo_if_observed(facility)
                self.connected, self.last_error = True, None
            except (CSEError, OperationError, ValueError) as exc:
                self.connected, self.last_error = False, type(exc).__name__
                self.log("runtime_error", "Observation update could not be verified against CSE", facility["id"], run_id=facility.get("active_run"), error=type(exc).__name__)

    def start_demo(self, fid, scenario, autorun, principal):
        with self.lock:
            return self._start_demo(fid, scenario, autorun, principal)

    def _start_demo(self, fid, scenario, autorun, principal):
        self.authorize(principal, fid, "set_damper")
        if scenario not in {s["id"] for s in json.loads((ROOT / "scenarios/scenarios.json").read_text())["cases"]}:
            raise OperationError("unknown_scenario", "Choose a supported scenario")
        facility = self.facility(fid)
        run_id = "demo-" + uuid.uuid4().hex[:10]
        facility.update(scenario=scenario, active_run=run_id)
        # Archive previous incidents so scenarios do not borrow earlier ACKs.
        for zone in facility["zones"]:
            key = fid + ":" + zone["id"]
            incident = self.store.get("incidents", key)
            if incident:
                self.store.put("incident_history", incident["id"], {**incident, "archived_at": utcnow()})
                self.store.delete("incidents", key)
        self.store.put("facilities", fid, facility)
        self.store.put("runs", run_id, {"id": run_id, "facility_id": fid, "principal_role": principal["role"], "scenario": scenario, "mode": "fixture" if autorun else "interactive", "status": "running", "started_at": utcnow(), "steps": [], "tool_calls": []})
        self.log("scenario_started", scenario.replace("_", " ").capitalize() + " · virtual equipment", fid, run_id=run_id)
        self.sample_facility(facility)
        if autorun and scenario not in ("normal", "stale", "missing"):
            self.request_action(ActionRequest(facility_id=fid, zone_id=facility["zones"][0]["id"], action="set_damper", value=100, reason="Preauthorized deterministic demonstration", request_id=run_id + ":damper"), principal, run_id)
        return {"run_id": run_id, "status": "running", "mode": "fixture" if autorun else "interactive"}

    def finish_demo_if_observed(self, facility):
        run = self.store.get("runs", facility.get("active_run"))
        if not run or run["status"] != "running" or run["mode"] not in ("fixture", "interactive"):
            return
        commands = [c for c in self.store.list("commands") if c.get("run_id") == run["id"]]
        scenario = facility["scenario"]
        expected = None
        if scenario == "normal" and self.facility_view(facility)["status"] == "nominal":
            expected = "normal_observations"
        elif scenario in ("stale", "missing") and self.facility_view(facility)["status"] == scenario:
            expected = "unsafe_evidence_remains_unresolved"
        elif any(c["status"] == "verified" for c in commands):
            expected = "ack_and_post_action_recovery"
        elif scenario == "missing_ack" and any(c["status"] == "timed_out" for c in commands):
            expected = "missing_ack_remains_unresolved"
        elif scenario == "no_recovery" and any(c["status"] == "unresolved" and c.get("unresolved_samples", 0) >= 2 for c in commands):
            expected = "ack_without_recovery_remains_unresolved"
        if expected:
            run.update(status="completed", outcome="PASS_FIXTURE" if run["mode"] == "fixture" else "OBSERVED", expected_behavior=expected, completed_at=utcnow(), command_ids=[c["id"] for c in commands], steps=[e for e in self.store.events() if e.get("run_id") == run["id"]])
            self.store.put("runs", run["id"], run)

    def facility_view(self, facility):
        zones = []
        for zone in facility["zones"]:
            row = self.store.get("observations", facility["id"] + ":" + zone["id"])
            item = {"id": zone["id"], "name": zone["name"], "target_airflow": zone["minimum_airflow"], "observations": {}, "status": "missing", "freshness": None}
            if row:
                obs = Observation.model_validate(row["observation"])
                result = diagnose(obs, zone, self.profiles[facility["profile"]])
                item.update(status=result["status"], freshness=result["freshness"], reason=result["reason"], cse_rqi=row["rqi"])
                for key, unit in UNITS.items():
                    val = getattr(obs, key)
                    item["observations"][key] = {"value": val, "unit": unit, "observed_at": obs.observed_at, "received_at": obs.received_at, "source": "simulated", "quality": "missing" if val is None else ("stale" if result["status"] == "stale" else "good")}
            zones.append(item)
        statuses = [z["status"] for z in zones]
        status = next((s for s in ("critical", "missing", "stale") if s in statuses), "nominal")
        return {**{k: facility[k] for k in ("id", "name", "profile", "adapter", "scenario", "active_run")}, "maintenance_enabled": "maintenance" in self.registry[facility["id"]], "zones": zones, "status": status, "simulation": True, "controls_enabled": facility["controls_enabled"]}

    def state(self, principal):
        facilities = [self.facility_view(f) for f in self.store.list("facilities")
                      if f["id"] in self.registry and (principal["role"] == "admin" or f["id"] in principal["facilities"])]
        allowed = {f["id"] for f in facilities}
        incidents = [i for i in self.store.list("incidents") if i["facility_id"] in allowed]
        commands = [c for c in self.store.list("commands") if c["facility_id"] in allowed][-40:]
        orders = [order for fid in sorted(allowed) if "maintenance" in self.registry[fid] for order in self.store.get("work_order_projection", fid, [])]
        return {"facilities": facilities, "work_orders": orders, "selected_facility": facilities[0]["id"] if facilities else None, "incidents": incidents, "commands": commands, "events": [e for e in self.store.events() if not e.get("facility_id") or e["facility_id"] in allowed], "runs": [r for r in self.store.list("runs") if r["facility_id"] in allowed][-15:], "runtime": {"cse_connected": self.connected, "cse_name": "ACME oneM2M", "simulation": True, "last_error": self.last_error, "last_notification": self.store.get("config", "last_notification")}, "summary": {"active_incidents": sum(i["status"] != "resolved" for i in incidents), "pending_commands": sum(c["status"] == "requested" for c in commands), "recovered_incidents": sum(i["status"] == "resolved" and i.get("resolved_at") is not None for i in incidents), "fresh_zones": sum(z["status"] not in ("stale", "missing") for f in facilities for z in f["zones"]), "total_zones": sum(len(f["zones"]) for f in facilities)}}

    def doctor(self):
        try:
            check = self.cse.retrieve(self.base)
            self.connected = True
            cse_status = {"connected": True, "rsc": check["rsc"], "rqi": check["rqi"], "base": self.base}
        except CSEError as exc:
            self.connected = False
            cse_status = {"connected": False, "error": str(exc), "next_step": "Start the bundled CSE runtime"}
        return {"status": "ready" if self.connected and self.store.list("facilities") else "not_ready", "cse": cse_status, "profiles": list(self.profiles), "simulation": True, "persistent_state": True, "physical_devices_supported": False}
