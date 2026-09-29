$ErrorActionPreference = 'Stop'
foreach ($required in @('src/planning/candidate_assessment.py', 'src/planning/candidate_reachability.py', '.venv/Scripts/python.exe')) {
    if (-not (Test-Path $required)) { throw "Missing $required. Run this from the project root after the reachability step." }
}
$files = @{
    'src/planning/planning_summary.py' = @'
"""Compose limited live candidate assessment with offline energy screening."""

import argparse
import json

from src.planning.candidate_assessment import assess_candidates
from src.planning.candidate_reachability import assess_candidate_reachability
from src.planning.vehicle_profile import VehicleProfile


def plan_candidate_summary(
    profile: VehicleProfile,
    start_percent: float,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    *,
    max_detour_checks: int = 2,
) -> dict:
    """Make one limited discovery/road assessment, then screen its energy.

    This is not a trip recommendation or a full-route multi-stop planner.
    """
    assessment = assess_candidates(
        profile, start_lat, start_lon, end_lat, end_lon,
        max_detour_checks=max_detour_checks,
    )
    energy = assess_candidate_reachability(profile, start_percent, assessment)
    categories = {
        "energy_feasible_if_charging_available": [],
        "unreachable_with_reserve": [],
        "next_leg_exceeds_full_battery_with_reserve": [],
    }
    for candidate in energy["candidates"]:
        if not candidate["station_reachable_with_reserve"]:
            categories["unreachable_with_reserve"].append(candidate)
        elif candidate["next_leg_possible_from_full"] is False:
            categories["next_leg_exceeds_full_battery_with_reserve"].append(candidate)
        else:
            categories["energy_feasible_if_charging_available"].append(candidate)
    unassessed_count = max(
        0, assessment["distinct_reported_address_count"] - len(assessment["assessments"])
    )
    return {
        "vehicle_name": profile.name,
        "start_percent": start_percent,
        "route_distance_miles": assessment["route_distance_miles"],
        "discovered_record_count": assessment["discovered_count"],
        "reported_connector_match_record_count": assessment["reported_connector_match_count"],
        "distinct_reported_address_count": assessment["distinct_reported_address_count"],
        "road_detours_assessed_count": len(assessment["assessments"]),
        "not_assessed_count": unassessed_count,
        "not_assessed_note": "Includes sites beyond the detour-check cap and any skipped for missing coordinates. These sites have not been energy-screened.",
        "categories": categories,
        "disclaimer": "Exploratory estimates only. Battery and consumption are user-supplied. Reported connector matches, site access, charger availability, charging speed, road conditions, and trip completion are unverified. No candidate is recommended or guaranteed.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Limited EV candidate energy summary (live API calls)")
    for name in ("start_lat", "start_lon", "end_lat", "end_lon"):
        parser.add_argument(name, type=float)
    parser.add_argument("--name", required=True)
    parser.add_argument("--battery-kwh", type=float, required=True)
    parser.add_argument("--kwh-per-100-miles", type=float, required=True)
    parser.add_argument("--max-charge-kw", type=float, required=True)
    parser.add_argument("--connector", required=True)
    parser.add_argument("--reserve-percent", type=float, default=10)
    parser.add_argument("--start-percent", type=float, required=True)
    parser.add_argument("--max-checks", type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args(argv)
    try:
        profile = VehicleProfile(
            args.name, args.battery_kwh, args.kwh_per_100_miles,
            args.max_charge_kw, args.connector, args.reserve_percent,
        )
        result = plan_candidate_summary(
            profile, args.start_percent, args.start_lat, args.start_lon,
            args.end_lat, args.end_lon, max_detour_checks=args.max_checks,
        )
    except (ValueError, RuntimeError, TypeError) as exc:
        parser.exit(2, f"Planning summary error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@
    'tests/test_planning_summary.py' = @'
import pytest

import src.planning.planning_summary as module
from src.planning.vehicle_profile import VehicleProfile


def test_summary_categories_and_unassessed_count(monkeypatch):
    profile = VehicleProfile("Example", 75, 30, 150, "CCS", 10)
    calls = []

    def assessment(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "route_distance_miles": 40,
            "discovered_count": 8,
            "reported_connector_match_count": 5,
            "distinct_reported_address_count": 4,
            "assessments": [{"station": {"id": i}, "detour": {}} for i in (1, 2, 3)],
        }

    def energy(*args):
        assert args[0] is profile and args[1] == 80
        return {"candidates": [
            {"station": {"id": 1}, "station_reachable_with_reserve": True, "next_leg_possible_from_full": True},
            {"station": {"id": 2}, "station_reachable_with_reserve": False, "next_leg_possible_from_full": None},
            {"station": {"id": 3}, "station_reachable_with_reserve": True, "next_leg_possible_from_full": False},
        ]}

    monkeypatch.setattr(module, "assess_candidates", assessment)
    monkeypatch.setattr(module, "assess_candidate_reachability", energy)
    result = module.plan_candidate_summary(profile, 80, 39.7, -105, 39.8, -104.9, max_detour_checks=3)
    assert len(calls) == 1
    assert calls[0][1] == {"max_detour_checks": 3}
    assert result["not_assessed_count"] == 1
    assert result["road_detours_assessed_count"] == 3
    assert result["categories"]["energy_feasible_if_charging_available"][0]["station"]["id"] == 1
    assert result["categories"]["unreachable_with_reserve"][0]["station"]["id"] == 2
    assert result["categories"]["next_leg_exceeds_full_battery_with_reserve"][0]["station"]["id"] == 3


def test_empty_candidates(monkeypatch):
    monkeypatch.setattr(module, "assess_candidates", lambda *a, **k: {
        "route_distance_miles": 10, "discovered_count": 0,
        "reported_connector_match_count": 0,
        "distinct_reported_address_count": 0, "assessments": [],
    })
    monkeypatch.setattr(module, "assess_candidate_reachability", lambda *a: {"candidates": []})
    result = module.plan_candidate_summary(
        VehicleProfile("Example", 75, 30, 150, "CCS"), 80, 39.7, -105, 39.8, -104.9
    )
    assert result["not_assessed_count"] == 0
    assert all(not entries for entries in result["categories"].values())
'@
}
foreach ($path in $files.Keys) {
    if (Test-Path $path) { throw "Refusing to overwrite existing file: $path" }
}
foreach ($path in $files.Keys) {
    New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $path), $files[$path], [System.Text.UTF8Encoding]::new($false))
    Write-Host "Created $path"
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. The CLI makes live requests only when you invoke it separately.'