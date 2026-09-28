$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'src/planning/trip_cli.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the EV-Route-and-Charging-Planner project root with its existing .venv.'
}
$files = @{
    'src/planning/trip_report.py' = @'
"""Print a readable itinerary: python -m src.planning.trip_report trip.json"""

import argparse
import json
from pathlib import Path

from src.planning.trip_cli import run_trip


def format_trip_report(output: dict) -> str:
    """Format an already calculated trip result for terminal reading."""
    if not isinstance(output, dict) or "itinerary" not in output:
        raise ValueError("output must contain an itinerary")
    itinerary = output["itinerary"]
    lines = [
        f"Vehicle: {output['vehicle_name']}",
        "ESTIMATE ONLY - supplied distances and charging powers are not verified.",
        f"Total distance: {itinerary['total_distance_miles']:.1f} miles",
        f"Energy added: {itinerary['total_charge_kwh']:.1f} kWh",
        f"Estimated charging: {itinerary['total_estimated_charging_minutes']:.1f} minutes",
        f"Final charge: {itinerary['final_percent']:.1f}%",
        "",
    ]
    stops = {stop["after_leg_number"]: stop for stop in itinerary["stops"]}
    for number, leg in enumerate(itinerary["legs"], start=1):
        lines.append(
            f"Leg {number}: {leg['distance_miles']:.1f} miles; "
            f"{leg['start_percent']:.1f}% -> {leg['estimated_arrival_percent']:.1f}%"
        )
        if number in stops:
            stop = stops[number]
            lines.append(
                f"  Stop after leg {number}: add {stop['charge']['energy_to_add_kwh']:.1f} kWh; "
                f"depart at {stop['charge']['departure_percent']:.1f}%; "
                f"estimated {stop['time']['estimated_minutes']:.1f} minutes"
            )
    lines.extend(["", f"Limitations: {output['limitations']}"])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Print a readable EV trip estimate")
    parser.add_argument("request_file", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.request_file.read_text(encoding="utf-8"))
        output = run_trip(payload)
        report = format_trip_report(output)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Trip request error: {exc}\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@
    'tests/test_trip_report.py' = @'
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
'@
}
foreach ($path in $files.Keys) {
    if (Test-Path $path) { throw "Refusing to overwrite existing file: $path" }
}
foreach ($path in $files.Keys) {
    $parent = Split-Path $path -Parent
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $path), $files[$path], [System.Text.UTF8Encoding]::new($false))
    Write-Host "Created $path"
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
& .\.venv\Scripts\python.exe -m src.planning.trip_report examples/sample_trip.json
if ($LASTEXITCODE -ne 0) { throw "Readable report failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Review the new files and report before committing.'