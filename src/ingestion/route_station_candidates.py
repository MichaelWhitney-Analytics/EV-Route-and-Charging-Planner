"""Discover possible DC chargers near sampled points on a road route."""

import argparse
import json
from math import atan2, cos, radians, sin, sqrt

from src.ingestion.live_road_route import get_road_route
from src.ingestion.live_stations import find_nearby_dc_stations


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode standard precision-5 Google-format polyline to (lat, lon)."""
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("encoded geometry must be a nonempty string")
    values = []
    index = 0
    for _ in range(2 * len(encoded)):
        if index >= len(encoded):
            break
        shift = 0
        value = 0
        while True:
            if index >= len(encoded):
                raise ValueError("truncated encoded geometry")
            char = ord(encoded[index]) - 63
            index += 1
            if char < 0 or char > 63 or shift > 35:
                raise ValueError("invalid encoded geometry")
            value |= (char & 0x1F) << shift
            if char < 0x20:
                break
            shift += 5
        values.append((value >> 1) ^ -(value & 1))
    if len(values) < 4 or len(values) % 2:
        raise ValueError("encoded geometry needs at least two points")
    latitude = longitude = 0
    points = []
    for i in range(0, len(values), 2):
        latitude += values[i]
        longitude += values[i + 1]
        lat, lon = latitude / 1e5, longitude / 1e5
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("decoded geometry has invalid coordinates")
        points.append((lat, lon))
    return points


def _crow_flight_miles(first, second):
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 3958.7613 * 2 * atan2(sqrt(a), sqrt(max(0, 1 - a)))


def sample_route(
    points: list[tuple[float, float]], count: int = 3
) -> list[tuple[float, float]]:
    """Sample evenly by approximate geometry distance, including both ends."""
    if len(points) < 2:
        raise ValueError("route needs at least two geometry points")
    if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= 18:
        raise ValueError("sample count must be an integer from 2 to 18")

    lengths = [
        _crow_flight_miles(a, b)
        for a, b in zip(points, points[1:])
    ]
    total = sum(lengths)
    if total == 0:
        return [points[0]] * (count - 1) + [points[-1]]

    result = [points[0]]
    segment = 0
    walked = 0.0

    for step in range(1, count - 1):
        target = total * step / (count - 1)
        while (
            segment < len(lengths) - 1
            and walked + lengths[segment] < target
        ):
            walked += lengths[segment]
            segment += 1

        length = lengths[segment]
        fraction = (target - walked) / length if length else 0.0
        a, b = points[segment], points[segment + 1]
        result.append(
            tuple(
                first + (second - first) * fraction
                for first, second in zip(a, b)
            )
        )

    result.append(points[-1])
    return result


def find_route_station_candidates(start_lat, start_lon, end_lat, end_lon, *, radius_miles=5, limit_per_sample=10):
    """Find candidate station records; does not validate detours or vehicle fit."""
    route = get_road_route(start_lat, start_lon, end_lat, end_lon)
    samples = sample_route(decode_polyline(route["encoded_geometry"]))
    stations_by_id = {}
    for lat, lon in samples:
        lookup = find_nearby_dc_stations(lat, lon, radius_miles=radius_miles, limit=limit_per_sample)
        for station in lookup["stations"]:
            if station.get("id") is not None:
                stations_by_id.setdefault(station["id"], station)
    return {
        "route_distance_miles": route["distance_miles"],
        "estimated_driving_minutes": route["estimated_driving_minutes"],
        "sample_points": [{"latitude": lat, "longitude": lon} for lat, lon in samples],
        "candidate_stations": list(stations_by_id.values()),
        "disclaimer": "Sparse sampled-point lookup only. Stations may be off-route, incompatible, unavailable, or unreachable; no detour, optimality, or charging feasibility has been calculated.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Find station candidates near three sampled road-route points")
    for name in ("start_latitude", "start_longitude", "end_latitude", "end_longitude"):
        parser.add_argument(name, type=float)
    parser.add_argument("--radius", type=float, default=5)
    args = parser.parse_args(argv)
    try:
        result = find_route_station_candidates(
            args.start_latitude, args.start_longitude,
            args.end_latitude, args.end_longitude, radius_miles=args.radius,
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Candidate lookup error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())