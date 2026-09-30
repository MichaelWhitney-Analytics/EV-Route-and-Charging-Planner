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


def build_ordered_itinerary(profile: VehicleProfile, start_percent: float, origin_name: str, legs: list[dict],
                            *, destination_profile: VehicleProfile | None = None) -> dict:
    """Estimate arrival and minimal next-leg charge at ordered supplied sites.

    Each leg has name, distance_miles (measured road distance), and kind
    ('site' or 'destination'). The last and only destination must be last.
    No site is automatically selected and no charging time is estimated.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    if destination_profile is None:
        destination_profile = profile
    if not isinstance(destination_profile, VehicleProfile):
        raise TypeError("destination_profile must be a VehicleProfile")
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
        leg_profile = destination_profile if leg["kind"] == "destination" else profile
        estimate = estimate_route_energy(leg_profile, leg["distance_miles"], current)
        if not estimate.reachable_without_charging:
            raise ValueError(
                f"leg {index + 1} cannot preserve the configured arrival reserve "
                f"(shortfall {estimate.shortfall_kwh:.6f} kWh; "
                f"road distance {leg['distance_miles']:.2f} mi)"
            )
        arrival = estimate.estimated_arrival_percent
        item = {
            "kind": leg["kind"], "name": leg["name"],
            "road_leg_miles": leg["distance_miles"],
            "arrival_percent": arrival,
        }
        if leg["kind"] == "site":
            next_distance = checked[index + 1]["distance_miles"]
            try:
                next_profile = (
                    destination_profile
                    if checked[index + 1]["kind"] == "destination"
                    else profile
                )
                charge = calculate_charging_stop(next_profile, arrival, next_distance)
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
        "arrival_reserve_percent": destination_profile.minimum_arrival_percent,
        "charging_stop_arrival_minimum_percent": profile.minimum_arrival_percent,
        "total_road_miles": sum(leg["distance_miles"] for leg in checked),
        "timeline": timeline,
        "disclaimer": "Ordered sites and road-leg distances are supplied inputs, not automatically chosen stops. Energy depends on the provided vehicle profile. Site access, connector compatibility in practice, availability, charge time, and actual trip feasibility remain unverified.",
    }