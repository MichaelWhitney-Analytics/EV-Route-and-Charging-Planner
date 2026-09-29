$ErrorActionPreference = 'Stop'
foreach ($path in @('src/planning/route_energy.py', 'src/planning/charging_stop.py', 'src/planning/vehicle_profile.py', '.venv/Scripts/python.exe')) {
    if (-not (Test-Path $path)) { throw "Missing $path. Run from project root after the energy-planning milestones." }
}
$files = @{
    'src/planning/ordered_itinerary.py' = @'
"""Energy continuity for an explicitly supplied order of road legs.

This is not a charging-stop finder, vehicle database, or route service.
"""

from math import isfinite

from src.planning.charging_stop import calculate_charging_stop
from src.planning.route_energy import estimate_route_energy
from src.planning.vehicle_profile import VehicleProfile


def _percent(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 100:
        raise ValueError(f"{label} must be a finite percentage from 0 to 100")
    return float(value)


def build_ordered_itinerary(profile: VehicleProfile, start_percent: float, origin_name: str, legs: list[dict]) -> dict:
    """Estimate arrival and minimal next-leg charge at ordered supplied sites.

    Each leg has name, distance_miles (measured road distance), and kind
    ('site' or 'destination'). The last and only destination must be last.
    No site is automatically selected and no charging time is estimated.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    current = _percent(start_percent, "start_percent")
    if not isinstance(origin_name, str) or not origin_name.strip():
        raise ValueError("origin_name must be nonempty")
    if not isinstance(legs, list) or not 1 <= len(legs) <= 12:
        raise ValueError("legs must contain 1 to 12 ordered road legs")
    checked = []
    for index, leg in enumerate(legs):
        if not isinstance(leg, dict) or not isinstance(leg.get("name"), str) or not leg["name"].strip():
            raise ValueError(f"leg {index + 1} needs a nonempty name")
        distance = leg.get("distance_miles")
        if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not isfinite(distance) or distance < 0:
            raise ValueError(f"leg {index + 1} needs a finite nonnegative road distance")
        expected = "destination" if index == len(legs) - 1 else "site"
        if leg.get("kind") != expected:
            raise ValueError(f"leg {index + 1} kind must be {expected}")
        checked.append({"name": leg["name"].strip(), "kind": expected, "distance_miles": float(distance)})

    timeline = [{"kind": "origin", "name": origin_name.strip(), "departure_percent": current}]
    for index, leg in enumerate(checked):
        estimate = estimate_route_energy(profile, leg["distance_miles"], current)
        if not estimate.reachable_without_charging:
            raise ValueError(f"leg {index + 1} cannot preserve the configured arrival reserve")
        arrival = estimate.estimated_arrival_percent
        item = {
            "kind": leg["kind"], "name": leg["name"],
            "road_leg_miles": leg["distance_miles"],
            "arrival_percent": arrival,
        }
        if leg["kind"] == "site":
            next_distance = checked[index + 1]["distance_miles"]
            try:
                charge = calculate_charging_stop(profile, arrival, next_distance)
            except ValueError as exc:
                if "cannot preserve arrival reserve" not in str(exc):
                    raise
                raise ValueError(f"leg {index + 2} exceeds a full battery with the configured arrival reserve") from exc
            item.update({
                "energy_to_add_kwh": charge.energy_to_add_kwh,
                "departure_percent": charge.departure_percent,
                "charge_needed_for_next_leg": charge.charge_needed,
                "site_usable": "unverified",
            })
            current = charge.departure_percent
        timeline.append(item)
    return {
        "vehicle_name": profile.name,
        "start_percent": float(start_percent),
        "arrival_reserve_percent": profile.minimum_arrival_percent,
        "total_road_miles": sum(leg["distance_miles"] for leg in checked),
        "timeline": timeline,
        "disclaimer": "Ordered sites and road-leg distances are supplied inputs, not automatically chosen stops. Energy depends on the provided vehicle profile. Site access, connector compatibility in practice, availability, charge time, and actual trip feasibility remain unverified.",
    }
'@
    'tests/test_ordered_itinerary.py' = @'
import pytest

from src.planning.ordered_itinerary import build_ordered_itinerary
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def vehicle():
    return VehicleProfile("Illustrative EV", 75, 30, 150, "CCS", 10)


def test_direct_trip_has_no_phantom_charging_stop(vehicle):
    result = build_ordered_itinerary(vehicle, 80, "Origin", [
        {"name": "Destination", "kind": "destination", "distance_miles": 100}
    ])
    assert [step["kind"] for step in result["timeline"]] == ["origin", "destination"]
    assert result["timeline"][1]["arrival_percent"] == pytest.approx(40)
    assert result["total_road_miles"] == 100
    assert result["arrival_reserve_percent"] == 10


def test_one_ordered_site_carries_battery_to_destination(vehicle):
    result = build_ordered_itinerary(vehicle, 80, "Origin", [
        {"name": "Supplied site", "kind": "site", "distance_miles": 100},
        {"name": "Destination", "kind": "destination", "distance_miles": 100},
    ])
    site, destination = result["timeline"][1:]
    assert site["arrival_percent"] == pytest.approx(40)
    assert site["departure_percent"] == pytest.approx(50)
    assert site["energy_to_add_kwh"] == pytest.approx(7.5)
    assert site["charge_needed_for_next_leg"] is True
    assert site["site_usable"] == "unverified"
    assert destination["arrival_percent"] == pytest.approx(10)


def test_multiple_sites_carry_forward_percentages(vehicle):
    result = build_ordered_itinerary(vehicle, 80, "Origin", [
        {"name": "A", "kind": "site", "distance_miles": 100},
        {"name": "B", "kind": "site", "distance_miles": 100},
        {"name": "End", "kind": "destination", "distance_miles": 100},
    ])
    assert [step["arrival_percent"] for step in result["timeline"][1:]] == pytest.approx([40, 10, 10])
    assert result["timeline"][2]["departure_percent"] == pytest.approx(50)


def test_optional_site_is_not_called_charging_stop(vehicle):
    result = build_ordered_itinerary(vehicle, 80, "Origin", [
        {"name": "Optional", "kind": "site", "distance_miles": 20},
        {"name": "End", "kind": "destination", "distance_miles": 20},
    ])
    assert result["timeline"][1]["charge_needed_for_next_leg"] is False
    assert result["timeline"][1]["energy_to_add_kwh"] == 0


def test_unreachable_first_leg_fails(vehicle):
    with pytest.raises(ValueError, match="leg 1 cannot preserve"):
        build_ordered_itinerary(vehicle, 80, "Origin", [
            {"name": "End", "kind": "destination", "distance_miles": 200}
        ])


def test_next_leg_exceeds_full_battery(vehicle):
    with pytest.raises(ValueError, match="leg 2 exceeds a full battery"):
        build_ordered_itinerary(vehicle, 80, "Origin", [
            {"name": "Site", "kind": "site", "distance_miles": 50},
            {"name": "End", "kind": "destination", "distance_miles": 226},
        ])


@pytest.mark.parametrize("bad", [float("nan"), -1, True, "10"])
def test_invalid_road_leg_distance(vehicle, bad):
    with pytest.raises(ValueError, match="finite nonnegative"):
        build_ordered_itinerary(vehicle, 80, "Origin", [
            {"name": "End", "kind": "destination", "distance_miles": bad}
        ])


def test_rejects_wrong_order(vehicle):
    with pytest.raises(ValueError, match="kind must be site"):
        build_ordered_itinerary(vehicle, 80, "Origin", [
            {"name": "Early destination", "kind": "destination", "distance_miles": 20},
            {"name": "End", "kind": "destination", "distance_miles": 20},
        ])
'@
}
foreach ($path in $files.Keys) { if (Test-Path $path) { throw "Refusing to overwrite $path" } }
$utf8 = [System.Text.UTF8Encoding]::new($false)
foreach ($path in $files.Keys) {
    New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $path), $files[$path], $utf8)
    Write-Host "Created $path"
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. This module does not select stops or verify chargers.'