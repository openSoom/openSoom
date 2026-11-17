from datetime import datetime, timedelta, timezone

import pytest

from opensoom.core import Core, OperationError
from opensoom.models import utcnow
from opensoom.policy import diagnose


@pytest.mark.parametrize("setpoint,expected_healthy", [(0, False), (50, False), (100, True)])
def test_virtual_device_preserves_acknowledged_setpoint(tmp_path, monkeypatch, setpoint, expected_healthy):
    service = Core(runtime=tmp_path)
    profile = service.profiles["food-production"]
    facility = {"id": "food-a", "profile": "food-production", "scenario": "exhaust_fault", "active_run": "new-run", "zones": profile["zones"], "adapter": "vendor-a"}
    service.store.put("runs", "new-run", {"started_at": (datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat()})
    service.store.put("commands", "current", {"facility_id": "food-a", "zone_id": "cook", "action": "set_damper", "ack": True, "created_at": utcnow(), "value": setpoint})
    observed = []
    monkeypatch.setattr(service, "acknowledge_pending", lambda _: None)
    monkeypatch.setattr(service, "publish", observed.append)
    service.sample_facility(facility)
    cooking = observed[0]
    assert cooking.damper_pct == setpoint
    assert (diagnose(cooking, profile["zones"][0], profile)["status"] == "nominal") == expected_healthy
    service.cse.close()


def test_other_actor_cannot_append_to_run_even_without_facility_argument(tmp_path):
    service = Core(runtime=tmp_path)
    record = {"id": "operator-run", "facility_id": "food-a", "principal_role": "operator", "tool_calls": []}
    service.store.put("runs", "operator-run", record)
    with pytest.raises(OperationError, match="owning identity"):
        service.tool("doctor", {}, {"role": "observer", "facilities": ["food-a"]}, "operator-run")
    assert service.store.get("runs", "operator-run") == record
    service.cse.close()


def test_read_only_actor_cannot_mutate_operator_run_or_denial_log(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import opensoom.app as api
    service = Core(runtime=tmp_path)
    record = {"id": "operator-run", "facility_id": "food-a", "principal_role": "operator", "mode": "fixture", "summary": "unchanged", "tool_calls": []}
    service.store.put("runs", "operator-run", record)
    monkeypatch.setattr(api, "core", service)
    monkeypatch.setattr(api, "credentials", {role+"_token": "unit-test-"+role for role in ("operator", "observer", "maintenance", "admin")})
    client = TestClient(api.app)
    headers = {"Authorization": "Bearer unit-test-observer"}
    assert client.get("/api/runs/operator-run", headers=headers).status_code == 200
    assert client.patch("/api/agent-runs/operator-run", json={"summary": "changed", "outcome": "FAIL"}, headers=headers).status_code == 403
    assert client.post("/api/tools/doctor", json={"arguments": {}}, headers={**headers, "X-OpenSoom-Run-ID": "operator-run"}).status_code == 403
    assert service.store.get("runs", "operator-run") == record
    owner = {"Authorization": "Bearer unit-test-operator"}
    assert client.patch("/api/agent-runs/operator-run", json={"summary": "owner update", "outcome": "RUNNING"}, headers=owner).status_code == 200
    assert service.store.get("runs", "operator-run")["summary"] == "owner update"
    service.cse.close()


@pytest.mark.parametrize("condition", ["critical", "stale", "missing"])
def test_zero_recovery_samples_and_empty_run_commands_do_not_erase_prior_ack(tmp_path, monkeypatch, condition):
    from opensoom.adapters import normalize
    service = Core(runtime=tmp_path)
    profile = service.profiles["learning-space"]
    zone = {**profile["zones"][0], "standard_path": "test/standard"}
    facility = {"id": "learning-b", "name": "Learning space", "profile": "learning-space",
                "adapter": "vendor-a", "scenario": "no_recovery", "active_run": "prior-run",
                "controls_enabled": True, "zones": [zone]}
    service.store.put("facilities", facility["id"], facility)
    incident = {"id": "existing-incident", "facility_id": "learning-b", "zone_id": zone["id"],
                "status": "recovering", "recovery_count": 1}
    service.store.put("incidents", "learning-b:" + zone["id"], incident)
    prior_command = {"id": "prior-command", "facility_id": "learning-b", "zone_id": zone["id"],
                     "incident_id": incident["id"], "run_id": "prior-run", "action": "set_damper",
                     "ack": True, "ack_at": (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(),
                     "status": "unresolved", "observed_result": "unresolved", "unresolved_samples": 2}
    service.store.put("commands", prior_command["id"], prior_command)
    values = {"observed_at": utcnow(), "pm25": 62, "co2": 1450, "airflow": 200,
              "fan_running": True, "damper_pct": 100}
    if condition == "stale":
        values["observed_at"] = (datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
    elif condition == "missing":
        values["airflow"] = None
    observation = normalize(values, "vendor-a", "learning-b", zone["id"])
    service.store.put("observations", "learning-b:" + zone["id"], {"observation": observation.model_dump(), "rqi": "regression-rqi"})
    service.evaluate(observation, facility, zone, "regression-rqi")
    service.store.put("runs", "new-observer-run", {"id": "new-observer-run", "facility_id": "learning-b", "principal_role": "observer"})
    monkeypatch.setattr(service, "refresh_observation", lambda *_: None)
    monkeypatch.setattr(service.cse, "retrieve", lambda *_, **__: {"body": {"cod:aiQSr": {"pm25": 62}}, "rqi": "standard-rqi"})
    result = service.tool("read_evidence", {"facility_id": "learning-b"}, {"role": "observer", "facilities": ["learning-b"]}, "new-observer-run")
    assert result["incidents"][0]["id"] == incident["id"]
    assert result["incidents"][0]["recovery_count"] == 0
    assert result["incidents"][0]["status"] != "resolved"
    assert result["zones"][0]["status"] == condition
    assert result["commands"] == []
    assert service.store.get("commands", "prior-command")["ack"] is True
    assert result["evidence_scope"]["commands"]["run_id"] == "new-observer-run"
    assert result["evidence_scope"]["commands"]["complete_facility_history"] is False
    assert result["evidence_scope"]["recovery_count"]["counts_action_attempts"] is False
    assert result["evidence_scope"]["recovery_count"]["required"] == profile["recovery_samples"]
    service.cse.close()
