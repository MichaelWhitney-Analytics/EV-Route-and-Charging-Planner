"""Run a supplied EV itinerary: python -m src.planning.trip_cli trip.json"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from src.planning.route_itinerary import build_itinerary
from src.planning.vehicle_profile import VehicleProfile


def run_trip(request: dict) -> dict:
    """Validate JSON structure and return a serializable itinerary estimate."""
    if not isinstance(request, dict):
        raise ValueError("trip request must be a JSON object")
    try:
        vehicle = request["vehicle"]
        legs = request["leg_distances_miles"]
        powers = request["effective_stop_powers_kw"]
        start = request["start_percent"]
    except KeyError as exc:
        raise ValueError(f"missing trip field: {exc.args[0]}") from exc

    if not isinstance(vehicle, dict):
        raise ValueError("vehicle must be a JSON object")
    if not isinstance(legs, list) or not isinstance(powers, list):
        raise ValueError("legs and stop powers must be JSON arrays")

    try:
        profile = VehicleProfile(**vehicle)
    except TypeError as exc:
        raise ValueError(f"invalid vehicle fields: {exc}") from exc

    result = build_itinerary(profile, tuple(legs), start, tuple(powers))
    return {
        "vehicle_name": profile.name,
        "estimate_only": True,
        "limitations": (
            "Caller-supplied leg distances and average charging power; "
            "does not verify roads, charger availability, weather, "
            "charging curve, driving time, or queue time."
        ),
        "itinerary": asdict(result),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Estimate an EV trip from JSON")
    parser.add_argument("request_file", type=Path)
    args = parser.parse_args(argv)

    try:
        request = json.loads(args.request_file.read_text(encoding="utf-8"))
        output = run_trip(request)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        parser.exit(2, f"Trip request error: {exc}\n")

    print(json.dumps(output, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())