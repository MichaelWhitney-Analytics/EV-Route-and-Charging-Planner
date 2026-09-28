$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'src/ingestion/live_road_route.py') -or -not (Test-Path 'src/ingestion/live_stations.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the EV-Route-and-Charging-Planner project root after both live-data modules are installed.'
}
$files = @{
    'src/ingestion/route_station_candidates.py' = @'
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


def sample_route(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Choose start, approximate half-way-by-geometry point, and end."""
    if len(points) < 2:
        raise ValueError("route needs at least two geometry points")
    lengths = [_crow_flight_miles(a, b) for a, b in zip(points, points[1:])]
    halfway = sum(lengths) / 2
    walked = 0.0
    middle = points[0]
    for index, length in enumerate(lengths):
        if walked + length >= halfway:
            fraction = (halfway - walked) / length if length else 0
            middle = tuple(a + (b - a) * fraction for a, b in zip(points[index], points[index + 1]))
            break
        walked += length
    return [points[0], middle, points[-1]]


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
'@
    'tests/test_route_station_candidates.py' = @'
import pytest

import src.ingestion.route_station_candidates as candidate_module
from src.ingestion.route_station_candidates import decode_polyline, find_route_station_candidates, sample_route


def test_decodes_known_polyline():
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [
        (38.5, -120.2), (40.7, -120.95), (43.252, -126.453),
    ]


@pytest.mark.parametrize("encoded", ["", "?", "!", "_p~iF"])
def test_rejects_malformed_polyline(encoded):
    with pytest.raises(ValueError):
        decode_polyline(encoded)


def test_samples_start_middle_and_end():
    samples = sample_route([(0, 0), (0, 1), (0, 2)])
    assert samples[0] == (0, 0)
    assert samples[1][1] == pytest.approx(1)
    assert samples[2] == (0, 2)


def test_deduplicates_station_ids(monkeypatch):
    monkeypatch.setattr(candidate_module, "get_road_route", lambda *args: {
        "distance_miles": 12, "estimated_driving_minutes": 20,
        "encoded_geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
    })
    calls = []

    def fake_lookup(lat, lon, *, radius_miles, limit):
        calls.append((lat, lon, radius_miles, limit))
        return {"stations": [{"id": 123, "name": "Example"}]}

    monkeypatch.setattr(candidate_module, "find_nearby_dc_stations", fake_lookup)
    result = find_route_station_candidates(38.5, -120.2, 43.252, -126.453)
    assert len(calls) == 3
    assert len(result["candidate_stations"]) == 1
    assert result["candidate_stations"][0]["id"] == 123
    assert "no detour" in result["disclaimer"]
'@
}
foreach ($path in $files.Keys) {
    if (Test-Path $path) { throw "Refusing to overwrite existing file: $path" }
}
foreach ($path in $files.Keys) {
    $parent = Split-Path $path -Parent
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $path), $files[$path], [System.Text.UTF8Encoding]::new($false))
    Write-Host "Created $path"
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. Live candidate lookup requires both ORS_API_KEY and NLR_API_KEY.'