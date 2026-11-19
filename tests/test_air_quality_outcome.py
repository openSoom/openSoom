from datetime import datetime, timedelta, timezone
import pytest

from opensoom import air_quality_outcome as air
from opensoom.core import Core, OperationError
from opensoom.store import Store


T0 = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
ZONE = {"id": "cook", "pm25_warning": 45, "co2_warning": 1200}
FACILITY = {"id": "food-a", "active_run": "run-a"}
PROFILE = {"freshness_seconds": 45}
STREAM = "food-a:cook"


def at(seconds):
    return (T0 + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


def reading(native_id, t, pm=80.0, co2=1600.0, created=None, issue=None, gap=False):
    return {"cin_id": native_id, "source_cin_path": "cse/observations/" + native_id, "rqi": "read-" + native_id,
            "run_id": "run-a", "cse_created_at": at(t if created is None else created),
            "sequence_issue": issue, "gap_before": gap,
            "observation": {"source": "simulated", "observed_at": at(t), "pm25": pm, "co2": co2}}


def start(store, command_id="one", second=0, baseline=None):
    command = {"id": command_id, "facility_id": "food-a", "zone_id": "cook",
               "created_at": at(second), "expires_at": at(second+30)}
    with store.transaction():
        air.initialize(store, command, FACILITY, ZONE, PROFILE, baseline or reading("base", second-1))
        store.put("commands", command_id, command)
    return command


def ack(store, command_id="one", second=2):
    command = store.get("commands", command_id)
    command.update(ack_at=at(second), ack_source={"cin_ri": "ack-" + command_id})
    air.acknowledge(command)
    store.put("commands", command_id, command)


def observe(store, frame, now=None, run="run-a"):
    with store.transaction():
        air.observe(store, STREAM, run, frame, datetime.fromisoformat(frame["cse_created_at"] if now is None else at(now)))


def result(store, command_id="one"):
    return store.get("commands", command_id)["air_quality_outcome"]


def test_elapsed_first_joint_target_contiguous_hold_rebound_and_restart(tmp_path):
    path = tmp_path/"db"
    db = Store(path)
    start(db)
    ack(db)
    observe(db, reading("high-pm", 4, 65, 900))
    observe(db, reading("high-co2", 7, 30, 1400))
    trace = result(db)
    assert trace["baseline"]["cin_ri"] == "base"
    assert trace["time_to_target_seconds"] is None
    assert trace["change"] == {"pm25":{"decrease":50.0,"percent":62.5},"co2":{"decrease":200.0,"percent":12.5}}
    observe(db, reading("reached", 12, 45, 1200))
    assert result(db)["time_to_target_seconds"] == 10
    assert result(db)["hold_seconds"] == 0
    db = Store(path)
    good = reading("held", 30, 15, 700)
    observe(db, good)
    observe(db, good)
    trace = result(db)
    assert (trace["first_target_sample"]["cin_ri"], trace["latest"]["cin_ri"], trace["hold_seconds"]) == ("reached","held",18)
    assert trace["sample_count"] == 4
    assert len(db.air_samples("one", 0, 200)) == 4
    observe(db, reading("rebound", 32, 60, 650))
    trace = result(db)
    assert (trace["status"],trace["hold_seconds"],trace["last_hold_seconds"]) == ("outside_target",None,18)
    assert (trace["last_hold"]["start"]["cin_ri"],trace["last_hold"]["end"]["cin_ri"]) == ("reached","held")
    observe(db, reading("again", 34, 30, 660))
    assert (result(db)["hold_seconds"],result(db)["first_target_at"]) == (0,at(12))


def test_current_staleness_frozen_at_last_measured_point_and_terminal_history(tmp_path):
    store = Store(tmp_path/"db")
    start(store)
    ack(store)
    observe(store, reading("first",5,40,1000))
    observe(store, reading("second",20,32,900))
    command = store.get("commands","one")
    assert air.view(command,T0+timedelta(seconds=50))["hold_seconds"] == 15
    expired = air.view(command,T0+timedelta(seconds=70))
    assert (expired["status"],expired["hold_seconds"],expired["last_hold_seconds"]) == ("evidence_gap",None,15)
    assert result(store)["hold_seconds"] == 15
    observe(store,reading("later",80,31,890))
    assert result(store)["hold_seconds"] == 0
    assert result(store)["last_hold_seconds"] == 15
    observe(store,reading("new-run",85,5,550),run="run-b")
    historical = air.view(store.get("commands","one"),T0+timedelta(days=10))
    assert (historical["status"],historical["latest"]["cin_ri"],historical["last_hold_seconds"]) == ("run_ended","later",0)
    assert all(x["cin_ri"]!="new-run" for x in store.air_samples("one",0,200))


def test_no_ack_legacy_supersession_and_request_only_cases(tmp_path):
    store = Store(tmp_path/"db")
    command = start(store)
    observe(store,reading("no-ack",3,20,700))
    assert air.view(command,T0+timedelta(seconds=31))["status"] == "timed_out"
    assert result(store)["sample_count"] == 0
    start(store,"two",second=35)
    ack(store,"one",second=36)
    observe(store,reading("late-ack-for-one",37,20,700))
    assert result(store,"one")["status"] == "superseded"
    assert result(store,"two")["status"] == "awaiting_ack"
    ack(store,"two",second=38)
    observe(store,reading("two-frame",40,20,700))
    assert result(store,"one")["latest"] is None
    assert result(store,"two")["time_to_target_seconds"] == 2
    assert air.view({"id":"pre-upgrade"}) is None


@pytest.mark.parametrize("invalid",[
    reading("partial", 9, None, 800),
    reading("clock-anomaly", 500, 30, 800, created=9, issue="future_at_ingest"),
    reading("old", 9, 33, 700, created=62)
])
def test_quality_gaps_close_and_restart_observed_span(tmp_path, invalid):
    store = Store(tmp_path/"db")
    start(store)
    ack(store)
    observe(store, reading("good1",4,40,900))
    observe(store, reading("good2",8,35,800))
    observe(store, invalid)
    assert (result(store)["status"],result(store)["hold_seconds"],result(store)["last_hold_seconds"]) == ("evidence_gap",None,4)
    assert result(store)["latest"]["cin_ri"] == "good2"
    t = max(11, (datetime.fromisoformat(invalid["cse_created_at"])-T0).total_seconds()+1)
    observe(store, reading("new-pair-start",t,32,750))
    assert result(store)["hold_seconds"] == 0


def test_conflicting_values_withdraw_a_prior_point_but_retain_both_native_records(tmp_path):
    store = Store(tmp_path/"db")
    start(store)
    ack(store)
    observe(store, reading("outside",4,65,900))
    observe(store, reading("apparent-target",8,35,800))
    observe(store, reading("contradiction",8,85,800,created=9,issue="conflicting_measurements"))
    trace = result(store)
    assert trace["first_target_at"] is None
    assert trace["hold_seconds"] is None
    assert trace["latest"]["cin_ri"] == "outside"
    assert trace["sample_count"] == 1
    history = store.air_samples("one",0,20)
    assert history[-1]["invalidates_cin_ri"] == history[-2]["cin_ri"]
    observe(store,reading("agreed",11,30,700))
    assert result(store)["time_to_target_seconds"] == 9


def test_native_gap_and_pre_ack_sample_boundaries_and_zero_baseline(tmp_path):
    store = Store(tmp_path/"db")
    start(store,baseline=reading("zero",-2,0.0,0.0))
    ack(store)
    observe(store,reading("late-pre-ack",1,25,800,created=3))
    observe(store,reading("too-early-on-cse-clock",3,20,650,created=2))
    assert result(store)["latest"] is None
    observe(store,reading("a",4,25,850))
    assert result(store)["change"] == {"pm25":{"decrease":-25,"percent":None},"co2":{"decrease":-850,"percent":None}}
    observe(store,reading("b",7,20,750))
    observe(store,reading("gap",10,18,700,gap=True))
    trace = result(store)
    assert trace["hold_seconds"] == 0
    assert trace["last_hold_seconds"] == 3
    assert trace["last_hold"]["ended_by"] == "unobserved_interval"


def test_missing_native_record_reported_by_late_pre_ack_sample_ends_hold(tmp_path):
    store = Store(tmp_path / "db")
    start(store)
    ack(store)
    observe(store, reading("within-1", 4, 35, 800))
    observe(store, reading("within-2", 6, 33, 800))
    observe(store, reading("delayed", 1, 30, 800, created=8, gap=True, issue="unobserved_interval"))
    trace = result(store)
    assert (trace["status"], trace["hold_seconds"], trace["last_hold_seconds"]) == ("evidence_gap", None, 2)
    assert trace["latest"]["cin_ri"] == "within-2"
    assert trace["sample_count"] == 2
    assert store.air_samples("one", 0, 10)[-1]["cin_ri"] == "delayed"
    observe(store, reading("within-3", 10, 31, 800))
    trace = result(store)
    assert (trace["hold_seconds"], trace["last_hold_seconds"], trace["first_target_at"]) == (0, 2, at(4))


def test_command_history_pagination_and_facility_scope(tmp_path):
    service = Core(runtime=tmp_path)
    try:
        start(service.store)
        ack(service.store)
        for i in range(3,6):
            observe(service.store,reading(str(i),i,20,800))
        actor = {"role":"observer","facilities":["food-a"]}
        page = service.air_quality_history("one",actor,0,2)
        page2 = service.air_quality_history("one",actor,page["next_after"],2)
        assert [v["cin_ri"] for v in page["samples"]+page2["samples"]] == ["3","4","5"]
        assert page2["next_after"] is None
        with pytest.raises(OperationError,match="cannot access"):
            service.air_quality_history("one",{"role":"observer","facilities":["learning-b"]},0,2)
    finally:
        service.cse.close()
