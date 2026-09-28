import json

import pytest

from src.planning.trip_cli import run_trip
from src.planning.trip_report import format_trip_report, main


@pytest.fixture
def trip_payload():
    return {
        "vehicle": {
            "name": "Example EV", "usable_battery_kwh": 75.0,
            "driving_kwh_per_100_miles": 30.0, "max_dc_charge_kw": 150.0,
            "connector": "CCS", "minimum_arrival_percent": 10.0,
        },
        "leg_distances_miles": [100, 100],
        "start_percent": 80,
        "effective_stop_powers_kw": [75],
    }


def test_format_shows_legs_stop_and_limitations(trip_payload):
    text = format_trip_report(run_trip(trip_payload))
    assert "ESTIMATE ONLY" in text
    assert "Leg 1: 100.0 miles" in text
    assert "Leg 2: 100.0 miles" in text
    assert "add 7.5 kWh" in text
    assert "estimated 6.0 minutes" in text
    assert "Final charge: 10.0%" in text
    assert "Limitations:" in text


def test_main_prints_readable_result(trip_payload, tmp_path, capsys):
    path = tmp_path / "trip.json"
    path.write_text(json.dumps(trip_payload), encoding="utf-8")
    assert main([str(path)]) == 0
    assert "Total distance: 200.0 miles" in capsys.readouterr().out


def test_main_reports_invalid_request(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main([str(path)])
    assert exc.value.code == 2
    assert "Trip request error" in capsys.readouterr().err


def test_format_rejects_missing_itinerary():
    with pytest.raises(ValueError, match="itinerary"):
        format_trip_report({})