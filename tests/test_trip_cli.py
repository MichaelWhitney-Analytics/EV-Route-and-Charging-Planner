import json

import pytest

from src.planning.trip_cli import main, run_trip


@pytest.fixture
def trip_request():
    return {
        "vehicle": {
            "name": "Example custom EV",
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


def test_run_trip_returns_itinerary(trip_request):
    result = run_trip(trip_request)

    assert result["estimate_only"] is True
    assert result["vehicle_name"] == "Example custom EV"
    assert result["itinerary"]["total_charge_kwh"] == pytest.approx(7.5)
    assert result["itinerary"]["final_percent"] == pytest.approx(10)


def test_main_prints_json(trip_request, tmp_path, capsys):
    path = tmp_path / "trip.json"
    path.write_text(json.dumps(trip_request), encoding="utf-8")

    assert main([str(path)]) == 0

    result = json.loads(capsys.readouterr().out)

    assert (
        result["itinerary"]["total_estimated_charging_minutes"]
        == pytest.approx(6)
    )


@pytest.mark.parametrize(
    "broken",
    [
        {},
        [],
        {"vehicle": "not an object"},
    ],
)
def test_rejects_invalid_request(broken):
    with pytest.raises(ValueError):
        run_trip(broken)


def test_main_rejects_invalid_json(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main([str(path)])

    assert exc.value.code == 2
    assert "Trip request error" in capsys.readouterr().err


def test_main_rejects_missing_file(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path / "missing.json")])

    assert exc.value.code == 2
    assert "Trip request error" in capsys.readouterr().err