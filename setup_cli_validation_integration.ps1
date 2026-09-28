$ErrorActionPreference = 'Stop'
$cliPath = 'src/planning/trip_cli.py'
$testPath = 'tests/test_cli_validation_integration.py'

if (-not (Test-Path $cliPath) -or -not (Test-Path 'src/validation/trip_request.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the project root after installing the CLI and validation modules.'
}
if (Test-Path $testPath) { throw "Refusing to overwrite existing file: $testPath" }
$old = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $cliPath))
if (-not $old.Contains('def run_trip(request: dict) -> dict:') -or $old.Contains('from src.validation.trip_request import validate_trip_request')) {
    throw 'CLI does not match the expected pre-integration version. No files were changed.'
}

$cli = @'
"""Run a supplied EV itinerary: python -m src.planning.trip_cli trip.json"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from src.planning.route_itinerary import build_itinerary
from src.planning.vehicle_profile import VehicleProfile
from src.validation.trip_request import validate_trip_request


def run_trip(request: dict) -> dict:
    """Validate the JSON request and return a serializable itinerary estimate."""
    validate_trip_request(request)
    profile = VehicleProfile(**request["vehicle"])
    result = build_itinerary(
        profile,
        tuple(request["leg_distances_miles"]),
        request["start_percent"],
        tuple(request["effective_stop_powers_kw"]),
    )
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
$tests = @'
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
'@

[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $cliPath), $cli, [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $testPath), $tests, [System.Text.UTF8Encoding]::new($false))
Write-Host "Updated $cliPath"
Write-Host "Created $testPath"

& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
& .\.venv\Scripts\python.exe -m src.planning.trip_cli examples/sample_trip.json
if ($LASTEXITCODE -ne 0) { throw "Sample trip failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Tests and sample completed. Review the changes before committing.'