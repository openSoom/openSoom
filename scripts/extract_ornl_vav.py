"""Rebuild the distributed airflow subsets from the five pinned Figshare v2 workbooks.

Requires openpyxl for reading the source only. Run from the repository root.
The application CLI consumes CSV and uses only the Python standard library.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ("room106", "damper-106", 106, 52700693, "833f63778fd7ef35b42f4656c0d4285c7e1a5e0ce4c0e794f8b11cab745877a3"),
    ("room104", "damper-104", 104, 52700696, "6068259959c6e9ad586f93b29e5d3ff02e555ae2e2eaa335cfa12e4090c46eab"),
    ("room205", "damper-205", 205, 52700699, "a854a1774d5579edac23ba2c9640a922b3d0f7fbbb6315a45032a2b890b3bc60"),
    ("air205a", "airflow-bias-205-a", 205, 52700702, "07951d8675e15eaea4fcee41dbbc75bf9d5e7b9efb93024a2361548d62939b43"),
    ("air205b", "airflow-bias-205-b", 205, 52700690, "14f36d13eccf29f7f7758dca365cd8efb7e4b7327413fa8e61be63f0bc67a0c8"),
]


def export_number(value, factor=1):
    if value is None or str(value).strip().upper() in ("NAN", "NA", ""):
        return ""
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Unexpected source value {value!r}")
    return format(value * factor, ".12g")


def extract(root, output):
    inventory = []
    output.mkdir(parents=True, exist_ok=True)
    for local, label, room, file_id, expected in FILES:
        path = root / f"{local}.xlsx"
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source checksum mismatch for {path.name}")
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        destination = output / f"{label}.csv.gz"
        days = {}
        columns = ["TIMESTAMP", "Occupancy Mode Indicator", f"VAV Box - Room {room}: Discharge Airflow Rate",
                   f"VAV Box - Room {room}: VAV Damper Opening"]
        try:
            with destination.open("wb") as stream, gzip.GzipFile(filename="", fileobj=stream, mode="wb", mtime=0) as archive:
                with io.TextIOWrapper(archive, encoding="utf-8", newline="") as text:
                    writer = csv.writer(text, lineterminator="\n")
                    writer.writerow(["site_local_time", "occupied", "airflow_m3_h", "reported_damper_pct"])
                    for sheet in book:
                        rows = iter(sheet.values)
                        header, units = next(rows), next(rows)
                        indices = [header.index(column) for column in columns]
                        if (units[indices[2]], units[indices[3]]) != ("m3/min", "%"):
                            raise ValueError(f"Unexpected units in {sheet.title}")
                        for row in rows:
                            stamp, mode, flow, position = (row[i] for i in indices)
                            day = stamp.date().isoformat()
                            if days.setdefault(day, sheet.title) != sheet.title:
                                raise ValueError("Overlapping test days")
                            writer.writerow([stamp.isoformat(timespec="milliseconds"), export_number(mode),
                                             export_number(flow, 60), export_number(position)])
        finally:
            book.close()
        reference, = (day for day, condition in days.items() if condition == "Fault-Free")
        inventory.append({"dataset": label, "room": room, "source_file_id": file_id, "source_sha256": expected,
                          "download_as": path.name, "file": destination.name, "reference_day": reference,
                          "conditions_by_date": days})
    (output / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory containing the five original files under their download_as names")
    parser.add_argument("--output", type=Path, default=ROOT / "examples/ornl-vav")
    args = parser.parse_args()
    extract(args.source_dir, args.output)
