"""Print a readable itinerary: python -m src.planning.trip_report trip.json"""

import argparse
import json
from pathlib import Path

from src.planning.trip_cli import run_trip


def format_trip_report(output: dict) -> str:
    """Format an already calculated trip result for terminal reading."""
    if not isinstance(output, dict) or "itinerary" not in output:
        raise ValueError("output must contain an itinerary")
    itinerary = output["itinerary"]
    lines = [
        f"Vehicle: {output['vehicle_name']}",
        "ESTIMATE ONLY - supplied distances and charging powers are not verified.",
        f"Total distance: {itinerary['total_distance_miles']:.1f} miles",
        f"Energy added: {itinerary['total_charge_kwh']:.1f} kWh",
        f"Estimated charging: {itinerary['total_estimated_charging_minutes']:.1f} minutes",
        f"Final charge: {itinerary['final_percent']:.1f}%",
        "",
    ]
    stops = {stop["after_leg_number"]: stop for stop in itinerary["stops"]}
    for number, leg in enumerate(itinerary["legs"], start=1):
        lines.append(
            f"Leg {number}: {leg['distance_miles']:.1f} miles; "
            f"{leg['start_percent']:.1f}% -> {leg['estimated_arrival_percent']:.1f}%"
        )
        if number in stops:
            stop = stops[number]
            lines.append(
                f"  Stop after leg {number}: add {stop['charge']['energy_to_add_kwh']:.1f} kWh; "
                f"depart at {stop['charge']['departure_percent']:.1f}%; "
                f"estimated {stop['time']['estimated_minutes']:.1f} minutes"
            )
    lines.extend(["", f"Limitations: {output['limitations']}"])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Print a readable EV trip estimate")
    parser.add_argument("request_file", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.request_file.read_text(encoding="utf-8"))
        output = run_trip(payload)
        report = format_trip_report(output)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Trip request error: {exc}\n")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())