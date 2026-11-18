"""Local transactional boundaries; actual CSE execution is captured separately."""
from datetime import datetime, timedelta, timezone
import threading

import pytest

from opensoom.handover import AuthorityStore, MaintenanceHandover, ServingCSE
from opensoom.onem2m import CSEError


@pytest.fixture
def store(tmp_path):
    value = AuthorityStore(tmp_path / "authority.sqlite")
    value.put("snapshot", {"facility_id": "facility-a", "profile_version": 1, "command_ttl_seconds": 60})
    value.activate(None, "A", "/cse-a")
    return value


def command(**changes):
    now = datetime.now(timezone.utc)
    return {"command_id": "pending-1", "facility_id": "facility-a", "profile_version": 1, "action": "set_damper", "value": 50.0, "issued_at": (now - timedelta(seconds=1)).isoformat(), "expires_at": (now + timedelta(seconds=40)).isoformat(), "target": "A", "epoch": 1, "source_cse_id": "/cse-a", **changes}


def test_old_source_and_forged_new_epoch_are_fenced(store):
    original = command()
    store.activate(store.get("authority"), "B", "/cse-b")
    assert store.execute_virtual(original, "/cse-a")["code"] == "stale_authority"
    assert store.execute_virtual({**original, "target": "B", "epoch": 2}, "/cse-a")["code"] == "stale_authority"
    assert store.execution_count() == 0


def test_dedupe_survives_restart_and_cse_change(store):
    original = command()
    assert store.execute_virtual(original, "/cse-a")["damper_pct"] == 50
    store.activate(store.get("authority"), "B", "/cse-b")
    moved = {**original, "target": "B", "epoch": 2, "source_cse_id": "/cse-b"}
    restarted = AuthorityStore(store.path)
    assert restarted.execute_virtual(moved, "/cse-b")["status"] == "duplicate"
    assert restarted.execute_virtual({**moved, "value": 80.0}, "/cse-b")["code"] == "idempotency_conflict"
    assert restarted.execution_count() == 1


@pytest.mark.parametrize("change,code", [
    ({"facility_id": "facility-b"}, "scope_mismatch"),
    ({"profile_version": 2}, "scope_mismatch"),
    ({"expires_at": "2020-01-01T00:00:00+00:00"}, "expired_or_invalid"),
    ({"expires_at": "2030-01-01T00:00:00+00:00"}, "expired_or_invalid"),
    ({"issued_at": "2030-01-01T00:00:00+00:00"}, "expired_or_invalid"),
    ({"value": True}, "expired_or_invalid"),
    ({"value": -1}, "expired_or_invalid"),
    ({"value": 101}, "expired_or_invalid"),
])
def test_invalid_commands_do_not_actuate(store, change, code):
    assert store.execute_virtual(command(**change), "/cse-a")["code"] == code
    assert store.execution_count() == 0


def test_two_controllers_cannot_commit_two_successor_epochs(store):
    expected = store.get("authority")
    barrier, results = threading.Barrier(2), []
    def switch():
        local = AuthorityStore(store.path)
        barrier.wait()
        try:
            results.append(local.activate(expected, "B", "/cse-b"))
        except RuntimeError:
            results.append("conflict")
    workers = [threading.Thread(target=switch) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert results.count("conflict") == 1
    assert store.get("authority")["epoch"] == 2


def test_permission_failure_never_triggers_switch(store):
    class Denied:
        def retrieve(self, *_args, **_kwargs):
            raise CSEError("Denied", {"rsc": 4103})
    a = ServingCSE("A", "http://127.0.0.1:1", "a", "/cse-a", Denied(), root="a/test", roles={"controller": "Ca"})
    b = ServingCSE("B", "http://127.0.0.1:2", "b", "/cse-b", None)
    controller = MaintenanceHandover([a, b], store, "test", "http://127.0.0.1:3/notify")
    with pytest.raises(CSEError):
        controller.tick()
    assert controller.failures == 0 and store.get("authority")["target"] == "A"


def test_target_write_failure_resumes_same_snapshot_before_atomic_activation(store, monkeypatch):
    state = store.get("snapshot")
    state.update(incident={"id": "incident-stays-open", "status": "open"}, last_sequence=3,
                 last_observation={"sequence": 3}, pending_command=command())
    store.put("snapshot", state)
    probes = []
    class Unavailable:
        def retrieve(self, *_args, **_kwargs):
            probes.append("A")
            raise CSEError("Stopped", {"rsc": 0})
    a = ServingCSE("A", "http://127.0.0.1:1", "a", "/cse-a", Unavailable(), root="a/test", roles={"controller": "Ca"})
    b = ServingCSE("B", "http://127.0.0.1:2", "b", "/cse-b", None)
    staged, writes = {}, []
    fail_once = [True]
    def prepare(target, name, body, role, epoch):
        writes.append((target.key, name, epoch))
        if name == "incident" and fail_once[0]:
            fail_once[0] = False
            raise CSEError("Injected target write transport failure", {"rsc": 0})
        previous = staged.setdefault(name, body)
        assert previous == body  # Retry must not invent a new pending command.
        return {"rsc": 2000, "body": body}
    def controller():
        value = MaintenanceHandover([a, b], AuthorityStore(store.path), "test", "http://127.0.0.1:3/notify", failure_threshold=1)
        monkeypatch.setattr(value, "provision", lambda target: {"target": target.key})
        monkeypatch.setattr(value, "_prepared_content", prepare)
        return value
    first = controller()
    assert first.tick()["kind"] == "target_restore_pending"
    assert store.get("authority") == {"target": "A", "cse_id": "/cse-a", "epoch": 1}
    assert store.get("snapshot") == state and store.get("restore_pending")["target"] == "B"
    with pytest.raises(RuntimeError):
        first.queue_command("new-command-during-transition", 100, command()["expires_at"])
    # A new controller can resume from the persisted marker without re-deciding
    # a destination or probing the source again.
    second = controller()
    assert second.tick()["kind"] == "serving_cse_changed"
    assert probes == ["A"] and store.get("restore_pending") is None
    assert store.get("authority") == {"target": "B", "cse_id": "/cse-b", "epoch": 2}
    restored = store.get("snapshot")
    assert restored["incident"] == state["incident"] and restored["last_observation"] == state["last_observation"]
    pending = restored["pending_command"]
    assert pending["command_id"] == state["pending_command"]["command_id"]
    assert pending["expires_at"] == state["pending_command"]["expires_at"]
    assert store.execute_virtual(pending, "/cse-b")["status"] == "applied"
    assert store.execute_virtual(pending, "/cse-b")["status"] == "duplicate"
    assert store.execution_count() == 1 and all(key == "B" for key, _, _ in writes)
