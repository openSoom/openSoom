import json
import shutil

import pytest

from opensoom import core


def prepare_checkout(tmp_path, monkeypatch):
    for directory in ("schemas", "profiles", "config"):
        shutil.copytree(core.ROOT / directory, tmp_path / directory)
    monkeypatch.setattr(core, "ROOT", tmp_path)
    monkeypatch.delenv("OPENSOOM_FACILITY_IDS", raising=False)


def test_new_facility_is_configuration_and_role_scope_is_preserved(tmp_path, monkeypatch):
    prepare_checkout(tmp_path, monkeypatch)
    path = tmp_path / "config/facilities.json"
    data = json.loads(path.read_text())
    data["facilities"].append({"id": "bakery-c", "name": "Bakery", "profile": "food-production", "adapter": "vendor-b", "read_only_roles": []})
    path.write_text(json.dumps(data))
    service = core.Core(runtime=tmp_path / "runtime")
    assert "bakery-c" in service.actor_facilities("operator")
    assert service.actor_facilities("observer") == ["food-a"]
    assert service.registry["bakery-c"]["adapter"] == "vendor-b"
    service.cse.close()


def test_unknown_selected_facility_fails_before_runtime_setup(tmp_path, monkeypatch):
    prepare_checkout(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENSOOM_FACILITY_IDS", "not-configured")
    with pytest.raises(ValueError, match="not configured"):
        core.Core.load_registry(core.Core.load_profiles())


def test_duplicate_facility_is_rejected(tmp_path, monkeypatch):
    prepare_checkout(tmp_path, monkeypatch)
    path = tmp_path / "config/facilities.json"
    data = json.loads(path.read_text())
    data["facilities"].append(data["facilities"][0])
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Duplicate"):
        core.Core.load_registry(core.Core.load_profiles())
