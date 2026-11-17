"""Receive centrally stored intents without transferring local action authority.

Only trusted service configuration chooses the CSE, queue, facility and actor.
An intent carries no credentials, endpoint, role, or permission grants. This
library is deliberately separate from a model-facing tool or arbitrary URL API.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .core import OperationError
from .models import ActionRequest, utcnow


class CentralIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    schema_version: Literal[1]
    request_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    facility_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,48}$")
    zone_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,48}$")
    profile_id: str = Field(min_length=1, max_length=100)
    profile_version: int = Field(ge=1)
    issued_at: str
    expires_at: str
    action: Literal["set_damper", "request_maintenance"]
    value: float | None = Field(default=None, ge=0, le=100)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("issued_at", "expires_at")
    @classmethod
    def timezone_required(cls, value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Intent timestamps require a timezone")
        return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds")


class FederationReceiver:
    """A fixed facility receiver; the local activated profile remains decisive.

    ``queue_resource_id`` is obtained while configuring a known central CSE.
    Callers must retrieve the CIN from that configured CSE using its authorized
    local actor. A successful CSE read is provenance, not an action approval.
    """

    def __init__(self, core, facility_id: str, profile_id: str, queue_resource_id: str, source_cse_id: str = "/opensoom-central"):
        self.core = core
        self.facility_id = facility_id
        self.profile_id = profile_id
        self.queue_resource_id = queue_resource_id
        self.source_cse_id = source_cse_id
        self._principal = {"role": "operator", "facilities": [facility_id]}

    def receive(self, cse_result: dict[str, Any]) -> dict[str, Any]:
        """Validate a retrieved intent, retain its receipt, and dispatch at most once."""
        cin = cse_result.get("body", {}).get("m2m:cin", {})
        if cse_result.get("rsc") != 2000 or not cse_result.get("rqi") or cin.get("ty") != 4 or cin.get("pi") != self.queue_resource_id or not cin.get("ri"):
            raise OperationError("intent_source_mismatch", "Intent must be retrieved from the configured CSE queue", 409)
        try:
            body = json.loads(cin["con"]) if isinstance(cin.get("con"), str) else cin.get("con")
            intent = CentralIntent.model_validate(body)
        except (ValueError, TypeError, ValidationError) as exc:
            raise OperationError("invalid_central_intent", "Central intent does not match the supported schema", 422) from exc
        data = intent.model_dump()
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        key = self.facility_id + ":" + intent.request_id
        source = {"cse_id": self.source_cse_id, "rqi": cse_result["rqi"], "cin_id": cin["ri"], "queue_resource_id": cin["pi"]}
        # The file lock covers receipt + Core dispatch across receiver processes.
        # The Core request_id check additionally protects an interrupted receipt.
        with (self.core.runtime / "federation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            previous = self.core.store.get("federation_receipts", key)
            if previous:
                if previous["intent_sha256"] != fingerprint:
                    raise OperationError("central_idempotency_conflict", "Central request ID already belongs to different intent content", 409)
                result = {**previous, "replayed": True, "retrieval_rqi": cse_result["rqi"]}
                if previous.get("command_id"):
                    result["command"] = self.core.store.get("commands", previous["command_id"])
                return result
            record = {"request_id": intent.request_id, "facility_id": self.facility_id, "received_at": utcnow(), "intent_sha256": fingerprint, "source": source, "replayed": False}
            try:
                self._validate_scope_and_time(intent)
                request = ActionRequest.model_validate({key: data[key] for key in ("request_id", "facility_id", "zone_id", "action", "value", "reason")})
                command = self.core.request_action(request, self._principal)
            except OperationError as error:
                record.update(status="rejected", code=error.code, message=error.message)
            else:
                record.update(status="accepted", command_id=command["id"], command=command)
            self.core.store.put("federation_receipts", key, record)
            self.core.log("central_intent_" + record["status"], "Central intent checked against local authority", self.facility_id, intent.zone_id, request_id=intent.request_id, cse_rqi=cse_result["rqi"], code=record.get("code"), command_id=record.get("command_id"))
            return record

    def _validate_scope_and_time(self, intent: CentralIntent) -> None:
        facility = self.core.facility(self.facility_id)
        if intent.facility_id != self.facility_id:
            raise OperationError("central_facility_mismatch", "Central intent belongs to another facility", 403)
        if facility["profile"] != self.profile_id or intent.profile_id != self.profile_id or intent.profile_version != facility["profile_version"]:
            raise OperationError("central_profile_mismatch", "Central intent does not match the activated local profile", 409)
        now = datetime.now(timezone.utc)
        issued, expires = (datetime.fromisoformat(value) for value in (intent.issued_at, intent.expires_at))
        maximum_lifetime = self.core.profiles[self.profile_id]["command_ttl_seconds"]
        if expires <= issued or (expires - issued).total_seconds() > maximum_lifetime:
            raise OperationError("central_lifetime_invalid", "Central intent lifetime exceeds the activated profile", 409)
        if issued > now:
            raise OperationError("central_issued_in_future", "Central intent was issued in the future", 409)
        if expires <= now:
            raise OperationError("central_intent_expired", "Expired central intent cannot create a local command", 409)
