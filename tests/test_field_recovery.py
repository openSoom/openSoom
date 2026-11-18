from copy import deepcopy

import pytest

from opensoom.maintenance_worker import MaintenanceWorker
from opensoom.mec_sensor import EvidenceError


def test_recovery_requires_the_original_ack_and_distinct_qualifying_acquisitions():
    worker = object.__new__(MaintenanceWorker)
    t0, t1, t2 = (f"2026-11-19T09:00:0{i}+00:00" for i in range(3))
    refs = [{"cin_ri": f"cin-{i}", "cin_path": f"observations/sample-{i}", "observed_at": instant}
            for i, instant in enumerate((t1, t2), 1)]
    ack = {"facility_id": "food-a", "zone_id": "cook", "incident_id": "incident", "command_id": "cmd",
           "ack_at": t0, "value": 95, "device_state": "damper_changed"}
    native = {"ack": ack, **{r["cin_ri"]: {"observed_at": r["observed_at"], "airflow": 905, "pm25": 10,
                                             "co2": 500, "fan_running": True} for r in refs}}
    worker.zone_record = lambda event, stream, ref: (native[ref["cin_ri"]], "native-" + ref["cin_ri"])
    reports = []
    worker.work_order = lambda *args, **data: reports.append((args, data))
    event = {"command_id": "cmd", "incident_id": "incident", "requested_pct": 95, "ack_at": t0,
             "ack_source": {"cin_ri": "ack", "cin_path": "acks/one"}, "source_cin_ri": refs[-1]["cin_ri"],
             "source_cin_path": refs[-1]["cin_path"], "observed_at": t2, "recovery_observations": refs,
             "required_samples": 2, "profile_version": 1, "verified_at": t2,
             "limits": {"minimum_airflow": 900, "pm25_warning": 35, "co2_warning": 1000, "freshness_seconds": 10}}
    worker.recovered(event, {"ri": "outcome"})
    assert len(reports) == 1 and reports[0][1]["recovery"]["ack"]["read_rqi"] == "native-ack"
    reports.clear()
    with pytest.raises(EvidenceError):
        worker.recovered({**event, "ack_at": t1}, {"ri": "bad-ack"})
    with pytest.raises(EvidenceError):
        worker.recovered({**event, "recovery_observations": [refs[1], refs[1]]}, {"ri": "duplicate"})
    override = deepcopy(refs)
    override[0]["observed_at"] = t0
    with pytest.raises(EvidenceError):
        worker.recovered({**event, "recovery_observations": override}, {"ri": "time"})
    with pytest.raises(EvidenceError):
        worker.recovered({**event, "verified_at": "2026-11-19T09:01:00+00:00"}, {"ri": "expired"})
    native["cin-2"]["pm25"] = 80
    with pytest.raises(EvidenceError):
        worker.recovered(event, {"ri": "high-particles"})
    assert reports == []
