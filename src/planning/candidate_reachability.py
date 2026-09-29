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