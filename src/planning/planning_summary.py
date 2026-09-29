"""Compose limited live candidate assessment with offline energy screening."""

import argparse
import json

from src.planning.candidate_assessment import assess_candidates
from src.planning.candidate_reachability import assess_candidate_reachability
from src.planning.planning_report import format_planning_report
from src.planning.vehicle_profile import VehicleProfile


def plan_candidate_summary(
    profile: VehicleProfile,
    start_percent: float,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    *,
    max_detour_checks: int = 2,
) -> dict:
    """Make one limited discovery/road assessment, then screen its energy.

    This is not a trip recommendation or a full-route multi-stop planner.
    """
    assessment = assess_candidates(
        profile, start_lat, start_lon, end_lat, end_lon,
        max_detour_checks=max_detour_checks,
    )
    energy = assess_candidate_reachability(profile, start_percent, assessment)
    categories = {
        "no_charging_needed": [],
        "charging_needed_if_usable": [],
        "unreachable_with_reserve": [],
        "next_leg_exceeds_full_battery_with_reserve": [],
    }
    for candidate in energy["candidates"]:
        if not candidate["station_reachable_with_reserve"]:
            categories["unreachable_with_reserve"].append(candidate)
        elif candidate["next_leg_possible_from_full"] is False:
            categories["next_leg_exceeds_full_battery_with_reserve"].append(candidate)
        elif candidate["charge_for_next_leg"] is not None and candidate["charge_for_next_leg"]["charge_needed"]:
            categories["charging_needed_if_usable"].append(candidate)
        else:
            categories["no_charging_needed"].append(candidate)
    unassessed_count = max(
        0, assessment["distinct_reported_address_count"] - len(assessment["assessments"])
    )
    return {
        "vehicle_name": profile.name,
        "start_percent": start_percent,
        "route_distance_miles": assessment["route_distance_miles"],
        "discovered_record_count": assessment["discovered_count"],
        "reported_connector_match_record_count": assessment["reported_connector_match_count"],
        "distinct_reported_address_count": assessment["distinct_reported_address_count"],
        "road_detours_assessed_count": len(assessment["assessments"]),
        "not_assessed_count": unassessed_count,
        "not_assessed_note": "Includes sites beyond the detour-check cap and any skipped for missing coordinates. These sites have not been energy-screened.",
        "categories": categories,
        "disclaimer": "Exploratory estimates only. Battery and consumption are user-supplied. Reported connector matches, site access, charger availability, charging speed, road conditions, and trip completion are unverified. No candidate is recommended or guaranteed.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Limited EV candidate energy summary (live API calls)")
    for name in ("start_lat", "start_lon", "end_lat", "end_lon"):
        parser.add_argument(name, type=float)
    parser.add_argument("--name", required=True)
    parser.add_argument("--battery-kwh", type=float, required=True)
    parser.add_argument("--kwh-per-100-miles", type=float, required=True)
    parser.add_argument("--max-charge-kw", type=float, required=True)
    parser.add_argument("--connector", required=True)
    parser.add_argument("--reserve-percent", type=float, default=10)
    parser.add_argument("--start-percent", type=float, required=True)
    parser.add_argument("--max-checks", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        profile = VehicleProfile(
            args.name, args.battery_kwh, args.kwh_per_100_miles,
            args.max_charge_kw, args.connector, args.reserve_percent,
        )
        result = plan_candidate_summary(
            profile, args.start_percent, args.start_lat, args.start_lon,
            args.end_lat, args.end_lon, max_detour_checks=args.max_checks,
        )
    except (ValueError, RuntimeError, TypeError) as exc:
        parser.exit(2, f"Planning summary error: {exc}\n")
    print(format_planning_report(result) if args.format == "text" else json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())