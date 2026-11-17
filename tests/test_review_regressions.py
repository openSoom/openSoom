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
