from uuid import uuid4

from fastapi import HTTPException
import pytest

from opensoom.technician import FieldDesk, Inspection


def test_worker_revision_for_superseded_command_cannot_be_signed(monkeypatch):
    desk = FieldDesk({"facility_id":"site", "facility_path":"mn/opensoom/facilities/site", "name":"Site", "profile":"metalwork",
                      "simulation":True, "zones":{"weld":{"name":"Welding","target_m3_h":600}}}, None)
    base = {"facility_id":"site", "zone_id":"weld", "work_order_id":"work-i1", "incident_id":"i1",
            "asset_id":"damper", "status":"open", "revision":4, "observed_at":"2026-11-01T00:00:00+00:00",
            "resource_id":"old-evidence", "priority":"inspect_airflow_path", "command_id":"old",
            "recorded_at":"20261101T000000","requested_pct":80}
    ack = {"facility_id":"site", "zone_id":"weld", "incident_id":"i1", "command_id":"new",
           "device_state":"damper_changed", "value":100,"ack_at":"2026-11-01T00:00:10+00:00","state_tag":4,"read_rqi":"req"}
    streams = {"work_orders":[base], "weld/acks":[ack], "inspections":[], "inspection_notes":[]}
    monkeypatch.setattr(desk,"stream", streams.__getitem__)
    order = desk.queue()["work_orders"][0]
    assert order["command_id"] == "new"
    assert order["requested_pct"] == 100
    assert order["evidence_status"] == "awaiting_current_command_followup"
    assert order.get("resource_id") is None
    assert order["historical_work_order_ri"] == "old-evidence"
    class NoPriorEntry:
        def retrieve(self, path):
            from opensoom.onem2m import CSEError
            raise CSEError("Missing", {"rsc":4004})
    desk.cse = NoPriorEntry()
    form = Inspection(work_order_ri="old-evidence", request_id=uuid4(), action="checked")
    with pytest.raises(HTTPException) as stale:
        desk.record("work-i1", form)
    assert stale.value.status_code == 409
    with pytest.raises(HTTPException) as other:
        desk.record("another-order", form)
    assert other.value.status_code == 404


def test_technician_entry_cannot_carry_an_equipment_command_or_change_facility():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Inspection(work_order_ri="cin1", request_id=uuid4(), action="set_damper", facility_id="other")


def test_retry_completes_interrupted_handoff_without_losing_private_note(monkeypatch):
    import json
    from opensoom.onem2m import CSEError

    class InterruptedStore:
        def __init__(self):
            self.rows = {}
            self.drop_summary = True

        def retrieve(self, path):
            if path not in self.rows:
                raise CSEError("No record", {"rsc": 4004})
            return {"body": {"m2m:cin": self.rows[path]}, "rqi": "read-request"}

        def create(self, parent, kind, body):
            if parent.endswith("/inspections") and self.drop_summary:
                self.drop_summary = False
                raise CSEError("Connection interrupted", {"rsc": 5103})
            item = body["m2m:cin"]
            self.rows[parent + "/" + item["rn"]] = {
                "con": item["con"], "ri": "cin-" + str(len(self.rows)), "ct": "20261119T015102",
            }

    store = InterruptedStore()
    desk = FieldDesk({"facility_id": "site", "facility_path": "mn/opensoom/facilities/site", "name": "Site",
                      "profile": "repair", "simulation": True, "zones": {}}, store)
    order = {"work_order_id": "work-1", "resource_id": "cin-order", "zone_id": "z", "asset_id": "d",
             "command_id": "cmd-1", "priority": "inspection"}
    monkeypatch.setattr(desk, "work_orders", lambda: [order])
    form = Inspection(work_order_ri="cin-order", request_id=uuid4(), action="scheduled", note="private field note")
    with pytest.raises(CSEError):
        desk.record("work-1", form)
    assert len(store.rows) == 1
    monkeypatch.setattr(desk, "work_orders", lambda: [])
    accepted = desk.record("work-1", form)
    assert len(store.rows) == 2
    assert desk.record("work-1", form)["resource_id"] == accepted["resource_id"]
    assert accepted["note"] == form.note
    for key, stored in store.rows.items():
        content = json.loads(stored["con"])
        assert content["work_order_ri"] == form.work_order_ri
        if "/inspections/" in key:
            assert "note" not in content
        else:
            assert content["note"] == form.note
