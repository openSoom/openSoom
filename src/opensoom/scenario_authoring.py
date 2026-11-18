"""Versioned, facility-bound virtual damper trials through the operating service."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .adapters import encode_virtual, normalize
from .models import ActionRequest, utcnow


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    facility_id: str
    scenario_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,47}$")
    zone_id: str
    observation_age_seconds: int = Field(ge=0, le=86400)
    airflow_m3_h: float = Field(ge=0, le=100000)
    damper_percent: float = Field(ge=0, le=100)
    expected_result: Literal["command_refused", "device_acknowledged"]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def profile_pin(core, facility):
    return digest({"profile": core.profiles[facility["profile"]], "adapter": facility["adapter"],
                   "asset_bindings": core.registry[facility["id"]].get("maintenance", {}).get("assets", {})})


def cse_commands(core, zone):
    reply = core.cse.retrieve(zone["path"] + "/commands", origin=core.identities["diagnostic"])
    container = reply["body"]["m2m:cnt"]
    return {"count": container["cni"], "state_tag": container["st"], "rqi": reply["rqi"]}


def dispatch(core, name, args, principal, agent_run_id, error):
    fid = args.get("facility_id")
    if not isinstance(fid, str) or not fid:
        raise error("invalid_arguments", "Supply a configured facility ID", 422)
    core.authorize(principal, fid)
    facility = core.facility(fid)
    if name == "read_scenario_run":
        if set(args) != {"facility_id", "execution_id"} or not isinstance(args["execution_id"], str):
            raise error("invalid_arguments", "Supply the facility and execution ID", 422)
        run = core.store.get("scenario_runs", args["execution_id"])
        if not run or run["facility_id"] != fid:
            raise error("unknown_execution", "Execution not found in this facility", 404)
        result = dict(run)
        if run.get("cin"):
            receipt = core.cse.retrieve(run["cin"], origin=core.identities["diagnostic"])
            cin = receipt["body"]["m2m:cin"]
            raw = cin["con"]
            source = json.loads(raw) if isinstance(raw, str) else raw
            if cin["ri"] != run["cin"] or (source["facility_id"], source["zone_id"]) != (fid, run["zone_id"]):
                raise error("observation_identity_mismatch", "Stored execution observation no longer matches", 409)
            result["readback"] = {"rqi": receipt["rqi"], "cin": cin["ri"], "observed_at": source["observed_at"],
                                  "airflow_m3_h": source["airflow"], "zone_id": source["zone_id"]}
        return result

    core.authorize(principal, fid, "set_damper")
    if not facility["simulated"]:
        raise error("virtual_only", "Authoring and replay require a virtual facility", 403)
    pin = profile_pin(core, facility)
    if name == "save_scenario":
        draft = ScenarioDefinition.model_validate(args)
        core.zone(facility, draft.zone_id)
        assets = core.registry[fid].get("maintenance", {}).get("assets", {})
        asset_id = assets.get(draft.zone_id, {}).get("asset_id", f"{fid}/{draft.zone_id}/damper")
        definition = {**draft.model_dump(), "profile_id": facility["profile"], "profile_pin": pin,
                      "asset_id": asset_id, "template": "virtual_damper_check_v1"}
        version = digest(definition)
        saved = {**definition, "version": version}
        core.store.put("scenario_definitions", version, saved)
        return saved

    if set(args) != {"facility_id", "scenario_id", "version", "request_id"}:
        raise error("invalid_arguments", "Provide facility, scenario ID, saved version, and retry-safe request ID", 422)
    if not all(isinstance(args[k], str) for k in args) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", args["request_id"]):
        raise error("invalid_arguments", "Invalid execution request", 422)
    saved = core.store.get("scenario_definitions", args["version"])
    if not saved or (saved["facility_id"], saved["scenario_id"]) != (fid, args["scenario_id"]):
        raise error("unknown_scenario", "No such scenario version for this facility", 404)
    if saved["version"] != digest({k: v for k, v in saved.items() if k != "version"}):
        raise error("definition_conflict", "The stored trial differs from its recorded version", 409)
    if pin != saved["profile_pin"]:
        # Early v1 trials pinned the profile and adapter before asset bindings
        # existed. Accept one only when the facility still has no bindings and
        # the recorded target is the same implicit virtual damper.
        legacy_pin = digest({"profile": core.profiles[facility["profile"]], "adapter": facility["adapter"]})
        implicit_asset = f"{fid}/{saved['zone_id']}/damper"
        if (saved["profile_pin"] != legacy_pin or saved.get("asset_id") != implicit_asset
                or core.registry[fid].get("maintenance", {}).get("assets")
                or saved.get("template") != "virtual_damper_check_v1"):
            raise error("profile_changed", "Review and save the trial against the current profile", 409)
    execution = "trial-" + digest([fid, args["request_id"]])[:24]
    with core.lock:
        prior = core.store.get("scenario_runs", execution)
        if prior:
            if prior["version"] != args["version"]:
                raise error("idempotency_conflict", "Execution request already references another version", 409)
            return prior
        facility = core.facility(fid)
        if facility.get("active_run"):
            raise error("simulation_busy", "This facility is already sampling another scenario. Choose an idle virtual instance.", 409)
        zone = core.zone(facility, saved["zone_id"])
        trial = {"execution_id": execution, "facility_id": fid, "zone_id": zone["id"], "asset_id": saved["asset_id"],
                 "scenario_id": saved["scenario_id"], "version": args["version"], "expected_result": saved["expected_result"],
                 "agent_run_id": agent_run_id, "status": "running", "started_at": utcnow()}
        core.store.put("scenario_runs", execution, trial)
        try:
            execute_trial(core, facility, zone, saved, trial, principal, error)
        except Exception as exc:
            trial.update(status="interrupted", error=getattr(exc, "code", type(exc).__name__))
            core.store.put("scenario_runs", execution, trial)
            raise
        core.store.put("scenario_runs", execution, trial)
        return trial


def execute_trial(core, facility, zone, saved, trial, principal, error):
    fid, zid = facility["id"], zone["id"]
    before = cse_commands(core, zone)
    observed_at = datetime.now(timezone.utc) - timedelta(seconds=saved["observation_age_seconds"])
    values = {"observed_at": observed_at.isoformat(), "airflow": saved["airflow_m3_h"], "pm25": 12.0, "co2": 620.0,
              "fan_running": True, "damper_pct": 70.0}
    def publish():
        observation = normalize(encode_virtual(values, facility["adapter"]), facility["adapter"], fid, zid)
        return core.publish(observation)
    sent = publish()
    cin = sent["body"]["m2m:cin"]["ri"]
    trial.update(cin=cin, publish_rqi=sent["rqi"], commands_before=before)
    action = ActionRequest(facility_id=fid, zone_id=zid, action="set_damper", value=saved["damper_percent"],
                           reason="User-authored virtual damper trial", request_id=trial["execution_id"] + ":damper")
    try:
        command = core.request_action(action, principal, trial["execution_id"])
    except error as exc:
        if exc.code != "evidence_not_current":
            raise
        actual = "command_refused"
        trial["refusal"] = exc.code
    else:
        core.acknowledge_pending(facility, only_command_id=command["id"])
        command = core.store.get("commands", command["id"])
        if not command.get("ack"):
            raise error("ack_missing", "Virtual device did not acknowledge this command", 409)
        values.update(damper_pct=command["value"])
        for _ in range(core.profiles[facility["profile"]]["recovery_samples"]):
            # The two adapters publish millisecond timestamps. Each post-ACK sample must be distinct.
            time.sleep(0.002)
            values["observed_at"] = utcnow()
            publish()
        command = core.store.get("commands", command["id"])
        trial["command"] = {k: command.get(k) for k in ("id", "cse_resource_id", "cse_rqi", "ack_rqi", "ack_at", "status", "verification_rqi")}
        actual = "device_acknowledged"
    after = cse_commands(core, zone)
    delta = after["state_tag"] - before["state_tag"]
    matched = actual == saved["expected_result"] and delta == (0 if actual == "command_refused" else 1)
    trial.update(status="completed", completed_at=utcnow(), actual_result=actual, assertion_passed=matched,
                 commands_after=after, command_state_tag_delta=delta)
