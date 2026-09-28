$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'src/ingestion/live_stations.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the EV-Route-and-Charging-Planner project root with its existing .venv.'
}
$files = @{
    'src/ingestion/live_road_route.py' = @'
"""Read-only road route lookup with openrouteservice; no EV routing claims."""

import argparse
import json
from math import isfinite
import os

import requests


URL = "https://api.openrouteservice.org/v2/directions/driving-car/json"


def get_road_route(
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
    *,
    api_key: str | None = None,
) -> dict:
    """Return road distance, duration, and decoded route geometry."""
    for name, value, lower, upper in (
        ("start_latitude", start_latitude, -90, 90),
        ("start_longitude", start_longitude, -180, 180),
        ("end_latitude", end_latitude, -90, 90),
        ("end_longitude", end_longitude, -180, 180),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} must be finite and between {lower} and {upper}")

    key = api_key if api_key is not None else os.getenv("ORS_API_KEY")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Set ORS_API_KEY in your terminal; never commit the key")

    try:
        response = requests.post(
            URL,
            headers={"Authorization": key.strip(), "Content-Type": "application/json"},
            json={
                "coordinates": [
                    [start_longitude, start_latitude],
                    [end_longitude, end_latitude],
                ],
                "instructions": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        raise RuntimeError("Road routing failed; check connectivity, key, coordinates, or API status") from None

    routes = payload.get("routes") if isinstance(payload, dict) else None
    if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
        raise RuntimeError("Road routing API returned no usable route")
    route = routes[0]
    summary = route.get("summary")
    if not isinstance(summary, dict) or not isinstance(summary.get("distance"), (int, float)) or not isinstance(summary.get("duration"), (int, float)):
        raise RuntimeError("Road routing API returned no usable route summary")
    if not isfinite(summary["distance"]) or not isfinite(summary["duration"]) or summary["distance"] < 0 or summary["duration"] < 0:
        raise RuntimeError("Road routing API returned invalid route measurements")
    if not isinstance(route.get("geometry"), str):
        raise RuntimeError("Road routing API returned no encoded route geometry")

    return {
        "source": "openrouteservice driving-car directions",
        "distance_miles": summary["distance"] / 1609.344,
        "estimated_driving_minutes": summary["duration"] / 60,
        "encoded_geometry": route["geometry"],
        "disclaimer": "Road route is not an EV-feasibility or charger-availability guarantee.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Look up a road route between two coordinates")
    parser.add_argument("start_latitude", type=float)
    parser.add_argument("start_longitude", type=float)
    parser.add_argument("end_latitude", type=float)
    parser.add_argument("end_longitude", type=float)
    args = parser.parse_args(argv)
    try:
        result = get_road_route(
            args.start_latitude, args.start_longitude,
            args.end_latitude, args.end_longitude,
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Road routing error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'@
    'tests/test_live_road_route.py' = @'
import pytest
import requests

from src.ingestion.live_road_route import get_road_route


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"routes": [{"summary": {"distance": 16093.44, "duration": 900}, "geometry": "encoded-example"}]}


def test_returns_road_distance_and_duration(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    result = get_road_route(39.7, -105.0, 39.8, -104.9, api_key="test-key")
    assert captured["body"]["coordinates"] == [[-105.0, 39.7], [-104.9, 39.8]]
    assert result["distance_miles"] == pytest.approx(10)
    assert result["estimated_driving_minutes"] == pytest.approx(15)
    assert result["encoded_geometry"] == "encoded-example"
    assert "test-key" not in str(result)


def test_missing_key_prevents_request(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ORS_API_KEY"):
        get_road_route(39.7, -105.0, 39.8, -104.9)


@pytest.mark.parametrize("value", [91, float("nan"), True])
def test_rejects_invalid_latitude(value):
    with pytest.raises(ValueError, match="start_latitude"):
        get_road_route(value, -105.0, 39.8, -104.9, api_key="test-key")


def test_network_error_hides_key(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        raise requests.RequestException("test-key is sensitive")

    monkeypatch.setattr(requests, "post", fake_post)
    with pytest.raises(RuntimeError) as exc:
        get_road_route(39.7, -105.0, 39.8, -104.9, api_key="test-key")
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
Write-Host 'Offline routing tests passed. Live lookup needs your own ORS_API_KEY.'