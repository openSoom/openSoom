"""oneM2M resources linking site decisions to independent maintenance applications."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .onem2m import CSEError
from .maintenance_worker import key


def commission(core, operation, args, error):
    fid = args.get("facility_id")
    facility = core.facility(fid)
    profile = args.get("provider_profile")
    request_id = args.get("request_id")
    allowed = core.registry[fid].get("maintenance", {}).get("provider_profiles", [])
    if set(args) != {"facility_id", "provider_profile", "request_id"} or not isinstance(request_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", request_id):
        raise error("invalid_request", "Use a facility, configured provider profile and stable request identifier", 422)
    if profile not in allowed:
        raise error("unknown_provider", "This provider is not configured for this facility", 403)
    path = facility["path"] + "/provider_requests"
    origin = core.identities["operator"]
    desired = {"kind": "provider.enable", "request_id": request_id, "facility_id": fid, "provider_profile": profile}
    if operation == "commission_provider":
        record = {**desired, "requested_at": datetime.now(timezone.utc).isoformat()}
        try:
            core.cse.create(path, 4, {"m2m:cin": {"rn": request_id, "con": json.dumps(record), "cnf": "application/json:0"}}, origin=origin)
        except CSEError as exc:
            if exc.rsc != 4105:
                raise
    request = core.cse.retrieve(path + "/" + request_id, origin=origin)
    cin = request["body"]["m2m:cin"]
    actual = json.loads(cin["con"])
    if not all(actual.get(k) == value for k, value in desired.items()):
        raise error("request_id_conflict", "This request identifier belongs to a different provider request", 409)
    receipt = {"request_id": request_id, "request_ri": cin["ri"], "request_rqi": request["rqi"], "status": "pending"}
    result_path = facility["path"] + "/provider_responses/" + key("provider", cin["ri"])
    try:
        result = core.cse.retrieve(result_path, origin=origin)
    except CSEError as exc:
        if exc.rsc != 4004:
            raise
        return receipt
    cin = result["body"]["m2m:cin"]
    answer = json.loads(cin["con"])
    if (answer.get("kind") != "provider.result" or answer.get("request_ri") != receipt["request_ri"]
            or any(answer.get(k) != desired[k] for k in ("facility_id", "provider_profile", "request_id"))):
        raise error("provider_receipt_conflict", "Provider response does not match the original request", 409)
    return {**receipt, "status": answer["status"], "result": answer, "result_ri": cin["ri"], "result_rqi": result["rqi"]}


def create_policy(core, fid, name, rules):
    admin = {"acor": ["CAdmin"], "acop": 63}
    policy = {"pv": {"acr": [admin, *rules]}, "pvs": {"acr": [admin]}}
    path, resource, _ = core.ensure(core.root, 1, "m2m:acp", {"rn": f"acp-{fid}-{name}", **policy})
    if any(resource.get(key) != value for key, value in policy.items()):
        core.cse.update(path, {"m2m:acp": policy})
    return resource["ri"]


def register_workers(core, fid):
    identities = {}
    suffix = hashlib.sha256(fid.encode()).hexdigest()[:16]
    for role in ("maintenance", "bridge", "sensor"):
        _, ae, _ = core.ensure(core.base, 2, "m2m:ae", {
            "rn": f"os-{role}-{suffix}", "api": f"N.org.opensoom.{role}", "rr": False,
            "srv": ["4"], "lbl": ["opensoom", "facility:" + fid, role],
        })
        identities[role] = ae["aei"]
        core.identities[f"{role}:{fid}"] = ae["aei"]
    return identities


def provision_streams(core, fid, facility_path, workers):
    maintenance = workers["maintenance"]
    bridge = workers["bridge"]
    operator = core.identities["operator"]
    sensor = workers["sensor"]
    streams = {
        "outcomes": (operator, [operator, maintenance]),
        "work_orders": (maintenance, [maintenance, operator]),
        "sensor_requests": (maintenance, [maintenance, bridge]),
        "sensor_responses": (bridge, [bridge, maintenance]),
        "independent_samples": (sensor, [sensor, bridge]),
        "provider_requests": (operator, [operator, bridge]),
        "provider_responses": (bridge, [bridge, operator, maintenance]),
    }
    callbacks = json.loads(os.environ.get("OPENSOOM_WORKER_CALLBACKS", "{}")).get(fid, {})
    for name, (writer, readers) in streams.items():
        policy = create_policy(core, fid, name, [
            {"acor": readers, "acop": 34},
            {"acor": [writer], "acop": 1, "acod": [{"chty": [4]}]},
        ])
        path, container, _ = core.ensure(facility_path, 3, "m2m:cnt", {
            "rn": name, "mni": 1000, "acpi": [policy], "lbl": ["opensoom:" + name, "facility:" + fid],
        })
        if container.get("acpi") != [policy]:
            core.cse.update(path, {"m2m:cnt": {"acpi": [policy]}})
        receiver = {"outcomes": "maintenance", "sensor_responses": "maintenance",
                    "sensor_requests": "bridge", "provider_requests": "bridge"}.get(name)
        if receiver in callbacks:
            target = callbacks[receiver]
            if urlsplit(target).scheme not in ("http", "https"):
                raise ValueError("Worker callback requires HTTP or HTTPS")
            attrs = {"rn": "notify-" + receiver, "nu": [target], "enc": {"net": [3], "chty": [4]}, "nct": 1}
            subpath, sub, _ = core.ensure(path, 23, "m2m:sub", attrs)
            if sub["nu"] != [target]:
                core.cse.update(subpath, {"m2m:sub": {"nu": [target]}})


def disable_streams(core, fid):
    # Revoke old worker rights before returning a site to its operations-only profile.
    for name in ("outcomes", "work_orders", "sensor_requests", "sensor_responses", "independent_samples",
                 "provider_requests", "provider_responses"):
        create_policy(core, fid, name, [])
    installed = core.store.get("facilities", fid)
    if installed:
        for stream, role in (("outcomes", "maintenance"), ("sensor_requests", "bridge"),
                             ("sensor_responses", "maintenance"), ("provider_requests", "bridge")):
            try:
                core.cse.delete(installed["path"] + "/" + stream + "/notify-" + role)
            except CSEError as exc:
                if exc.rsc != 4004:
                    raise
    # An entire site can also be removed from the configuration. Its raw sensor
    # observations may still exist in the CSE and use the original facility ACP.
    path = core.root + "/acp-" + fid + "-observations"
    try:
        acp = core.cse.retrieve(path)["body"]["m2m:acp"]
    except CSEError as exc:
        if exc.rsc != 4004:
            raise
    else:
        origin = core.identities.get("maintenance:" + fid)
        if any(origin in rule["acor"] for rule in acp["pv"]["acr"]):
            rules = [{**rule, "acor": [value for value in rule["acor"] if value != origin]} for rule in acp["pv"]["acr"]]
            core.cse.update(path, {"m2m:acp": {"pv": {"acr": [rule for rule in rules if rule["acor"]]}}})
    core.store.delete("work_order_cursor", fid)
    core.store.delete("work_order_projection", fid)
    for role in ("maintenance", "bridge", "sensor"):
        core.identities.pop(f"{role}:{fid}", None)


def queue_outcome(core, kind, incident, observation, facility, zone, rqi, command=None):
    asset = core.registry[facility["id"]].get("maintenance", {}).get("assets", {}).get(zone["id"])
    if not asset:
        return False
    record = core.store.get("observations", facility["id"] + ":" + zone["id"])
    name = "opened-" + incident["id"] if command is None else "unresolved-" + command["id"]
    content = {
        "kind": kind, "facility_id": facility["id"], "zone_id": zone["id"], "asset_id": asset["asset_id"],
        "incident_id": incident["id"], "run_id": facility.get("active_run"), "source_cin_ri": record["cin_id"],
        "source_cin_path": record["source_cin_path"], "rqi": rqi, "profile_version": facility["profile_version"],
        "observed_at": observation.observed_at,
    }
    if command:
        content.update(command_id=command["id"], ack_at=command["ack_at"], requested_pct=command["value"])
    core.store.put("maintenance_outbox", name, {"name": name, "parent": facility["path"] + "/outcomes", "content": content})
    return True


def flush_outbox(core):
    for item in core.store.list("maintenance_outbox"):
        fid = item["content"]["facility_id"]
        if "maintenance" not in core.registry.get(fid, {}):
            continue
        origin = core.identities["operator"]
        attrs = {"rn": item["name"], "cnf": "application/json:0", "con": json.dumps(item["content"])}
        try:
            core.cse.create(item["parent"], 4, {"m2m:cin": attrs}, origin=origin)
        except CSEError as exc:
            if exc.rsc != 4105:
                raise
            existing = core.cse.retrieve(item["parent"] + "/" + item["name"], origin=origin)
            if json.loads(existing["body"]["m2m:cin"]["con"]) != item["content"]:
                raise ValueError("Existing outcome conflicts with the recorded site decision") from exc
        core.store.delete("maintenance_outbox", item["name"])


def damper_ack_order(command):
    # Early virtual-device snapshots stored only the applied flag and issue time.
    # Maintenance evidence separately requires an actual ACK timestamp.
    recorded_at = command.get("ack_at") or command["created_at"]
    return datetime.fromisoformat(recorded_at), int(command.get("ack_sequence", 0))


def latest_damper_commands(commands):
    latest = {}
    for command in commands:
        if command.get("action") != "set_damper" or not command.get("ack_at") or not command.get("incident_id"):
            continue
        key = (command["facility_id"], command["zone_id"], command["incident_id"])
        if key not in latest or damper_ack_order(command) >= damper_ack_order(latest[key]):
            latest[key] = command
    return latest


def current_order_view(order, acknowledged):
    current = acknowledged.get((order["facility_id"], order["zone_id"], order["incident_id"]))
    if not current or not order.get("command_id") or order["command_id"] == current["id"]:
        return order
    # The historical CIN stays intact. While the new setpoint settles, expose an
    # explicitly projected pending state without its predecessor's sensor reading.
    view = {k: order.get(k) for k in ("facility_id", "zone_id", "asset_id", "incident_id", "run_id",
                                       "work_order_id", "status", "profile_version")}
    return {**view, "kind": "work_order", "command_id": current["id"], "ack_at": current["ack_at"],
            "requested_pct": current["value"], "observed_at": current["ack_at"], "revision": 0,
            "priority": "inspection", "evidence_status": "awaiting_current_command_followup",
            "view_source": "current_device_ack", "ack_rqi": current.get("ack_rqi"),
            "historical_work_order_ri": order.get("resource_id")}


def refresh_work_orders(core):
    acknowledged = latest_damper_commands(core.store.list("commands"))
    for fid, config in core.registry.items():
        if "maintenance" not in config:
            continue
        path = core.facility(fid)["path"] + "/work_orders"
        origin = core.identities["operator"]
        container = core.cse.retrieve(path, origin=origin)["body"]["m2m:cnt"]
        active_ids = sorted(cmd["id"] for key, cmd in acknowledged.items() if key[0] == fid)
        version = [container["ri"], container["st"], active_ids]
        if core.store.get("work_order_cursor", fid) == version:
            continue
        discovery = core.cse.retrieve(path, origin=origin, params={"fu": 1, "ty": 4, "drt": 1})
        latest = {}
        for uri in discovery["body"]["m2m:uril"]:
            reply = core.cse.retrieve(path + "/" + uri.rsplit("/", 1)[-1], origin=origin)
            cin = reply["body"]["m2m:cin"]
            item = json.loads(cin["con"])
            if cin["pi"] != container["ri"] or item.get("facility_id") != fid:
                raise ValueError("Work order does not belong to this facility")
            key = item["work_order_id"]
            # A later command can open a new investigation on the same order.
            # Compare its source observation before evidence quality within it.
            current = acknowledged.get((fid, item["zone_id"], item["incident_id"]))
            is_current = bool(current and item.get("command_id") == current["id"])
            rank = (is_current, datetime.fromisoformat(item["observed_at"]), int(item["revision"]), cin["ct"], cin["ri"])
            if key not in latest or rank > latest[key][0]:
                latest[key] = (rank, {**item, "resource_id": cin["ri"], "read_rqi": reply["rqi"]})
        with core.store.transaction():
            core.store.put("work_order_projection", fid, [value for _, value in latest.values()])
            core.store.put("work_order_cursor", fid, version)
