from math import isfinite


VEHICLE_FIELDS = {
    "name",
    "usable_battery_kwh",
    "driving_kwh_per_100_miles",
    "max_dc_charge_kw",
    "connector",
    "minimum_arrival_percent",
}
TRIP_FIELDS = {
    "vehicle",
    "leg_distances_miles",
    "start_percent",
    "effective_stop_powers_kw",
}


def _is_finite_number(value) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
    )


def validate_trip_request(request: dict) -> None:
    """Reject malformed JSON before the planning model is invoked."""
    if not isinstance(request, dict):
        raise ValueError("trip request must be a JSON object")

    missing = TRIP_FIELDS - set(request)
    unknown = set(request) - TRIP_FIELDS
    if missing:
        raise ValueError(f"missing trip fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"unknown trip fields: {sorted(unknown)}")

    vehicle = request["vehicle"]
    if not isinstance(vehicle, dict):
        raise ValueError("vehicle must be a JSON object")

    missing_vehicle = VEHICLE_FIELDS - set(vehicle)
    unknown_vehicle = set(vehicle) - VEHICLE_FIELDS
    if missing_vehicle:
        raise ValueError(
            f"missing vehicle fields: {sorted(missing_vehicle)}"
        )
    if unknown_vehicle:
        raise ValueError(
            f"unknown vehicle fields: {sorted(unknown_vehicle)}"
        )

    if not isinstance(request["leg_distances_miles"], list):
        raise ValueError("leg_distances_miles must be a JSON array")
    if not request["leg_distances_miles"]:
        raise ValueError("leg_distances_miles must not be empty")
    if not isinstance(request["effective_stop_powers_kw"], list):
        raise ValueError("effective_stop_powers_kw must be a JSON array")
    if len(request["effective_stop_powers_kw"]) != len(request["leg_distances_miles"]) - 1:
        raise ValueError(
            "effective_stop_powers_kw must have one value between each pair of legs"
        )

    for value in request["leg_distances_miles"]:
        if not _is_finite_number(value) or value < 0:
            raise ValueError("each leg distance must be a finite number of 0 or greater")
    for value in request["effective_stop_powers_kw"]:
        if not _is_finite_number(value) or value <= 0:
            raise ValueError("each effective stop power must be a positive finite number")

    start = request["start_percent"]
    if not _is_finite_number(start) or not 0 <= start <= 100:
        raise ValueError("start_percent must be a finite number from 0 to 100")

    if not isinstance(vehicle["name"], str) or not vehicle["name"].strip():
        raise ValueError("vehicle name must be a nonempty string")
    if not isinstance(vehicle["connector"], str) or not vehicle["connector"].strip():
        raise ValueError("vehicle connector must be a nonempty string")

    for field in (
        "usable_battery_kwh",
        "driving_kwh_per_100_miles",
        "max_dc_charge_kw",
    ):
        if not _is_finite_number(vehicle[field]) or vehicle[field] <= 0:
            raise ValueError(f"vehicle {field} must be a positive finite number")

    reserve = vehicle["minimum_arrival_percent"]
    if not _is_finite_number(reserve) or not 0 <= reserve < 100:
        raise ValueError(
            "vehicle minimum_arrival_percent must be from 0 up to 100"
        )