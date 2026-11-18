from types import SimpleNamespace

import pytest

from opensoom.core import OperationError
from opensoom.facility_pack import operation, worker_templates


def test_templates_follow_activated_bindings_without_exporting_deployment_secrets():
    settings = {"assets": {"second": {"asset_id": "bench", "sensor_id": "shaft"}},
                "settle_seconds": 4, "freshness_seconds": 45, "tolerance_pct": 9,
                "provider_profiles": ["private-deployment"], "token": "not-exportable"}
    core = SimpleNamespace(registry={"archive": {"maintenance": settings}, "plain": {}},
                           facility=lambda fid: {"path": "cse/opensoom/facilities/" + fid},
                           identities={"maintenance:archive": "Cmaint", "bridge:archive": "Cbridge"})
    result = worker_templates(core, "archive")
    assert result["maintenance"]["origin"] == "Cmaint"
    assert result["bridge"]["origin"] == "Cbridge"
    assert result["bridge"]["facility_path"] == "cse/opensoom/facilities/archive"
    assert set(result["bridge"]) == {"facility_id", "facility_path", "origin", "assets",
                                     "settle_seconds", "freshness_seconds", "tolerance_pct"}
    result["bridge"]["assets"]["second"]["sensor_id"] = "changed-copy"
    assert settings["assets"]["second"]["sensor_id"] == "shaft"
    assert result["maintenance"]["assets"]["second"]["sensor_id"] == "shaft"
    assert worker_templates(core, "plain") == {}


def test_operator_cannot_activate_pack_to_obtain_role_templates():
    with pytest.raises(OperationError) as failure:
        operation(None, "activate_facility", {"version": "reviewed"}, {"role": "operator"},
                  OperationError, None)
    assert failure.value.code == "admin_required"
