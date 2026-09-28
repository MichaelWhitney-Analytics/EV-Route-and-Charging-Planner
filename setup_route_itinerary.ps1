$ErrorActionPreference = 'Stop'

if (-not (Test-Path 'src/planning/charging_time.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run this script from the EV-Route-and-Charging-Planner project root with the existing .venv.'
}

$files = @{
    'src/planning/route_itinerary.py' = @'
from dataclasses import dataclass
from math import isfinite

from src.planning.charging_stop import ChargingStopResult, calculate_charging_stop
from src.planning.charging_time import ChargingTimeEstimate, estimate_charging_time
from src.planning.route_energy import RouteEnergyResult, estimate_route_energy
from src.planning.vehicle_profile import VehicleProfile


@dataclass(frozen=True)
class ItineraryStop:
    after_leg_number: int
    charge: ChargingStopResult
    time: ChargingTimeEstimate


@dataclass(frozen=True)
class ItineraryResult:
    legs: tuple[RouteEnergyResult, ...]
    stops: tuple[ItineraryStop, ...]
    total_distance_miles: float
    total_charge_kwh: float
    total_estimated_charging_minutes: float
    final_percent: float


def build_itinerary(
    profile: VehicleProfile,
    leg_distances_miles: tuple[float, ...],
    start_percent: float,
    effective_stop_powers_kw: tuple[float, ...],
) -> ItineraryResult:
    """Simulate ordered legs with a stop between every consecutive pair.

    Legs and stop powers are caller-supplied; this does not discover roads or
    chargers. A stop with no charge needed has zero estimated charging minutes.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    if not isinstance(leg_distances_miles, tuple) or not leg_distances_miles:
        raise ValueError("leg_distances_miles must be a nonempty tuple")
    if not isinstance(effective_stop_powers_kw, tuple) or len(effective_stop_powers_kw) != len(leg_distances_miles) - 1:
        raise ValueError("provide one effective stop power between each pair of legs")
    if (
        isinstance(start_percent, bool)
        or not isinstance(start_percent, (int, float))
        or not isfinite(start_percent)
        or not 0 <= start_percent <= 100
    ):
        raise ValueError("start_percent must be a finite number from 0 to 100")

    legs = []
    stops = []
    current_percent = start_percent

    for index, distance in enumerate(leg_distances_miles):
        leg = estimate_route_energy(profile, distance, current_percent)
        if not leg.reachable_without_charging:
            raise ValueError(f"leg {index + 1} is not reachable with the arrival reserve")
        legs.append(leg)
        current_percent = leg.estimated_arrival_percent

        if index < len(leg_distances_miles) - 1:
            charge = calculate_charging_stop(
                profile,
                arrival_percent=current_percent,
                next_leg_miles=leg_distances_miles[index + 1],
            )
            time = estimate_charging_time(
                profile, charge, effective_stop_powers_kw[index]
            )
            stops.append(ItineraryStop(index + 1, charge, time))
            current_percent = charge.departure_percent

    return ItineraryResult(
        legs=tuple(legs),
        stops=tuple(stops),
        total_distance_miles=sum(leg_distances_miles),
        total_charge_kwh=sum(stop.charge.energy_to_add_kwh for stop in stops),
        total_estimated_charging_minutes=sum(stop.time.estimated_minutes for stop in stops),
        final_percent=legs[-1].estimated_arrival_percent,
    )
'@
    'tests/test_route_itinerary.py' = @'
import pytest

from src.planning.route_itinerary import build_itinerary
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile():
    return VehicleProfile(
        name="Test EV", usable_battery_kwh=75.0,
        driving_kwh_per_100_miles=30.0, max_dc_charge_kw=150.0,
        connector="CCS", minimum_arrival_percent=10.0,
    )


def test_single_leg_needs_no_stop(profile):
    result = build_itinerary(profile, (100,), 80, ())
    assert len(result.legs) == 1
    assert result.stops == ()
    assert result.final_percent == pytest.approx(40)
    assert result.total_charge_kwh == 0


def test_two_legs_carry_charge_forward(profile):
    result = build_itinerary(profile, (100, 100), 80, (75,))
    assert len(result.legs) == 2
    assert result.legs[0].estimated_arrival_percent == pytest.approx(40)
    assert result.stops[0].charge.departure_percent == pytest.approx(50)
    assert result.stops[0].charge.energy_to_add_kwh == pytest.approx(7.5)
    assert result.total_estimated_charging_minutes == pytest.approx(6)
    assert result.final_percent == pytest.approx(10)
    assert result.total_distance_miles == 200


def test_three_legs_carry_state_across_two_stops(profile):
    result = build_itinerary(profile, (100, 100, 50), 80, (75, 75))
    assert len(result.stops) == 2
    assert result.stops[0].after_leg_number == 1
    assert result.stops[1].after_leg_number == 2
    assert result.total_charge_kwh == pytest.approx(22.5)
    assert result.total_estimated_charging_minutes == pytest.approx(18)
    assert result.final_percent == pytest.approx(10)


def test_stop_with_sufficient_charge_adds_nothing(profile):
    result = build_itinerary(profile, (50, 50), 100, (75,))
    assert result.stops[0].charge.charge_needed is False
    assert result.total_estimated_charging_minutes == 0


def test_rejects_unreachable_first_leg(profile):
    with pytest.raises(ValueError, match="leg 1"):
        build_itinerary(profile, (230,), 100, ())


def test_rejects_unreachable_next_leg_even_from_full(profile):
    with pytest.raises(ValueError, match="next leg cannot preserve"):
        build_itinerary(profile, (50, 226), 100, (75,))


@pytest.mark.parametrize("legs, powers", [((), ()), ((50, 50), ()), ((50,), (75,))])
def test_rejects_invalid_leg_stop_structure(profile, legs, powers):
    with pytest.raises(ValueError):
        build_itinerary(profile, legs, 100, powers)


def test_rejects_invalid_stop_power(profile):
    with pytest.raises(ValueError, match="effective_power_kw"):
        build_itinerary(profile, (50, 50), 100, (151,))


def test_rejects_invalid_start_percent(profile):
    with pytest.raises(ValueError, match="start_percent"):
        build_itinerary(profile, (50,), float("nan"), ())
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
Write-Host 'All tests passed. Review the two new files before committing.'