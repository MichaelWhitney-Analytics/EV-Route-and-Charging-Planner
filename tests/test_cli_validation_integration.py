from copy import deepcopy
import json

import pytest

from src.planning.trip_cli import main, run_trip


@pytest.fixture
def valid_trip():
    return {
        "vehicle": {
            "name": "Test EV",
            "usable_battery_kwh": 75.0,
            "driving_kwh_per_100_miles": 30.0,
            "max_dc_charge_kw": 150.0,
            "connector": "CCS",
            "minimum_arrival_percent": 10.0,
        },
        "leg_distances_miles": [100, 100],
        "start_percent": 80,
        "effective_stop_powers_kw": [75],
    }


def test_validated_request_still_produces_itinerary(valid_trip):
    result = run_trip(valid_trip)
    assert result["itinerary"]["total_charge_kwh"] == pytest.approx(7.5)


def test_cli_rejects_unknown_field(valid_trip, tmp_path, capsys):
    payload = deepcopy(valid_trip)
    payload["unexpected"] = True
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main([str(path)])
    assert exc.value.code == 2
    assert "unknown trip fields" in capsys.readouterr().err


def test_cli_rejects_boolean_battery(valid_trip, tmp_path, capsys):
    payload = deepcopy(valid_trip)
    payload["vehicle"]["usable_battery_kwh"] = True
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main([str(path)])
    assert exc.value.code == 2
    assert "usable_battery_kwh" in capsys.readouterr().err


def test_cli_rejects_nonstandard_nan(valid_trip, tmp_path, capsys):
    payload = deepcopy(valid_trip)
    payload["start_percent"] = float("nan")
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main([str(path)])
    assert exc.value.code == 2
    assert "start_percent" in capsys.readouterr().err