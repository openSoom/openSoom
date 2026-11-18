"""Run the installed, read-only history CLI, then join the published experimental labels."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "examples/ornl-vav"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate():
    experiments = []
    for source in json.loads((DATA / "inventory.json").read_text()):
        file = DATA / source["file"]
        process = subprocess.run([str(Path(sys.executable).with_name("opensoom-airflow-history")), str(file),
                                  "--reference-day", source["reference_day"]], capture_output=True, text=True, check=True)
        report = json.loads(process.stdout)
        for day in report["days"]:
            day["published_condition"] = source["conditions_by_date"][day["date"]]
        experiments.append({"dataset": source["dataset"], "room": source["room"], "file": source["file"],
                            "csv_gz_sha256": digest(file), **report})
    all_days = [day for exp in experiments for day in exp["days"]]
    return {"kind": "retrospective_occupied_building_trends", "captured_at": datetime.now(timezone.utc).isoformat(),
            "dataset_doi": "10.6084/m9.figshare.27948192.v2", "facility": "ORNL Flexible Research Platform, one building",
            "cli_source_sha256": digest(ROOT / "src/opensoom/airflow_history.py"),
            "extractor_sha256": digest(ROOT / "scripts/extract_ornl_vav.py"), "total_room_days": len(all_days),
            "source_rows": sum(d["rows"] for d in all_days), "occupied_rows": sum(d["occupied"] for d in all_days),
            "complete_occupied_rows": sum(d["complete_occupied"] for d in all_days),
            "method": "Workbook source conditions were attached after the CLI processed the timestamped CSV. Flow is discharge airflow in m3/h. Position is the reported BMS point. Comparison uses the reference day's occupied median, not a commissioned target.",
            "experiments": experiments}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(evaluate(), indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
    else:
        print(report, end="")
