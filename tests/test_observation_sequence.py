from datetime import datetime, timedelta, timezone

import pytest

from opensoom.core import Core
from opensoom.models import Observation
from opensoom.policy import diagnose


def frame(at, airflow):
    return Observation(facility_id="food-a", zone_id="cook", observed_at=at.isoformat(), adapter="vendor-a",
                       pm25=10, co2=600, airflow=airflow, fan_running=True, damper_pct=95)


@pytest.mark.parametrize("legacy_age,run_age,retained", [(0,30,True),(600,30,False),(-20,1,False)])
def test_legacy_watermark_survives_restart_without_locking_new_run_or_future_time(
        tmp_path, monkeypatch, legacy_age, run_age, retained):
    now = datetime.now(timezone.utc)
    service = Core(runtime=tmp_path)
    fid, zid = "food-a", "cook"
    zone = {**service.profiles["food-production"]["zones"][0], "path":"cse/site/cook"}
    facility = {"id":fid,"profile":"food-production","active_run":"run","zones":[zone]}
    monkeypatch.setattr(service,"facility",lambda _:facility)
    monkeypatch.setattr(service,"evaluate",lambda *_:None)
    monkeypatch.setitem(service.identities,"diagnostic","Cdiagnostic")
    service.store.put("runs","run",{"started_at":(now-timedelta(seconds=run_age)).isoformat()})
    old = frame(now+timedelta(seconds=legacy_age),950)
    if run_age == 1:
        old.received_at = (now-timedelta(seconds=10)).isoformat()
    service.store.put("observations",fid+":"+zid,{"cin_id":"old","observation":old.model_dump()})
    incoming = frame(now-timedelta(seconds=40),360)
    cin = {"ri":"new","rn":"new","ct":now.strftime("%Y%m%dT%H%M%S,%f"),"con":incoming.model_dump()}
    monkeypatch.setattr(service.cse,"retrieve",lambda *args,**kwargs:{"body":{"m2m:cin":cin},"rqi":"native-read"})
    assert service.refresh_observation(fid,zid)["cin_id"] == ("old" if retained else "new")
    service.cse.close()


def test_future_frame_does_not_become_control_evidence_when_wall_clock_catches_up():
    instant = datetime.now(timezone.utc)
    observation = frame(instant,1000)
    profile = Core.load_profiles()["food-production"]
    result = diagnose(observation,profile["zones"][0],profile,now=instant+timedelta(seconds=1),
                      sequence_issue="future_at_ingest")
    assert result["status"] == "stale"


def test_native_creation_time_with_explicit_offset_preserves_the_instant(tmp_path, monkeypatch):
    service = Core(runtime=tmp_path)
    now = datetime.now(timezone.utc)
    zone = {**service.profiles["food-production"]["zones"][0], "path":"cse/site/cook"}
    monkeypatch.setattr(service,"facility",lambda _:{"id":"food-a","profile":"food-production","zones":[zone]})
    monkeypatch.setattr(service,"evaluate",lambda *_:None)
    monkeypatch.setitem(service.identities,"diagnostic","Cdiagnostic")
    observation = frame(now+timedelta(minutes=1),1100)
    # Native UTC and an explicit +09:00 representation denote the same creation instant.
    local_creation = now.astimezone(timezone(timedelta(hours=9))).isoformat()
    cin = {"ri":"cin-1","rn":"cin-1","ct":local_creation,"con":observation.model_dump()}
    monkeypatch.setattr(service.cse,"retrieve",lambda *args,**kwargs:{"body":{"m2m:cin":cin},"rqi":"native-read"})
    admitted = service.refresh_observation("food-a","cook")
    assert admitted["sequence_issue"] == "future_at_ingest"
    assert admitted["measured_through"] is None
    assert datetime.fromisoformat(admitted["cse_created_at"]) == now
    service.cse.close()
