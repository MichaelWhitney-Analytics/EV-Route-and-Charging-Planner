"""Limited exploratory assessment of reported connector matches and detours."""

import argparse
import json
from math import isfinite

from src.ingestion.route_station_candidates import find_route_station_candidates
from src.planning.connector_screening import screen_station_connectors
from src.planning.station_detour import compare_station_detour
from src.planning.station_sites import group_station_sites
from src.planning.vehicle_profile import VehicleProfile


MAX_DETOUR_CHECKS = 3


def assess_candidates(
    profile: VehicleProfile,
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    *,
    max_detour_checks: int = 2,
) -> dict:
    """Screen station records and check detours at a few distinct addresses.

    Listing order is not a ranking. One discovery route call and three station
    searches are followed by three road-route calls per assessed site.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    if isinstance(max_detour_checks, bool) or not isinstance(max_detour_checks, int) or not 1 <= max_detour_checks <= MAX_DETOUR_CHECKS:
        raise ValueError("max_detour_checks must be an integer from 1 to 3")
    for name, value, low, high in (
        ("start_lat", start_lat, -90, 90), ("start_lon", start_lon, -180, 180),
        ("end_lat", end_lat, -90, 90), ("end_lon", end_lon, -180, 180),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name} must be a finite coordinate between {low} and {high}")

    discovery = find_route_station_candidates(start_lat, start_lon, end_lat, end_lon)
    screening = screen_station_connectors(profile, discovery["candidate_stations"])
    sites = group_station_sites(screening["possible_matches"])
    assessments = []
    skipped_without_coordinates = 0
    for site in sites:
        if len(assessments) >= max_detour_checks:
            break
        station = site["representative"]
        lat, lon = station.get("latitude"), station.get("longitude")
        if (
            isinstance(lat, bool) or isinstance(lon, bool)
            or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
            or not isfinite(lat) or not isfinite(lon)
            or not -90 <= lat <= 90 or not -180 <= lon <= 180
        ):
            skipped_without_coordinates += 1
            continue
        detour = compare_station_detour(start_lat, start_lon, lat, lon, end_lat, end_lon)
        assessments.append({
            "station": station,
            "co_located_station_ids": site["station_ids"],
            "detour": detour,
        })

    return {
        "vehicle_connector": profile.connector,
        "route_distance_miles": discovery["route_distance_miles"],
        "discovered_count": len(discovery["candidate_stations"]),
        "reported_connector_match_count": len(screening["possible_matches"]),
        "distinct_reported_address_count": len(sites),
        "skipped_without_coordinates": skipped_without_coordinates,
        "assessments": assessments,
        "disclaimer": "Only first listed matching addresses are checked; Not ranked or optimized. Same-address records are grouped for detour sampling only. Connector fit, site access, charger availability, and vehicle range remain unverified.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Assess a few distinct route charger sites")
    for name in ("start_lat", "start_lon", "end_lat", "end_lon"):
        parser.add_argument(name, type=float)
    parser.add_argument("--connector", required=True, help="CCS, NACS, or CHADEMO")
    parser.add_argument("--max-checks", type=int, default=2, choices=(1, 2, 3))
    args = parser.parse_args(argv)
    try:
        # Placeholder inputs only satisfy the existing VehicleProfile interface;
        # no driving energy or charging estimates use these values here.
        profile = VehicleProfile("Connector check only", 1.0, 1.0, 1.0, args.connector)
        result = assess_candidates(profile, args.start_lat, args.start_lon, args.end_lat, args.end_lon, max_detour_checks=args.max_checks)
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Assessment error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())