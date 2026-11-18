"""Manager-authored virtual facility installations with administrator activation."""
from __future__ import annotations

import json
import os
from pathlib import Path

import jsonschema

from .scenario_authoring import digest


def validate(pack, root: Path):
    json.dumps(pack, allow_nan=False)
    profile, facility = pack["profile"], pack["facility"]
    jsonschema.validate(profile, json.loads((root / "schemas/facility-profile.schema.json").read_text()))
    jsonschema.validate({"facilities": [facility]}, json.loads((root / "schemas/facilities.schema.json").read_text()))
    if facility["profile"] != profile["id"] or not profile["simulation_only"]:
        raise ValueError("The facility and its virtual profile must match")
    zones = {zone["id"] for zone in profile["zones"]}
    if len(zones) != len(profile["zones"]):
        raise ValueError("Give every zone a distinct ID")
    assets = facility.get("maintenance", {}).get("assets", {})
    if assets.keys() - zones or any(len({asset[field] for asset in assets.values()}) != len(assets)
                                   for field in ("asset_id", "sensor_id")):
        raise ValueError("Each maintenance binding must have a unique sensor and asset in a configured zone")


def operation(core, name, args, principal, error, root):
    if name == "draft_facility":
        if principal["role"] not in ("operator", "admin"):
            raise error("action_denied", "A facility manager can prepare the installation preview", 403)
        required = {"site_id", "name", "template", "adapter", "zones"}
        if not required <= args.keys() or args.keys() - required - {"maintenance"}:
            raise error("invalid_arguments", "Supply a facility ID, name, template, adapter and zone targets", 422)
        template = core.profiles.get(args["template"]) if isinstance(args["template"], str) else None
        if not template:
            raise error("unknown_profile", "Choose an installed template with the intended operating policy", 404)
        fid = args["site_id"]
        if not isinstance(fid, str):
            raise error("invalid_facility", "Choose a short facility ID", 422)
        profile = {**template, "id": fid, "name": args["name"], "zones": args["zones"],
                   "description": "Virtual installation based on " + template["id"]}
        facility = {"id": fid, "name": args["name"], "profile": fid, "adapter": args["adapter"], "read_only_roles": []}
        if args.get("maintenance") is not None:
            facility["maintenance"] = args["maintenance"]
        pack = {"facility": facility, "profile": profile}
        try:
            validate(pack, root)
            version = digest(pack)
        except (jsonschema.ValidationError, ValueError, TypeError) as exc:
            raise error("invalid_facility", getattr(exc, "message", str(exc))[:220], 422) from exc
        core.store.put("facility_pack_drafts", version, pack)
        return {"status": "preview", "version": version, **pack}
    if principal["role"] != "admin":
        raise error("admin_required", "The site administrator activates a reviewed installation", 403)
    if set(args) != {"version"} or not isinstance(args["version"], str):
        raise error("invalid_arguments", "Supply a reviewed facility pack version", 422)
    pack = core.store.get("facility_pack_drafts", args["version"])
    if not pack or digest(pack) != args["version"]:
        raise error("unknown_pack", "This facility pack version is unavailable", 404)
    profile, facility = pack["profile"], pack["facility"]
    fid = facility["id"]
    # A single-site runtime keeps the deployment scope chosen by its owner.
    selected = os.environ.get("OPENSOOM_FACILITY_IDS")
    if selected and fid not in {name.strip() for name in selected.split(",")}:
        raise error("outside_deployment", "Activate this pack on an installation that includes the facility", 403)
    with core.lock:
        # Reserve the identity before writing CSE resources. An interrupted install can
        # resume from this immutable intent, including after a process restart.
        with core.store.transaction():
            existing = core.store.get("installed_facility_packs", fid)
            claimed = existing is not None or fid in core.registry or profile["id"] in core.profiles
            if claimed and existing != pack:
                raise error("facility_exists", "Choose a new identity to preserve the existing facility and its operating history", 409)
            core.store.put("installed_facility_packs", fid, pack)
        core.profiles[profile["id"]] = profile
        core.registry[fid] = facility
        core.setup_facility(fid, facility["name"], profile["id"], facility["adapter"])
        core.store.put("config", "identities", core.identities)
        return {"status": "active", "facility_id": fid, "version": args["version"],
                "cse_path": core.facility(fid)["path"], "zone_ids": [zone["id"] for zone in profile["zones"]]}
