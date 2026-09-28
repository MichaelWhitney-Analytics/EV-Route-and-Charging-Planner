from dataclasses import dataclass
from math import isfinite

from src.planning.vehicle_profile import VehicleProfile


@dataclass(frozen=True)
class ChargingStopResult:
    arrival_percent: float
    next_leg_miles: float
    departure_percent: float
    energy_to_add_kwh: float
    charge_needed: bool


def calculate_charging_stop(
    profile: VehicleProfile,
    arrival_percent: float,
    next_leg_miles: float,
) -> ChargingStopResult:
    """Find minimum charge needed for one next leg plus arrival reserve.

    This is an energy estimate, not a charge-time or charger-availability estimate.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")

    for name, value, minimum, maximum in (
        ("arrival_percent", arrival_percent, 0, 100),
        ("next_leg_miles", next_leg_miles, 0, None),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or value < minimum
            or (maximum is not None and value > maximum)
        ):
            bound = "0 to 100" if maximum is not None else "0 or greater"
            raise ValueError(f"{name} must be a finite number from {bound}")

    energy_for_leg = next_leg_miles * profile.energy_per_mile_kwh
    required_departure_kwh = energy_for_leg + profile.reserve_energy_kwh
    battery_kwh = profile.usable_battery_kwh

    if required_departure_kwh > battery_kwh + 1e-9:
        raise ValueError(
            "next leg cannot preserve arrival reserve even from 100% charge"
        )

    arrival_kwh = battery_kwh * arrival_percent / 100
    energy_to_add_kwh = max(0.0, required_departure_kwh - arrival_kwh)
    departure_kwh = arrival_kwh + energy_to_add_kwh

    return ChargingStopResult(
        arrival_percent=arrival_percent,
        next_leg_miles=next_leg_miles,
        departure_percent=min(100.0, departure_kwh / battery_kwh * 100),
        energy_to_add_kwh=energy_to_add_kwh,
        charge_needed=energy_to_add_kwh > 1e-9,
    )