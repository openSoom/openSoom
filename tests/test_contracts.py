from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from opensoom.adapters import encode_virtual, normalize
from opensoom.core import Core
from opensoom.models import ActionRequest, Observation, utcnow
from opensoom.policy import diagnose


def example():
    return {"observed_at": utcnow(), "pm25": 12.4, "co2": 650.0, "airflow": 1100.0, "fan_running": True, "damper_pct": 75.0}


def test_both_vendor_formats_preserve_meaning_and_units():
    values = example()
    a = normalize(values, "vendor-a", "food-a", "cook")
    b = normalize(encode_virtual(values, "vendor-b"), "vendor-b", "food-a", "cook")
    for field in ("pm25", "co2", "airflow", "damper_pct"):
        assert getattr(a, field) == pytest.approx(getattr(b, field))
    assert a.fan_running == b.fan_running
    assert a.observed_at == b.observed_at


def test_profile_change_changes_diagnosis_without_core_change():
    profiles = Core.load_profiles()
    values = {**example(), "airflow": 550}
    obs = normalize(values, "vendor-a", "food-a", "cook")
    food = profiles["food-production"]
    learning = profiles["learning-space"]
    assert diagnose(obs, food["zones"][0], food)["status"] == "critical"
    assert diagnose(obs, learning["zones"][0], learning)["status"] == "nominal"


@pytest.mark.parametrize("delta", [-300, 30])
def test_stale_and_future_readings_never_pass_as_healthy(delta):
    values = {**example(), "observed_at": (datetime.now(timezone.utc) + timedelta(seconds=delta)).isoformat()}
    profile = Core.load_profiles()["food-production"]
    assert diagnose(normalize(values, "vendor-a", "food-a", "cook"), profile["zones"][0], profile)["status"] == "stale"


def test_missing_airflow_does_not_become_zero_or_healthy():
    values = {**example(), "airflow": None}
    profile = Core.load_profiles()["food-production"]
    obs = normalize(encode_virtual(values, "vendor-b"), "vendor-b", "food-a", "cook")
    assert obs.airflow is None
    assert diagnose(obs, profile["zones"][0], profile)["status"] == "missing"


def test_running_fan_does_not_establish_airflow():
    profile = Core.load_profiles()["food-production"]
    obs = normalize({**example(), "airflow": 100}, "vendor-a", "food-a", "cook")
    assert obs.fan_running
    assert diagnose(obs, profile["zones"][0], profile)["status"] == "critical"


def test_action_contract_rejects_extra_authority_and_out_of_bounds():
    action = {"facility_id": "food-a", "zone_id": "cook", "action": "set_damper", "value": 100, "reason": "Test", "request_id": "request-1"}
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({**action, "role": "admin"})
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({**action, "value": 101})
    with pytest.raises(ValidationError):
        ActionRequest.model_validate({**action, "facility_id": "../other"})


def test_timezone_and_nonnegative_measurements_are_required():
    with pytest.raises(ValidationError):
        normalize({**example(), "observed_at": "2026-11-18T10:00:00"}, "vendor-a", "food-a", "cook")
    with pytest.raises(ValidationError):
        normalize({**example(), "pm25": -1}, "vendor-a", "food-a", "cook")
