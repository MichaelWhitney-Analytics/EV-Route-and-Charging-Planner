$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'src/planning/connector_screening.py') -or -not (Test-Path 'src/planning/station_detour.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the EV-Route-and-Charging-Planner project root with its existing .venv.'
}
$files = @{
    'src/planning/candidate_assessment.py' = @'
"""Limited exploratory assessment of reported connector matches and detours."""

import argparse
import json
from math import isfinite

from src.ingestion.route_station_candidates import find_route_station_candidates
from src.planning.connector_screening import screen_station_connectors
from src.planning.station_detour import compare_station_detour
from src.planning.vehicle_profile import VehicleProfile


MAX_DETOUR_CHECKS = 3


def assess_candidates(
    profile: VehicleProfile,
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    *,
    max_detour_checks: int = 2,
) -> dict:
    """Discover stations, screen listed plugs, and measure limited detours.

    Order follows lookup response, not proximity, quality, or optimality.
    One road-route call discovers the route, three station searches sample it,
    then each checked candidate makes three additional road-route calls.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    if (
        isinstance(max_detour_checks, bool)
        or not isinstance(max_detour_checks, int)
        or not 1 <= max_detour_checks <= MAX_DETOUR_CHECKS
    ):
        raise ValueError("max_detour_checks must be an integer from 1 to 3")
    for name, value, low, high in (
        ("start_lat", start_lat, -90, 90), ("start_lon", start_lon, -180, 180),
        ("end_lat", end_lat, -90, 90), ("end_lon", end_lon, -180, 180),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name} must be a finite coordinate between {low} and {high}")

    discovery = find_route_station_candidates(start_lat, start_lon, end_lat, end_lon)
    screening = screen_station_connectors(profile, discovery["candidate_stations"])
    assessments = []
    skipped_without_coordinates = 0
    for station in screening["possible_matches"]:
        if len(assessments) >= max_detour_checks:
            break
        lat = station.get("latitude")
        lon = station.get("longitude")
        if (
            isinstance(lat, bool) or isinstance(lon, bool)
            or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
            or not isfinite(lat) or not isfinite(lon)
            or not -90 <= lat <= 90 or not -180 <= lon <= 180
        ):
            skipped_without_coordinates += 1
            continue
        detour = compare_station_detour(start_lat, start_lon, lat, lon, end_lat, end_lon)
        assessments.append({"station": station, "detour": detour})

    return {
        "vehicle_connector": profile.connector,
        "route_distance_miles": discovery["route_distance_miles"],
        "discovered_count": len(discovery["candidate_stations"]),
        "reported_connector_match_count": len(screening["possible_matches"]),
        "skipped_without_coordinates": skipped_without_coordinates,
        "assessments": assessments,
        "disclaimer": "Only the first listed connector matches are assessed, up to the cap. Not ranked or optimized. Connector labels, route detours, charger access, working status, and vehicle range need further verification.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assess a few route charger candidates")
    for name in ("start_lat", "start_lon", "end_lat", "end_lon"):
        parser.add_argument(name, type=float)
    parser.add_argument("--connector", required=True, help="CCS, NACS, or CHADEMO")
    parser.add_argument("--max-checks", type=int, default=2, choices=(1, 2, 3))
    args = parser.parse_args(argv)
    try:
        # This profile is used solely to pass the declared connector through
        # the existing vehicle-profile interface. Example values are not real specs.
        profile = VehicleProfile("Connector check only", 1.0, 1.0, 1.0, args.connector)
        result = assess_candidates(
            profile, args.start_lat, args.start_lon, args.end_lat, args.end_lon,
            max_detour_checks=args.max_checks,
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Assessment error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@
    'tests/test_candidate_assessment.py' = @'
import pytest

import src.planning.candidate_assessment as module
from src.planning.candidate_assessment import assess_candidates
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile():
    return VehicleProfile("Test", 75, 30, 150, "CCS")


def test_caps_detour_calls_and_screens_labels(monkeypatch, profile):
    stations = [
        {"id": 1, "latitude": 39.71, "longitude": -105.01, "connector_types_reported": ["J1772COMBO"]},
        {"id": 2, "latitude": 39.72, "longitude": -105.02, "connector_types_reported": ["TESLA"]},
        {"id": 3, "latitude": 39.73, "longitude": -105.03, "connector_types_reported": ["J1772COMBO"]},
        {"id": 4, "latitude": 39.74, "longitude": -105.04, "connector_types_reported": ["J1772COMBO"]},
    ]
    monkeypatch.setattr(module, "find_route_station_candidates", lambda *a: {
        "route_distance_miles": 20, "candidate_stations": stations,
    })
    calls = []

    def fake_detour(*coords):
        calls.append(coords)
        return {"additional_driving_miles": 2}

    monkeypatch.setattr(module, "compare_station_detour", fake_detour)
    result = assess_candidates(profile, 39.7, -105, 39.8, -104.9)
    assert result["discovered_count"] == 4
    assert result["reported_connector_match_count"] == 3
    assert [a["station"]["id"] for a in result["assessments"]] == [1, 3]
    assert len(calls) == 2
    assert "Not ranked" in result["disclaimer"]


def test_empty_candidates_make_no_detour_requests(monkeypatch, profile):
    monkeypatch.setattr(module, "find_route_station_candidates", lambda *a: {
        "route_distance_miles": 10, "candidate_stations": [],
    })
    result = assess_candidates(profile, 39.7, -105, 39.8, -104.9)
    assert result["assessments"] == []


@pytest.mark.parametrize("cap", [0, 4, True, 1.5])
def test_rejects_invalid_cap_before_network(profile, cap):
    with pytest.raises(ValueError, match="max_detour_checks"):
        assess_candidates(profile, 39.7, -105, 39.8, -104.9, max_detour_checks=cap)


def test_rejects_invalid_coordinates_before_network(profile):
    with pytest.raises(ValueError, match="start_lat"):
        assess_candidates(profile, 91, -105, 39.8, -104.9)
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
Write-Host 'Tests passed. Live assessment requires ORS_API_KEY and NLR_API_KEY.'