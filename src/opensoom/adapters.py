"""Two intentionally different vendor formats mapped to the same contract."""
from typing import Any
from .models import Observation, utcnow


def normalize(payload: dict[str, Any], vendor: str, facility_id: str, zone_id: str) -> Observation:
    if vendor == "vendor-a":
        values = dict(payload)
    elif vendor == "vendor-b":
        values = {
            "observed_at": payload["sampleTime"],
            "pm25": None if payload.get("dust_mg_m3") is None else payload["dust_mg_m3"] * 1000,
            "co2": payload.get("carbonDioxidePPM"),
            "airflow": None if payload.get("flow_l_s") is None else payload["flow_l_s"] * 3.6,
            "fan_running": payload["motor"] == "RUN",
            "damper_pct": payload["valve_fraction"] * 100,
        }
    else:
        raise ValueError("Unknown adapter")
    return Observation(facility_id=facility_id, zone_id=zone_id, adapter=vendor, received_at=utcnow(), **values)


def encode_virtual(values: dict[str, Any], vendor: str) -> dict[str, Any]:
    if vendor == "vendor-a":
        return values
    if vendor != "vendor-b":
        raise ValueError("Unknown adapter")
    return {
        "sampleTime": values["observed_at"],
        "dust_mg_m3": None if values.get("pm25") is None else values["pm25"] / 1000,
        "carbonDioxidePPM": values.get("co2"),
        "flow_l_s": None if values.get("airflow") is None else values["airflow"] / 3.6,
        "motor": "RUN" if values["fan_running"] else "STOP",
        "valve_fraction": values["damper_pct"] / 100,
    }
