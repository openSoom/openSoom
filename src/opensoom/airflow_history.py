"""Inspect one zone's historical BMS trends without connecting to the control system."""
import argparse
import csv
from datetime import date, datetime
import gzip
import json
import math
from pathlib import Path
from statistics import median

COLUMNS = ("site_local_time", "occupied", "airflow_m3_h", "reported_damper_pct")


def measurement(raw, name):
    if raw is None:
        raise ValueError(f"Missing column value for {name}")
    text = raw.strip()
    if text.upper() in ("", "NA", "NAN"):
        return None
    value = float(text)
    if not math.isfinite(value) or value < 0 or (name == "reported_damper_pct" and value > 100):
        raise ValueError(f"Out-of-range {name}")
    return value


def summarize_history(path: Path, reference_day: date) -> dict:
    """Group by recorded site-local date. Only complete occupied samples enter the comparison."""
    days = {}
    seen = set()
    timezone_aware = None
    open_file = gzip.open if path.suffix.lower() == ".gz" else open
    with open_file(path, "rt", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or not set(COLUMNS).issubset(headers):
            raise ValueError("CSV needs unique column names including " + ", ".join(COLUMNS))
        for line, row in enumerate(reader, 2):
            try:
                stamp = datetime.fromisoformat(row["site_local_time"])
                if "T" not in row["site_local_time"] and " " not in row["site_local_time"]:
                    raise ValueError("Expected a date and time")
                has_offset = stamp.utcoffset() is not None
                if timezone_aware is None:
                    timezone_aware = has_offset
                elif timezone_aware != has_offset:
                    raise ValueError("Use consistent local timestamps, either all with offsets or all without")
                if stamp in seen:
                    raise ValueError("Duplicate timestamp in this zone")
                seen.add(stamp)
                group = days.setdefault(stamp.date(), {"rows": 0, "occupied": 0, "unknown_mode": 0, "flows": [], "positions": []})
                group["rows"] += 1
                mode = (row["occupied"] or "").strip()
                if mode.upper() in ("", "NAN", "NA"):
                    group["unknown_mode"] += 1
                    continue
                if mode not in ("0", "1"):
                    raise ValueError("Expected occupied 0 or 1")
                if mode == "0":
                    continue
                group["occupied"] += 1
                flow = measurement(row["airflow_m3_h"], "airflow_m3_h")
                position = measurement(row["reported_damper_pct"], "reported_damper_pct")
                if flow is not None and position is not None:
                    group["flows"].append(flow)
                    group["positions"].append(position)
            except (TypeError, ValueError) as error:
                raise ValueError(f"CSV row {line}: {error}") from error
    reference = days.get(reference_day)
    if not reference or len(reference["flows"]) < 2:
        raise ValueError("Reference date needs at least two distinct complete occupied samples")
    reference_flow = median(reference["flows"])
    result = []
    for day, sample in sorted(days.items()):
        flows, positions = sample["flows"], sample["positions"]
        count = len(flows)
        typical = median(flows) if count else None
        result.append({
            "date": day.isoformat(), "rows": sample["rows"], "occupied": sample["occupied"],
            "unknown_mode": sample["unknown_mode"], "complete_occupied": count,
            "excluded_incomplete_occupied": sample["occupied"] - count,
            "median_airflow_m3_h": typical,
            "median_flow_difference_from_reference_m3_h": None if typical is None else typical - reference_flow,
            "reported_damper_min_pct": min(positions) if count else None,
            "reported_damper_max_pct": max(positions) if count else None,
            "reported_position_varied": len(set(positions)) > 1 if count >= 2 else None,
        })
    return {"reference_date": reference_day.isoformat(), "reference_median_airflow_m3_h": reference_flow, "days": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="One zone per CSV or CSV.GZ, one row per acquisition")
    parser.add_argument("--reference-day", type=date.fromisoformat, required=True, help="Site-local comparison date YYYY-MM-DD")
    args = parser.parse_args()
    try:
        result = summarize_history(args.csv, args.reference_day)
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(2, f"{error}\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
