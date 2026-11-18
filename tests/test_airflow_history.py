import csv
from datetime import date

import pytest

from opensoom.airflow_history import COLUMNS, summarize_history


def write_samples(path, samples):
    with path.open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(COLUMNS)
        writer.writerows(samples)


def test_history_uses_only_complete_occupied_samples_and_keeps_zero(tmp_path):
    path = tmp_path / "measurements.csv"
    write_samples(path, [
        ("2024-01-01T07:00", "1", 0, 0), ("2024-01-01T07:01", "1", 100, 80),
        ("2024-01-01T07:02", "0", 300, 0), ("2024-01-01T07:03", "", 500, 0),
        ("2024-01-02T07:00", "1", 50, 20), ("2024-01-02T07:01", "1", 60, "NAN"),
    ])
    result = summarize_history(path, date(2024, 1, 1))
    reference, followup = result["days"]
    assert result["reference_median_airflow_m3_h"] == 50
    assert reference["unknown_mode"] == 1 and reference["reported_position_varied"] is True
    assert followup["complete_occupied"] == 1 and followup["excluded_incomplete_occupied"] == 1
    assert followup["reported_position_varied"] is None


@pytest.mark.parametrize("bad_record,problem", [
    (("2024-01-01T07:00", "1", 80, 20), "Duplicate"),
    (("2024-01-01T07:01+01:00", "1", 80, 20), "Use consistent"),
    (("2024-01-01T07:01", "1", "inf", 30), "Out-of-range"),
    (("2024-01-01T07:01", "1", 50, 101), "Out-of-range"),
    (("2024-01-01T07:01", "on", 50, 40), "Expected occupied"),
])
def test_bad_history_is_identified_by_line(tmp_path, bad_record, problem):
    path = tmp_path / "readings.csv"
    write_samples(path, [("2024-01-01T07:00", "1", 100, 10), bad_record])
    with pytest.raises(ValueError, match="CSV row 3: " + problem):
        summarize_history(path, date(2024, 1, 1))
