from datetime import datetime, timedelta, timezone

from opensoom.adapters import encode_virtual, normalize
from opensoom.ventilation_trials import PERSISTENT, REBOUND, RECOVERY, observed_ending, pollutant_readings


def test_second_facility_uses_its_own_thresholds_with_vendor_b_units():
    zone = {"pm25_warning": 25, "co2_warning": 1000}
    pm, co2 = pollutant_readings(REBOUND, zone, 16)
    stamp = datetime.now(timezone.utc)
    values = {"observed_at": stamp.isoformat(), "pm25": pm, "co2": co2, "airflow": 575,
              "fan_running": True, "damper_pct": 100}
    sample = normalize(encode_virtual(values, "vendor-b"), "vendor-b", "learning-b", "classroom")
    assert sample.pm25 > zone["pm25_warning"] and sample.co2 < zone["co2_warning"]
    command = {"ack_at": (stamp - timedelta(seconds=17)).isoformat(), "status": "verified"}
    assert observed_ending(REBOUND, command, {"observation": sample.model_dump()}, zone) == "particles_returned_after_first_target"


def test_verified_command_does_not_finish_rebound_trial_before_particles_return():
    zone = {"pm25_warning": 45, "co2_warning": 1200}
    ack = datetime.now(timezone.utc)
    command = {"ack_at": ack.isoformat(), "status": "verified"}
    observation = {"observed_at": (ack + timedelta(seconds=10)).isoformat(), "pm25": 15, "co2": 720}
    assert observed_ending(REBOUND, command, {"observation": observation}, zone) is None
    observation["observed_at"] = (ack + timedelta(seconds=17)).isoformat()
    assert observed_ending(REBOUND, command, {"observation": observation}, zone) is None
    for scenario in (RECOVERY, REBOUND, PERSISTENT):
        assert pollutant_readings(scenario, zone, None) == (75, 1500)
