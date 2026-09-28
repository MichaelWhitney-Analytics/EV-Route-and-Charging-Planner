$ErrorActionPreference = 'Stop'

if (-not (Test-Path 'src/planning/route_itinerary.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run this script from the EV-Route-and-Charging-Planner project root with the existing .venv.'
}

$files = @{
    'src/planning/trip_cli.py' = @'
"""Run a supplied EV itinerary: python -m src.planning.trip_cli trip.json"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from src.planning.route_itinerary import build_itinerary
from src.planning.vehicle_profile import VehicleProfile


def run_trip(request: dict) -> dict:
    """Validate JSON structure and return a serializable itinerary estimate."""
    if not isinstance(request, dict):
        raise ValueError("trip request must be a JSON object")
    try:
        vehicle = request["vehicle"]
        legs = request["leg_distances_miles"]
        powers = request["effective_stop_powers_kw"]
        start = request["start_percent"]
    except KeyError as exc:
        raise ValueError(f"missing trip field: {exc.args[0]}") from exc

    if not isinstance(vehicle, dict):
        raise ValueError("vehicle must be a JSON object")
    if not isinstance(legs, list) or not isinstance(powers, list):
        raise ValueError("legs and stop powers must be JSON arrays")

    try:
        profile = VehicleProfile(**vehicle)
    except TypeError as exc:
        raise ValueError(f"invalid vehicle fields: {exc}") from exc

    result = build_itinerary(profile, tuple(legs), start, tuple(powers))
    return {
        "vehicle_name": profile.name,
        "estimate_only": True,
        "limitations": (
            "Caller-supplied leg distances and average charging power; "
            "does not verify roads, charger availability, weather, "
            "charging curve, driving time, or queue time."
        ),
        "itinerary": asdict(result),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Estimate an EV trip from JSON")
    parser.add_argument("request_file", type=Path)
    args = parser.parse_args(argv)

    try:
        request = json.loads(args.request_file.read_text(encoding="utf-8"))
        output = run_trip(request)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        parser.exit(2, f"Trip request error: {exc}\n")

    print(json.dumps(output, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@
    'tests/test_trip_cli.py' = @'
import json

import pytest

from src.planning.trip_cli import main, run_trip


@pytest.fixture
def request():
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


def test_run_trip_returns_itinerary(request):
    result = run_trip(request)
    assert result["estimate_only"] is True
    assert result["vehicle_name"] == "Example custom EV"
    assert result["itinerary"]["total_charge_kwh"] == pytest.approx(7.5)
    assert result["itinerary"]["final_percent"] == pytest.approx(10)


def test_main_prints_json(request, tmp_path, capsys):
    path = tmp_path / "trip.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    assert main([str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["itinerary"]["total_estimated_charging_minutes"] == pytest.approx(6)


@pytest.mark.parametrize("broken", [{}, [], {"vehicle": "not an object"}])
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
'@
    'examples/sample_trip.json' = @'
{
  "vehicle": {
    "name": "Example custom EV (illustrative inputs only)",
    "usable_battery_kwh": 75.0,
    "driving_kwh_per_100_miles": 30.0,
    "max_dc_charge_kw": 150.0,
    "connector": "CCS",
    "minimum_arrival_percent": 10.0
  },
  "leg_distances_miles": [100, 100],
  "start_percent": 80,
  "effective_stop_powers_kw": [75]
}
'@
}

foreach ($path in $files.Keys) {
    if (Test-Path $path) { throw "Refusing to overwrite existing file: $path" }
}
foreach ($path in $files.Keys) {
    $parent = Split-Path $path -Parent
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [System.IO.File]::WriteAllText(
        (Join-Path (Get-Location).Path $path),
        $files[$path],
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "Created $path"
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
& .\.venv\Scripts\python.exe -m src.planning.trip_cli examples/sample_trip.json
if ($LASTEXITCODE -ne 0) { throw "Sample trip failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Tests and sample trip completed. Review the new files before committing.'