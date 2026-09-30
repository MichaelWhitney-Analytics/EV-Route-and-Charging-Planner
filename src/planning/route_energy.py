from dataclasses import dataclass
from math import isfinite

from src.planning.vehicle_profile import VehicleProfile


@dataclass(frozen=True)
class RouteEnergyResult:
    distance_miles: float
    start_percent: float
    energy_needed_kwh: float
    energy_available_above_reserve_kwh: float
    estimated_arrival_percent: float
    shortfall_kwh: float
    reachable_without_charging: bool


def estimate_route_energy(
    profile: VehicleProfile,
    distance_miles: float,
    start_percent: float,
) -> RouteEnergyResult:
    """Estimate whether one route leg preserves the arrival reserve.

    Uses the profile's user-provided driving-energy assumption.
    Does not account for speed, weather, terrain, or battery changes.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")

    if (
        isinstance(distance_miles, bool)
        or not isinstance(distance_miles, (int, float))
        or not isfinite(distance_miles)
        or distance_miles < 0
    ):
        raise ValueError(
            "distance_miles must be a finite, nonnegative number"
        )

    if (
        isinstance(start_percent, bool)
        or not isinstance(start_percent, (int, float))
        or not isfinite(start_percent)
        or not 0 <= start_percent <= 100
    ):
        raise ValueError(
            "start_percent must be a finite number from 0 to 100"
        )

    start_energy_kwh = (
        profile.usable_battery_kwh * start_percent / 100
    )
    energy_needed_kwh = (
        distance_miles * profile.energy_per_mile_kwh
    )
    energy_available_above_reserve_kwh = max(
        0.0,
        start_energy_kwh - profile.reserve_energy_kwh,
    )
    estimated_arrival_percent = (
        (start_energy_kwh - energy_needed_kwh)
        / profile.usable_battery_kwh
        * 100
    )
    shortfall_kwh = max(
        0.0,
        energy_needed_kwh
        + profile.reserve_energy_kwh
        - start_energy_kwh,
    )

    return RouteEnergyResult(
        distance_miles=distance_miles,
        start_percent=start_percent,
        energy_needed_kwh=energy_needed_kwh,
        energy_available_above_reserve_kwh=(
            energy_available_above_reserve_kwh
        ),
        estimated_arrival_percent=estimated_arrival_percent,
        shortfall_kwh=shortfall_kwh,
        reachable_without_charging=(
            start_energy_kwh + 1e-9
            >= energy_needed_kwh + profile.reserve_energy_kwh
        ),
    )