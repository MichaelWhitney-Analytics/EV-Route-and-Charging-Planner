"""Run a supplied EV itinerary: python -m src.planning.trip_cli trip.json"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from src.planning.route_itinerary import build_itinerary
from src.planning.vehicle_profile import VehicleProfile
from src.validation.trip_request import validate_trip_request


def run_trip(request: dict) -> dict:
    """Validate the JSON request and return a serializable itinerary estimate."""
    validate_trip_request(request)
    profile = VehicleProfile(**request["vehicle"])
    result = build_itinerary(
        profile,
        tuple(request["leg_distances_miles"]),
        request["start_percent"],
        tuple(request["effective_stop_powers_kw"]),
    )
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