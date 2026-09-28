"""Limited exploratory assessment of reported connector matches and detours."""

import argparse
import json
from math import isfinite

from src.ingestion.route_station_candidates import find_route_station_candidates
from src.planning.connector_screening import screen_station_connectors
from src.planning.station_detour import compare_station_detour
from src.planning.vehicle_profile import VehicleProfile


MAX_DETOUR_CHECKS = 3


def assess_candidates(
    profile: VehicleProfile,
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    *,
    max_detour_checks: int = 2,
) -> dict:
    """Discover stations, screen listed plugs, and measure limited detours.

    Order follows lookup response, not proximity, quality, or optimality.
    One road-route call discovers the route, three station searches sample it,
    then each checked candidate makes three additional road-route calls.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    if (
        isinstance(max_detour_checks, bool)
        or not isinstance(max_detour_checks, int)
        or not 1 <= max_detour_checks <= MAX_DETOUR_CHECKS
    ):
        raise ValueError("max_detour_checks must be an integer from 1 to 3")
    for name, value, low, high in (
        ("start_lat", start_lat, -90, 90), ("start_lon", start_lon, -180, 180),
        ("end_lat", end_lat, -90, 90), ("end_lon", end_lon, -180, 180),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name} must be a finite coordinate between {low} and {high}")

    discovery = find_route_station_candidates(start_lat, start_lon, end_lat, end_lon)
    screening = screen_station_connectors(profile, discovery["candidate_stations"])
    assessments = []
    skipped_without_coordinates = 0
    for station in screening["possible_matches"]:
        if len(assessments) >= max_detour_checks:
            break
        lat = station.get("latitude")
        lon = station.get("longitude")
        if (
            isinstance(lat, bool) or isinstance(lon, bool)
            or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
            or not isfinite(lat) or not isfinite(lon)
            or not -90 <= lat <= 90 or not -180 <= lon <= 180
        ):
            skipped_without_coordinates += 1
            continue
        detour = compare_station_detour(start_lat, start_lon, lat, lon, end_lat, end_lon)
        assessments.append({"station": station, "detour": detour})

    return {
        "vehicle_connector": profile.connector,
        "route_distance_miles": discovery["route_distance_miles"],
        "discovered_count": len(discovery["candidate_stations"]),
        "reported_connector_match_count": len(screening["possible_matches"]),
        "skipped_without_coordinates": skipped_without_coordinates,
        "assessments": assessments,
        "disclaimer": "Only the first listed connector matches are assessed, up to the cap. Not ranked or optimized. Connector labels, route detours, charger access, working status, and vehicle range need further verification.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assess a few route charger candidates")
    for name in ("start_lat", "start_lon", "end_lat", "end_lon"):
        parser.add_argument(name, type=float)
    parser.add_argument("--connector", required=True, help="CCS, NACS, or CHADEMO")
    parser.add_argument("--max-checks", type=int, default=2, choices=(1, 2, 3))
    args = parser.parse_args(argv)
    try:
        # This profile is used solely to pass the declared connector through
        # the existing vehicle-profile interface. Example values are not real specs.
        profile = VehicleProfile("Connector check only", 1.0, 1.0, 1.0, args.connector)
        result = assess_candidates(
            profile, args.start_lat, args.start_lon, args.end_lat, args.end_lon,
            max_detour_checks=args.max_checks,
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Assessment error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())