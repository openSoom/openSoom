"""Track measured air quality for one ventilation command from accepted oneM2M records."""
from datetime import datetime, timezone


def seconds_between(later, earlier):
    return round((datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).total_seconds(), 3)


def sample(record):
    observation = record["observation"]
    return {"observed_at": observation["observed_at"], "cin_ri": record["cin_id"],
            "cin_path": record["source_cin_path"], "read_rqi": record["rqi"],
            "pm25": observation["pm25"], "co2": observation["co2"]}


def initialize(store, command, facility, zone, profile, record):
    key = facility["id"] + ":" + zone["id"]
    finish(store, key, "superseded", command["created_at"])
    before = None
    baseline_age = seconds_between(command["created_at"], record["observation"]["observed_at"])
    if (record.get("cin_id") and record.get("source_cin_path") and record.get("rqi")
            and record.get("run_id") == facility.get("active_run") and not record.get("sequence_issue")
            and 0 <= baseline_age <= profile["freshness_seconds"]):
        before = sample(record)
    command["air_quality_outcome"] = {
        "status": "awaiting_ack", "source": record["observation"].get("source", "simulated"),
        "baseline": before, "latest": None, "targets": {"pm25": zone["pm25_warning"], "co2": zone["co2_warning"]},
        "freshness_seconds": profile["freshness_seconds"], "ack_at": None, "ack_cin_ri": None,
        "first_target_at": None, "first_target_sample": None, "time_to_target_seconds": None,
        "hold_started_at": None, "hold_start_sample": None, "hold_seconds": None,
        "last_hold": None, "last_hold_seconds": None, "sample_count": 0, "last_sample_status": None,
        "last_event": None, "change": {"pm25": None, "co2": None}}
    store.put("active_air_quality", key, {"command_id": command["id"], "source_run": facility.get("active_run")})


def end_hold(outcome, reason):
    if outcome["hold_start_sample"] is None:
        return
    outcome["last_hold"] = {"start": outcome["hold_start_sample"], "end": outcome["latest"],
                            "seconds": outcome["hold_seconds"], "ended_by": reason}
    outcome["last_hold_seconds"] = outcome["hold_seconds"]
    outcome.update(hold_start_sample=None, hold_started_at=None, hold_seconds=None)


def finish(store, key, reason, ended_at):
    active = store.get("active_air_quality", key)
    if not active:
        return
    command = store.get("commands", active["command_id"])
    if command and (outcome := command.get("air_quality_outcome")):
        reason_hold = reason
        if outcome["latest"] and seconds_between(ended_at, outcome["latest"]["observed_at"]) > outcome["freshness_seconds"]:
            reason_hold = "stale_silence"
        end_hold(outcome, reason_hold)
        outcome.update(status=reason, ended_at=ended_at)
        store.put("commands", command["id"], command)
        store.delete("air_quality_before_latest", command["id"])
    store.delete("active_air_quality", key)


def acknowledge(command):
    outcome = command.get("air_quality_outcome")
    if outcome and outcome["status"] == "awaiting_ack":
        outcome.update(status="awaiting_sample", ack_at=command["ack_at"], ack_cin_ri=command["ack_source"]["cin_ri"])


def observe(store, key, source_run, record, now):
    active = store.get("active_air_quality", key)
    if not active:
        return
    if active["source_run"] != source_run:
        finish(store, key, "run_ended", now.isoformat())
        return
    command = store.get("commands", active["command_id"])
    outcome = command["air_quality_outcome"]
    ack = outcome["ack_at"]
    if not ack or datetime.fromisoformat(record["cse_created_at"]) <= datetime.fromisoformat(ack):
        return
    point = sample(record)
    age = (now - datetime.fromisoformat(point["observed_at"])).total_seconds()
    issue = record.get("sequence_issue")
    if seconds_between(point["observed_at"], ack) <= 0:
        return
    if not issue and (age < -5 or age > outcome["freshness_seconds"]):
        issue = "sample_not_fresh"
    if not issue and (point["pm25"] is None or point["co2"] is None):
        issue = "incomplete_air_quality"
    if issue:
        status = "evidence_gap"
    elif all(point[name] <= limit for name, limit in outcome["targets"].items()):
        status = "in_target"
    else:
        status = "outside_target"

    # The observation row, immutable evidence and derived command summary share
    # the caller's SQLite transaction. Notifications can safely be redelivered.
    event = {**point, "status": status, "issue": issue, "gap_before": bool(record.get("gap_before")),
             "cse_created_at": record["cse_created_at"]}
    previous = outcome["latest"]
    disputed = (issue == "conflicting_measurements" and previous
                and previous["observed_at"] == point["observed_at"])
    if disputed:
        event["invalidates_cin_ri"] = previous["cin_ri"]
    seq = store.append_air_sample(command["id"], event)
    if seq is None:
        return
    event["sequence"] = seq
    if disputed:
        # A second value at the very same acquisition time withdraws the
        # earlier point as proof. Both original CINs remain in the audit trail.
        outcome = store.get("air_quality_before_latest", command["id"])
        command["air_quality_outcome"] = outcome
    elif status != "evidence_gap":
        store.put("air_quality_before_latest", command["id"], outcome)
    if record.get("gap_before"):
        end_hold(outcome, "unobserved_interval")
    if outcome["last_event"] and seconds_between(record["cse_created_at"], outcome["last_event"]["cse_created_at"]) > outcome["freshness_seconds"]:
        end_hold(outcome, "stale_silence")
    if outcome["latest"] and seconds_between(point["observed_at"], outcome["latest"]["observed_at"]) > outcome["freshness_seconds"]:
        end_hold(outcome, "sample_gap")
    if status != "in_target":
        end_hold(outcome, issue or "above_target")
    elif outcome["hold_start_sample"] is None:
        outcome.update(hold_start_sample=point, hold_started_at=point["observed_at"], hold_seconds=0.0)
    else:
        outcome["hold_seconds"] = seconds_between(point["observed_at"], outcome["hold_started_at"])
    if status == "in_target" and outcome["first_target_sample"] is None:
        outcome.update(first_target_sample=point, first_target_at=point["observed_at"],
                       time_to_target_seconds=seconds_between(point["observed_at"], ack))
    if status != "evidence_gap":
        outcome["latest"] = point
        outcome["sample_count"] += 1
        if outcome["baseline"]:
            for name in outcome["targets"]:
                before = outcome["baseline"][name]
                decrease = before - point[name]
                outcome["change"][name] = {"decrease": round(decrease, 6),
                                            "percent": round(100 * decrease / before, 2) if before else None}
    outcome.update(status=status, last_sample_status=status, last_event=event)
    store.put("commands", command["id"], command)


def view(command, now=None):
    """Historical duration always ends at an observed sample, including during silence."""
    outcome = command.get("air_quality_outcome")
    if not outcome:
        return None
    now = now or datetime.now(timezone.utc)
    if outcome["status"] == "awaiting_ack" and datetime.fromisoformat(command["expires_at"]) < now:
        return {**outcome, "status": "timed_out"}
    if outcome["status"] in ("in_target", "outside_target", "awaiting_sample"):
        as_of = (outcome["latest"] or {}).get("observed_at") or outcome["ack_at"]
        if (now - datetime.fromisoformat(as_of)).total_seconds() > outcome["freshness_seconds"]:
            outcome = dict(outcome)
            end_hold(outcome, "stale_silence")
            outcome["status"] = "evidence_gap"
    return outcome
