$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'src/planning/candidate_assessment.py') -or -not (Test-Path 'src/planning/route_energy.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the EV-Route-and-Charging-Planner project root with its existing .venv.'
}
$files = @{
    'src/planning/candidate_reachability.py' = @'
"""Screen already-assessed station detours with a real custom vehicle profile."""

from dataclasses import asdict
from math import isfinite

from src.planning.charging_stop import calculate_charging_stop
from src.planning.route_energy import estimate_route_energy
from src.planning.vehicle_profile import VehicleProfile


def assess_candidate_reachability(profile: VehicleProfile, start_percent: float, assessment: dict) -> dict:
    """Evaluate driving energy to each candidate and charge needed for its next leg.

    Uses supplied vehicle assumptions and previously measured road legs; does
    not make network calls or assert that a candidate charger can be used.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    if isinstance(start_percent, bool) or not isinstance(start_percent, (int, float)) or not isfinite(start_percent) or not 0 <= start_percent <= 100:
        raise ValueError("start_percent must be a finite number from 0 to 100")
    if not isinstance(assessment, dict) or not isinstance(assessment.get("assessments"), list):
        raise ValueError("assessment must contain an assessments list")

    results = []
    for item in assessment["assessments"]:
        if not isinstance(item, dict) or not isinstance(item.get("station"), dict) or not isinstance(item.get("detour"), dict):
            raise ValueError("each assessed item needs a station and detour")
        detour = item["detour"]
        first = detour.get("start_to_station_distance_miles")
        second = detour.get("station_to_end_distance_miles")
        for label, value in (("start_to_station_distance_miles", first), ("station_to_end_distance_miles", second)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                raise ValueError(f"{label} must be a finite nonnegative road distance")

        arrival = estimate_route_energy(profile, first, start_percent)
        outcome = {
            "station": item["station"],
            "station_reachable_with_reserve": arrival.reachable_without_charging,
            "arrival_estimate": asdict(arrival),
            "charge_for_next_leg": None,
            "next_leg_possible_from_full": None,
        }
        if arrival.reachable_without_charging:
            try:
                charge = calculate_charging_stop(
                    profile, arrival.estimated_arrival_percent, second
                )
            except ValueError as exc:
                if "cannot preserve arrival reserve" not in str(exc):
                    raise
                outcome["next_leg_possible_from_full"] = False
            else:
                outcome["charge_for_next_leg"] = asdict(charge)
                outcome["next_leg_possible_from_full"] = True
        results.append(outcome)

    return {
        "vehicle_name": profile.name,
        "start_percent": start_percent,
        "candidates": results,
        "disclaimer": "Energy estimates depend on user-provided battery and driving-use assumptions. A reachable station is not a verified usable charger. No live availability, adapter rights, charging speed, road conditions, or detour optimization is guaranteed.",
    }
'@
    'tests/test_candidate_reachability.py' = @'
import pytest

from src.planning.candidate_reachability import assess_candidate_reachability
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile():
    return VehicleProfile("Test EV", 75, 30, 150, "CCS", 10)


def assessed(first, second):
    return {"assessments": [{
        "station": {"id": 123, "name": "Example"},
        "detour": {
            "start_to_station_distance_miles": first,
            "station_to_end_distance_miles": second,
        },
    }]}


def test_reachable_station_reports_charge_needed(profile):
    result = assess_candidate_reachability(profile, 80, assessed(100, 100))
    candidate = result["candidates"][0]
    assert candidate["station_reachable_with_reserve"] is True
    assert candidate["arrival_estimate"]["estimated_arrival_percent"] == pytest.approx(40)
    assert candidate["charge_for_next_leg"]["energy_to_add_kwh"] == pytest.approx(7.5)
    assert candidate["next_leg_possible_from_full"] is True


def test_unreachable_station_does_not_assume_a_charge(profile):
    result = assess_candidate_reachability(profile, 80, assessed(200, 10))
    candidate = result["candidates"][0]
    assert candidate["station_reachable_with_reserve"] is False
    assert candidate["charge_for_next_leg"] is None
    assert candidate["next_leg_possible_from_full"] is None


def test_leg_too_long_even_with_full_battery(profile):
    result = assess_candidate_reachability(profile, 80, assessed(50, 226))
    candidate = result["candidates"][0]
    assert candidate["station_reachable_with_reserve"] is True
    assert candidate["next_leg_possible_from_full"] is False
    assert candidate["charge_for_next_leg"] is None


def test_empty_assessment_is_valid(profile):
    result = assess_candidate_reachability(profile, 80, {"assessments": []})
    assert result["candidates"] == []


@pytest.mark.parametrize("value", [-1, 101, True, float("nan")])
def test_rejects_invalid_start_percent(profile, value):
    with pytest.raises(ValueError, match="start_percent"):
        assess_candidate_reachability(profile, value, assessed(100, 100))


def test_rejects_bad_distance(profile):
    with pytest.raises(ValueError, match="start_to_station_distance_miles"):
        assess_candidate_reachability(profile, 80, assessed(-1, 100))
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
Write-Host 'Offline reachability tests passed. No live calls or vehicle specifications were invented.'