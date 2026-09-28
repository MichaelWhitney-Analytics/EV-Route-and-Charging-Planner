$ErrorActionPreference = 'Stop'
$target = 'src/planning/candidate_assessment.py'
$testPath = 'tests/test_unique_candidate_sites.py'
if (-not (Test-Path $target) -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the EV-Route-and-Charging-Planner project root after candidate assessment is installed.'
}
if (Test-Path $testPath) { throw "Refusing to overwrite existing file: $testPath" }
$old = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $target))
if (-not $old.Contains('MAX_DETOUR_CHECKS = 3') -or $old.Contains('from src.planning.station_sites import group_station_sites')) {
    throw 'Candidate assessment is not the expected pre-grouping version. No files changed.'
}
$files = @{
    'src/planning/station_sites.py' = @'
"""Group candidate station records that report the same street address."""


def group_station_sites(stations: list[dict]) -> list[dict]:
    """Group by complete address, otherwise keep each station ID separate.

    This does not merge chargers by physical proximity alone or verify access.
    """
    if not isinstance(stations, list):
        raise ValueError("stations must be a list")
    sites = {}
    for station in stations:
        if not isinstance(station, dict):
            raise ValueError("each station must be an object")
        address = station.get("address")
        city = station.get("city")
        state = station.get("state")
        if all(isinstance(item, str) and item.strip() for item in (address, city, state)):
            key = tuple(item.strip().casefold() for item in (address, city, state))
        else:
            key = ("record", len(sites))
        if key not in sites:
            sites[key] = {"representative": station, "station_ids": []}
        sites[key]["station_ids"].append(station.get("id"))
    return list(sites.values())
'@
    'src/planning/candidate_assessment.py' = @'
"""Limited exploratory assessment of reported connector matches and detours."""

import argparse
import json
from math import isfinite

from src.ingestion.route_station_candidates import find_route_station_candidates
from src.planning.connector_screening import screen_station_connectors
from src.planning.station_detour import compare_station_detour
from src.planning.station_sites import group_station_sites
from src.planning.vehicle_profile import VehicleProfile


MAX_DETOUR_CHECKS = 3


def assess_candidates(
    profile: VehicleProfile,
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    *,
    max_detour_checks: int = 2,
) -> dict:
    """Screen station records and check detours at a few distinct addresses.

    Listing order is not a ranking. One discovery route call and three station
    searches are followed by three road-route calls per assessed site.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    if isinstance(max_detour_checks, bool) or not isinstance(max_detour_checks, int) or not 1 <= max_detour_checks <= MAX_DETOUR_CHECKS:
        raise ValueError("max_detour_checks must be an integer from 1 to 3")
    for name, value, low, high in (
        ("start_lat", start_lat, -90, 90), ("start_lon", start_lon, -180, 180),
        ("end_lat", end_lat, -90, 90), ("end_lon", end_lon, -180, 180),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name} must be a finite coordinate between {low} and {high}")

    discovery = find_route_station_candidates(start_lat, start_lon, end_lat, end_lon)
    screening = screen_station_connectors(profile, discovery["candidate_stations"])
    sites = group_station_sites(screening["possible_matches"])
    assessments = []
    skipped_without_coordinates = 0
    for site in sites:
        if len(assessments) >= max_detour_checks:
            break
        station = site["representative"]
        lat, lon = station.get("latitude"), station.get("longitude")
        if (
            isinstance(lat, bool) or isinstance(lon, bool)
            or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
            or not isfinite(lat) or not isfinite(lon)
            or not -90 <= lat <= 90 or not -180 <= lon <= 180
        ):
            skipped_without_coordinates += 1
            continue
        detour = compare_station_detour(start_lat, start_lon, lat, lon, end_lat, end_lon)
        assessments.append({
            "station": station,
            "co_located_station_ids": site["station_ids"],
            "detour": detour,
        })

    return {
        "vehicle_connector": profile.connector,
        "route_distance_miles": discovery["route_distance_miles"],
        "discovered_count": len(discovery["candidate_stations"]),
        "reported_connector_match_count": len(screening["possible_matches"]),
        "distinct_reported_address_count": len(sites),
        "skipped_without_coordinates": skipped_without_coordinates,
        "assessments": assessments,
        "disclaimer": "Only first listed matching addresses are checked; Not ranked or optimized. Same-address records are grouped for detour sampling only. Connector fit, site access, charger availability, and vehicle range remain unverified.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assess a few distinct route charger sites")
    for name in ("start_lat", "start_lon", "end_lat", "end_lon"):
        parser.add_argument(name, type=float)
    parser.add_argument("--connector", required=True, help="CCS, NACS, or CHADEMO")
    parser.add_argument("--max-checks", type=int, default=2, choices=(1, 2, 3))
    args = parser.parse_args(argv)
    try:
        # Placeholder inputs only satisfy the existing VehicleProfile interface;
        # no driving energy or charging estimates use these values here.
        profile = VehicleProfile("Connector check only", 1.0, 1.0, 1.0, args.connector)
        result = assess_candidates(profile, args.start_lat, args.start_lon, args.end_lat, args.end_lon, max_detour_checks=args.max_checks)
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Assessment error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@
    'tests/test_unique_candidate_sites.py' = @'
import pytest

import src.planning.candidate_assessment as module
from src.planning.station_sites import group_station_sites
from src.planning.vehicle_profile import VehicleProfile


def test_groups_same_address_case_insensitively():
    stations = [
        {"id": 1, "address": "350 S Santa Fe Dr", "city": "Denver", "state": "CO"},
        {"id": 2, "address": " 350 s santa fe dr ", "city": "DENVER", "state": "co"},
        {"id": 3, "address": "Elsewhere", "city": "Denver", "state": "CO"},
    ]
    sites = group_station_sites(stations)
    assert len(sites) == 2
    assert sites[0]["station_ids"] == [1, 2]
    assert sites[1]["station_ids"] == [3]


def test_missing_addresses_remain_separate():
    sites = group_station_sites([{"id": 1}, {"id": 2}])
    assert len(sites) == 2


def test_assessment_checks_distinct_sites(monkeypatch):
    stations = [
        {"id": 1, "address": "Same", "city": "Denver", "state": "CO", "latitude": 39.71, "longitude": -105.01, "connector_types_reported": ["J1772COMBO"]},
        {"id": 2, "address": "Same", "city": "Denver", "state": "CO", "latitude": 39.72, "longitude": -105.02, "connector_types_reported": ["J1772COMBO"]},
        {"id": 3, "address": "Different", "city": "Denver", "state": "CO", "latitude": 39.73, "longitude": -105.03, "connector_types_reported": ["J1772COMBO"]},
    ]
    monkeypatch.setattr(module, "find_route_station_candidates", lambda *a: {"route_distance_miles": 20, "candidate_stations": stations})
    calls = []

    def fake_detour(*coords):
        calls.append(coords)
        return {"additional_driving_miles": 1}

    monkeypatch.setattr(module, "compare_station_detour", fake_detour)
    result = module.assess_candidates(VehicleProfile("Test", 75, 30, 150, "CCS"), 39.7, -105, 39.8, -104.9)
    assert result["distinct_reported_address_count"] == 2
    assert len(calls) == 2
    assert result["assessments"][0]["co_located_station_ids"] == [1, 2]
    assert result["assessments"][1]["station"]["id"] == 3


def test_rejects_invalid_collection():
    with pytest.raises(ValueError, match="stations must be a list"):
        group_station_sites(None)
'@
}
foreach ($path in $files.Keys) {
    if ($path -ne $target -and (Test-Path $path)) { throw "Refusing to overwrite existing file: $path" }
}
foreach ($path in $files.Keys) {
    $parent = Split-Path $path -Parent
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $path), $files[$path], [System.Text.UTF8Encoding]::new($false))
    Write-Host "Wrote $path"
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. Live check needs ORS_API_KEY and NLR_API_KEY.'