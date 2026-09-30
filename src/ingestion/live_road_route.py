"""Read-only road route lookup with openrouteservice; no EV routing claims."""

import argparse
import json
from math import isfinite
import os

import requests


URL = "https://api.heigit.org/openrouteservice/v2/directions/driving-car/json"


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
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 429:
            raise RuntimeError("Road routing provider rate limit reached (HTTP 429); wait before retrying") from None
        if status in (401, 403):
            raise RuntimeError(f"Road routing provider rejected the request (HTTP {status}); check API key and quota") from None
        raise RuntimeError(f"Road routing provider returned HTTP {status}; route lookup did not complete") from None
    except requests.Timeout:
        raise RuntimeError("Road routing provider timed out") from None
    except requests.RequestException:
        raise RuntimeError("Road routing connection failed") from None
    except ValueError:
        raise RuntimeError("Road routing provider returned invalid JSON") from None

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