"""Virtual sensor inputs for the three air-quality response trials."""
from datetime import datetime
from math import isclose


RECOVERY = "air_quality_recovery"
PERSISTENT = "air_quality_persistent"
REBOUND = "air_quality_rebound"
SCENARIOS = (RECOVERY, PERSISTENT, REBOUND)


def pollutant_readings(scenario, zone, elapsed):
    """Sample a deterministic input trace using elapsed device time in real seconds."""
    pm_limit, co2_limit = zone["pm25_warning"], zone["co2_warning"]
    if elapsed is None:
        return round(pm_limit * 5 / 3, 2), round(co2_limit * 1.25, 2)
    if elapsed < 5:
        return round(pm_limit * 4 / 3, 2), round(co2_limit * 1.1, 2)
    if scenario == PERSISTENT or (scenario == REBOUND and elapsed >= 14):
        return round(pm_limit * 4 / 3, 2), round(co2_limit * .6, 2)
    if elapsed < 9:
        return round(pm_limit * 2 / 3, 2), round(co2_limit * .8, 2)
    return round(pm_limit / 3, 2), round(co2_limit * .6, 2)


def observed_ending(scenario, command, record, zone):
    """Keep the live fixture running until a measurement witnesses its last phase."""
    if not command or not command.get("ack_at") or not record:
        return None
    obs = record["observation"]
    elapsed = (datetime.fromisoformat(obs["observed_at"]) - datetime.fromisoformat(command["ack_at"])).total_seconds()
    if elapsed < 16 or record.get("sequence_issue"):
        return None
    expected_pm, expected_co2 = pollutant_readings(scenario, zone, elapsed)
    if obs["pm25"] is None or obs["co2"] is None or not (
        isclose(obs["pm25"], expected_pm) and isclose(obs["co2"], expected_co2)
    ):
        return None
    if scenario == PERSISTENT and command["status"] == "unresolved":
        return "airflow_restored_particles_still_high"
    if command["status"] == "verified":
        return "particles_returned_after_first_target" if scenario == REBOUND else "air_quality_targets_observed"
    return None
