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