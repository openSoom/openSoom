"""Stable contracts shared by adapters, policies, tools and the dashboard."""
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    facility_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,48}$")
    zone_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,48}$")
    observed_at: str
    received_at: str = Field(default_factory=utcnow)
    source: Literal["simulated"] = "simulated"
    adapter: Literal["vendor-a", "vendor-b"]
    pm25: float | None = Field(default=None, ge=0)
    co2: float | None = Field(default=None, ge=0)
    airflow: float | None = Field(default=None, ge=0)
    fan_running: bool
    damper_pct: float = Field(ge=0, le=100)

    @field_validator("observed_at", "received_at")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamp must include timezone")
        return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds")


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    facility_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,48}$")
    zone_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,48}$")
    action: Literal["set_damper", "request_maintenance"]
    value: float | None = None
    reason: str = Field(min_length=1, max_length=1000)
    request_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.:-]+$")

    @field_validator("value")
    @classmethod
    def bounded_value(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 100:
            raise ValueError("Damper percentage must be within 0–100")
        return value


class ToolEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    arguments: dict[str, Any] = Field(default_factory=dict)
