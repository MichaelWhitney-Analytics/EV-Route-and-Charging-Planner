$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'src/ingestion/route_station_candidates.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the EV-Route-and-Charging-Planner project root with its existing .venv.'
}
$files = @{
    'src/planning/station_detour.py' = @'
"""Measure road detour for one explicitly chosen candidate station."""

import argparse
import json
from math import isfinite

from src.ingestion.live_road_route import get_road_route


def compare_station_detour(
    start_lat: float, start_lon: float,
    station_lat: float, station_lon: float,
    end_lat: float, end_lon: float,
) -> dict:
    """Compare direct road route with start -> station -> destination.

    Makes three routing calls. Does not select a charger or assume it works.
    """
    for name, value, low, high in (
        ("start_lat", start_lat, -90, 90), ("start_lon", start_lon, -180, 180),
        ("station_lat", station_lat, -90, 90), ("station_lon", station_lon, -180, 180),
        ("end_lat", end_lat, -90, 90), ("end_lon", end_lon, -180, 180),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name} must be a finite coordinate between {low} and {high}")

    direct = get_road_route(start_lat, start_lon, end_lat, end_lon)
    to_station = get_road_route(start_lat, start_lon, station_lat, station_lon)
    from_station = get_road_route(station_lat, station_lon, end_lat, end_lon)

    via_distance = to_station["distance_miles"] + from_station["distance_miles"]
    via_minutes = to_station["estimated_driving_minutes"] + from_station["estimated_driving_minutes"]
    extra_miles = via_distance - direct["distance_miles"]
    extra_minutes = via_minutes - direct["estimated_driving_minutes"]

    return {
        "direct_distance_miles": direct["distance_miles"],
        "direct_driving_minutes": direct["estimated_driving_minutes"],
        "via_station_distance_miles": via_distance,
        "via_station_driving_minutes": via_minutes,
        "additional_driving_miles": extra_miles,
        "additional_driving_minutes": extra_minutes,
        "start_to_station_distance_miles": to_station["distance_miles"],
        "station_to_end_distance_miles": from_station["distance_miles"],
        "disclaimer": "Three separate driving routes; negative differences can occur if independently calculated routes differ. Excludes charging, queue time, compatibility, availability, and traffic changes.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compare road detour through one chosen station")
    for name in ("start_lat", "start_lon", "station_lat", "station_lon", "end_lat", "end_lon"):
        parser.add_argument(name, type=float)
    args = parser.parse_args(argv)
    try:
        result = compare_station_detour(
            args.start_lat, args.start_lon, args.station_lat, args.station_lon,
            args.end_lat, args.end_lon,
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Detour lookup error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@
    'tests/test_station_detour.py' = @'
import json

import pytest

import src.planning.station_detour as module
from src.planning.station_detour import compare_station_detour, main


@pytest.fixture
def fake_routes(monkeypatch):
    calls = []
    routes = [(10, 20), (6, 12), (7, 14)]

    def fake_route(*coords):
        calls.append(coords)
        miles, minutes = routes[len(calls) - 1]
        return {"distance_miles": miles, "estimated_driving_minutes": minutes}

    monkeypatch.setattr(module, "get_road_route", fake_route)
    return calls


def test_compares_driving_detour(fake_routes):
    result = compare_station_detour(39.7, -105.0, 39.75, -104.95, 39.8, -104.9)
    assert result["direct_distance_miles"] == 10
    assert result["via_station_distance_miles"] == 13
    assert result["additional_driving_miles"] == 3
    assert result["additional_driving_minutes"] == 6
    assert result["start_to_station_distance_miles"] == 6
    assert len(fake_routes) == 3
    assert fake_routes[1] == (39.7, -105.0, 39.75, -104.95)


def test_command_prints_json(fake_routes, capsys):
    assert main(["39.7", "-105", "39.75", "-104.95", "39.8", "-104.9"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["additional_driving_miles"] == 3


@pytest.mark.parametrize("bad", [91, float("nan"), True])
def test_rejects_invalid_coordinates_before_network(bad):
    with pytest.raises(ValueError, match="start_lat"):
        compare_station_detour(bad, -105, 39.75, -104.95, 39.8, -104.9)


def test_routing_error_is_not_silently_ignored(monkeypatch):
    def failing_route(*coords):
        raise RuntimeError("Road routing failed")

    monkeypatch.setattr(module, "get_road_route", failing_route)
    with pytest.raises(RuntimeError, match="Road routing failed"):
        compare_station_detour(39.7, -105, 39.75, -104.95, 39.8, -104.9)
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
Write-Host 'Offline tests passed. Live detour comparison requires ORS_API_KEY and makes three routing calls.'