"""Deterministic, facility-profile-bound diagnosis; no LLM safety decisions."""
from datetime import datetime, timezone
from .models import Observation


def diagnose(observation: Observation, zone: dict, profile: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    age = (now - datetime.fromisoformat(observation.observed_at)).total_seconds()
    if age < -5:
        return {"status": "stale", "reason": "Observation timestamp is in the future", "freshness": age}
    if age > profile["freshness_seconds"]:
        return {"status": "stale", "reason": "Observation is too old for control", "freshness": age}
    if any(getattr(observation, name) is None for name in ("airflow", "co2", "pm25")):
        return {"status": "missing", "reason": "A required observation is missing", "freshness": age}
    reasons = []
    if observation.airflow < zone["minimum_airflow"]:
        reasons.append("Airflow is below this zone's configured simulation target")
    if observation.pm25 > zone["pm25_warning"]:
        reasons.append("Particles exceed the configured simulation target")
    if observation.co2 > zone["co2_warning"]:
        reasons.append("CO₂ exceeds the configured simulation target")
    if not observation.fan_running:
        reasons.append("Fan reports stopped")
    return {"status": "critical" if reasons else "nominal", "reason": "; ".join(reasons) or "Within configured operating targets", "freshness": age}
