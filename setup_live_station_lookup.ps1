$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'src/planning/trip_cli.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run this script from the EV-Route-and-Charging-Planner project root with its existing .venv.'
}
$files = @{
    'src/ingestion/live_stations.py' = @'
"""Read-only public DC charger lookup using the AFDC/NLR nearest API."""

import argparse
import json
from math import isfinite
import os

import requests


URL = "https://developer.nlr.gov/api/alt-fuel-stations/v1/nearest.json"


def find_nearby_dc_stations(
    latitude: float,
    longitude: float,
    *,
    radius_miles: float = 25,
    limit: int = 10,
    api_key: str | None = None,
) -> dict:
    """Look up public, listed-as-available DC stations near coordinates.

    Listed station status is not live port occupancy or a working-plug guarantee.
    """
    for name, value, lower, upper in (
        ("latitude", latitude, -90, 90),
        ("longitude", longitude, -180, 180),
        ("radius_miles", radius_miles, 0, 500),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or not lower <= value <= upper
        ):
            raise ValueError(f"{name} must be finite and between {lower} and {upper}")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("limit must be an integer from 1 to 200")

    key = api_key if api_key is not None else os.getenv("NLR_API_KEY")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Set NLR_API_KEY in your terminal; never commit the key")

    params = {
        "api_key": key.strip(),
        "latitude": latitude,
        "longitude": longitude,
        "radius": radius_miles,
        "limit": limit,
        "fuel_type": "ELEC",
        "country": "US",
        "status": "E",
        "access": "public",
        "ev_charging_level": "dc_fast",
    }
    try:
        response = requests.get(URL, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError("Station lookup failed; check connectivity, key, or API status") from None

    if not isinstance(payload, dict) or not isinstance(payload.get("fuel_stations"), list):
        raise RuntimeError("Station API returned an unexpected response shape")

    stations = []
    for station in payload["fuel_stations"]:
        if not isinstance(station, dict):
            continue
        if station.get("fuel_type_code") != "ELEC" or station.get("status_code") != "E" or station.get("access_code") != "public":
            continue
        if not station.get("ev_dc_fast_num"):
            continue
        stations.append({
            "id": station.get("id"),
            "name": station.get("station_name"),
            "address": station.get("street_address"),
            "city": station.get("city"),
            "state": station.get("state"),
            "distance_miles_straight_line": station.get("distance"),
            "latitude": station.get("latitude"),
            "longitude": station.get("longitude"),
            "dc_fast_ports_reported": station.get("ev_dc_fast_num"),
            "connector_types_reported": station.get("ev_connector_types"),
        })

    return {
        "source": "AFDC Alternative Fuel Stations API (NLR)",
        "live_lookup": True,
        "disclaimer": "Station records do not confirm a working or unoccupied compatible plug; distance is not driving distance.",
        "stations": stations,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Look up nearby U.S. public DC charging stations")
    parser.add_argument("latitude", type=float)
    parser.add_argument("longitude", type=float)
    parser.add_argument("--radius", type=float, default=25)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        result = find_nearby_dc_stations(
            args.latitude, args.longitude, radius_miles=args.radius, limit=args.limit
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Station lookup error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@
    'tests/test_live_stations.py' = @'
import pytest
import requests

from src.ingestion.live_stations import find_nearby_dc_stations


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "fuel_stations": [
                {
                    "id": 123, "station_name": "Example public charger",
                    "fuel_type_code": "ELEC", "status_code": "E",
                    "access_code": "public", "ev_dc_fast_num": 2,
                    "distance": 2.3, "ev_connector_types": ["J1772COMBO"],
                },
                {
                    "id": 124, "fuel_type_code": "ELEC",
                    "status_code": "P", "access_code": "public", "ev_dc_fast_num": 2,
                },
            ]
        }


def test_queries_public_available_dc_stations(monkeypatch):
    captured = {}

    def fake_get(url, *, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)
    result = find_nearby_dc_stations(39.7, -105.0, api_key="test-key")
    assert captured["params"]["fuel_type"] == "ELEC"
    assert captured["params"]["ev_charging_level"] == "dc_fast"
    assert captured["params"]["access"] == "public"
    assert captured["params"]["status"] == "E"
    assert captured["timeout"] == 20
    assert result["stations"][0]["id"] == 123
    assert len(result["stations"]) == 1
    assert "test-key" not in str(result)


def test_missing_key_stops_before_network(monkeypatch):
    monkeypatch.delenv("NLR_API_KEY", raising=False)
    with pytest.raises(ValueError, match="NLR_API_KEY"):
        find_nearby_dc_stations(39.7, -105.0)


@pytest.mark.parametrize("lat, lon", [(91, 0), (0, -181), (float("nan"), 0), (True, 0)])
def test_rejects_invalid_coordinates(lat, lon):
    with pytest.raises(ValueError):
        find_nearby_dc_stations(lat, lon, api_key="test-key")


def test_rejects_invalid_limit():
    with pytest.raises(ValueError, match="limit"):
        find_nearby_dc_stations(39.7, -105.0, limit=201, api_key="test-key")


def test_network_error_does_not_reveal_key(monkeypatch):
    def fake_get(url, *, params, timeout):
        raise requests.RequestException("sensitive test-key")

    monkeypatch.setattr(requests, "get", fake_get)
    with pytest.raises(RuntimeError) as exc:
        find_nearby_dc_stations(39.7, -105.0, api_key="test-key")
    assert "test-key" not in str(exc.value)
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
Write-Host 'Offline tests passed. Live lookup requires your own NLR_API_KEY environment variable.'