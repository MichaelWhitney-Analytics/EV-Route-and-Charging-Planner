"""Local-only static web server and limited ORS road-route proxy.

Run with ORS_API_KEY set. Never commit or expose the API key to browser JS.
"""

import csv
import json
import math
import os
from dataclasses import replace
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request

from src.planning.measured_candidate_graph import build_measured_candidate_graph
from src.planning.vehicle_profile import VehicleProfile
from src.planning.verified_vehicle_profiles import load_catalog, load_profiles


ORS_URL = "https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson"
WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "vehicle_catalog.csv"
)


def validate_point(value):
    if not isinstance(value, dict):
        raise ValueError("Select a place from each suggestion list.")

    lat = value.get("latitude")
    lon = value.get("longitude")

    if (
        any(
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(number)
            for number in (lat, lon)
        )
        or not -90 <= lat <= 90
        or not -180 <= lon <= 180
    ):
        raise ValueError("Selected place coordinates are invalid.")

    return [float(lon), float(lat)]


def fetch_road_route(origin, destination, key):
    if not key:
        raise RuntimeError("ORS_API_KEY is not set in the server terminal.")

    coordinates = [validate_point(origin), validate_point(destination)]
    payload = json.dumps({"coordinates": coordinates}).encode("utf-8")

    request_object = request.Request(
        ORS_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": key,
            "Content-Type": "application/json",
            "Accept": "application/geo+json",
        },
    )

    try:
        with request.urlopen(request_object, timeout=18) as response:
            data = json.load(response)
    except error.HTTPError as exc:
        if exc.code == 429:
            raise RuntimeError(
                "Road routing provider rate limit reached (HTTP 429). "
                "Wait before retrying."
            ) from None

        if exc.code in (401, 403):
            raise RuntimeError(
                "Road routing provider rejected the request "
                f"(HTTP {exc.code}). Check API key or quota."
            ) from None

        raise RuntimeError(
            "Road routing provider returned "
            f"HTTP {exc.code}; route lookup did not complete."
        ) from None
    except (error.URLError, TimeoutError):
        raise RuntimeError(
            "Road routing connection failed or timed out."
        ) from None

    features = data.get("features") if isinstance(data, dict) else None

    if not isinstance(features, list) or not features:
        raise RuntimeError("No road route was returned for these places.")

    feature = features[0]
    geometry = feature.get("geometry", {})
    summary = feature.get("properties", {}).get("summary", {})
    distance = summary.get("distance")
    duration = summary.get("duration")

    points = (
        geometry.get("coordinates")
        if geometry.get("type") == "LineString"
        else None
    )

    if (
        not isinstance(points, list)
        or len(points) < 2
        or len(points) > 100000
        or any(
            not isinstance(point, list)
            or len(point) < 2
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in point[:2]
            )
            for point in points
        )
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in (distance, duration)
        )
    ):
        raise RuntimeError(
            "Road routing returned incomplete or invalid geometry."
        )

    return {
        "geometry": geometry,
        "distance_miles": distance / 1609.344,
        "driving_minutes": duration / 60,
        "origin": coordinates[0],
        "destination": coordinates[1],
        "note": (
            "Direct road route only. No charging stops or battery outcomes "
            "have been calculated."
        ),
    }


def _build_profile_from_payload(payload):
    if "vehicle_id" in payload:
        if "vehicle" in payload:
            raise ValueError(
                "Provide either a catalog vehicle ID or a custom profile, "
                "not both."
            )

        return profile_for_catalog_id(
            payload["vehicle_id"],
            payload.get("minimum_arrival_percent", 10.0),
        )

    vehicle = payload.get("vehicle")

    if not isinstance(vehicle, dict):
        raise ValueError("Provide a custom vehicle profile.")

    allowed = (
        "name",
        "usable_battery_kwh",
        "driving_kwh_per_100_miles",
        "max_dc_charge_kw",
        "connector",
        "minimum_arrival_percent",
    )

    if (
        set(vehicle) != set(allowed)
        or not isinstance(vehicle["name"], str)
        or len(vehicle["name"]) > 80
    ):
        raise ValueError(
            "Provide all six custom vehicle fields with a short name."
        )

    return VehicleProfile(**vehicle)


def _profile_basis(payload):
    if "vehicle_id" not in payload:
        return "user_supplied"

    sourced_ids = read_charging_profile_ids()["vehicle_ids"]

    return (
        "sourced"
        if payload["vehicle_id"] in sourced_ids
        else "estimated"
    )


def _estimate_warning(profile_basis):
    if profile_basis != "estimated":
        return ""

    return (
        " Estimated profile: battery energy is derived from this model's EPA "
        "range and electricity use with an assumed 85% wall-to-battery "
        "factor. Actual battery capacity, road energy use, charging "
        "connector, DC speed, and charger compatibility are unverified."
    )


def _planner_result(
    result,
    profile_basis,
    search_mode,
    *,
    recovery_attempted=False,
):
    selection = result["selection"]

    return {
        "status": selection["status"],
        "profile_basis": profile_basis,
        "search_mode": search_mode,
        "recovery_attempted": recovery_attempted,
        "selected_site_names": selection.get("selected_site_names", []),
        "itinerary": selection["itinerary"],
        "candidate_sites_considered": result["ordered_sites"],
        "search_coverage": result.get("search_coverage", {}),
        "baseline_road_miles": result["baseline_road_miles"],
        "disclaimer": (
            result["disclaimer"]
            + " "
            + selection["note"]
            + _estimate_warning(profile_basis)
        ),
    }


def build_conditional_plan(payload):
    """Build a bounded charging plan along the displayed direct road corridor.

    The standard pass preserves the normal public-demo workload. If that
    measured graph cannot establish a reserve-safe path, one bounded expanded
    recovery pass increases station sampling and measured candidate coverage.
    This does not request an alternate road route or verify charger usability.
    """
    if not isinstance(payload, dict):
        raise ValueError("Planning request must be an object.")

    origin = payload.get("origin")
    destination = payload.get("destination")

    validate_point(origin)
    validate_point(destination)

    if (
        not isinstance(origin.get("label"), str)
        or not origin["label"].strip()
        or len(origin["label"]) > 120
    ):
        raise ValueError(
            "Origin needs a selected place label of at most 120 characters."
        )

    if (
        not isinstance(destination.get("label"), str)
        or not destination["label"].strip()
        or len(destination["label"]) > 120
    ):
        raise ValueError(
            "Destination needs a selected place label of at most 120 "
            "characters."
        )

    profile = _build_profile_from_payload(payload)

    start = payload.get("start_percent")

    if (
        isinstance(start, bool)
        or not isinstance(start, (int, float))
        or not math.isfinite(start)
        or not 0 <= start <= 100
    ):
        raise ValueError(
            "Starting battery must be a finite percentage from 0 to 100."
        )

    # Intermediate stops preserve a 10% arrival reserve. The original,
    # user-selected profile remains the destination-reserve profile.
    stop_profile = replace(profile, minimum_arrival_percent=10.0)

    graph_arguments = {
        "radius_miles": 25,
        "limit_per_sample": 10,
        "max_sites": 8,
        "max_route_samples": 9,
        "road_lookup_budget": 12,
        "destination_profile": profile,
    }

    standard_result = build_measured_candidate_graph(
        stop_profile,
        start,
        origin["label"],
        (origin["latitude"], origin["longitude"]),
        destination["label"],
        (destination["latitude"], destination["longitude"]),
        **graph_arguments,
    )

    basis = _profile_basis(payload)

    if (
        standard_result["selection"]["status"]
        != "no_feasible_path_in_supplied_graph"
    ):
        return _planner_result(
            standard_result,
            basis,
            "standard",
        )

    # Recovery remains bounded: it searches more of the same direct road
    # corridor rather than claiming to evaluate an alternate route.
    recovery_result = build_measured_candidate_graph(
        stop_profile,
        start,
        origin["label"],
        (origin["latitude"], origin["longitude"]),
        destination["label"],
        (destination["latitude"], destination["longitude"]),
        radius_miles=35,
        limit_per_sample=15,
        max_sites=12,
        max_route_samples=12,
        road_lookup_budget=20,
        destination_profile=profile,
    )

    recovery_status = recovery_result["selection"]["status"]

    return _planner_result(
        recovery_result,
        basis,
        (
            "expanded_recovery"
            if recovery_status != "no_feasible_path_in_supplied_graph"
            else "expanded_recovery_no_path"
        ),
        recovery_attempted=True,
    )


def read_vehicle_choices(path=None):
    """Display-only BEV catalog; it is not a complete verified profile."""
    path = CATALOG_PATH if path is None else Path(path)

    try:
        if path.stat().st_size > 5_000_000:
            raise RuntimeError("Vehicle catalog is too large to display.")

        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)

            required = {
                "vehicle_id",
                "year",
                "make",
                "model",
                "electricity_kwh_per_100_miles",
                "epa_range_miles",
            }

            if (
                not reader.fieldnames
                or not required.issubset(reader.fieldnames)
            ):
                raise RuntimeError("Vehicle catalog has missing columns.")

            choices = []

            for row in reader:
                try:
                    use = float(row["electricity_kwh_per_100_miles"])
                    epa_range = float(row["epa_range_miles"])
                    vehicle_id = int(row["vehicle_id"])
                    year = int(row["year"])
                    make = row["make"].strip()
                    model = row["model"].strip()

                    if not (
                        math.isfinite(use)
                        and use > 0
                        and math.isfinite(epa_range)
                        and epa_range > 0
                        and make
                        and model
                        and 1900 <= year <= 2100
                    ):
                        continue

                    choices.append(
                        {
                            "vehicle_id": vehicle_id,
                            "year": year,
                            "make": make,
                            "model": model,
                            "electricity_kwh_per_100_miles": use,
                            "epa_range_miles": epa_range,
                        }
                    )
                except (ValueError, TypeError, AttributeError):
                    continue

            return {
                "vehicles": choices,
                "note": (
                    "EPA range and electricity use support exploratory "
                    "estimates; battery capacity, connector and charging "
                    "power are not verified for most models."
                ),
            }
    except OSError as exc:
        raise RuntimeError(
            "Processed vehicle catalog unavailable; build it locally first."
        ) from exc


def profile_for_catalog_id(vehicle_id, minimum_arrival_percent=10.0):
    """Use sourced specs where available, otherwise an unverified estimate."""
    if isinstance(vehicle_id, bool) or not isinstance(vehicle_id, int):
        raise ValueError("vehicle_id must be an integer catalog ID.")

    catalog = load_catalog(CATALOG_PATH)
    profiles_path = (
        CATALOG_PATH.parent / "verified_vehicle_profiles.json"
    )
    profiles = load_profiles(profiles_path, catalog)

    matches = [
        row
        for row in read_vehicle_choices()["vehicles"]
        if row["vehicle_id"] == vehicle_id
    ]

    if len(matches) != 1:
        raise ValueError(
            "Catalog vehicle has no unique usable consumption value."
        )

    row = matches[0]
    sourced = profiles.get(vehicle_id)

    if sourced is not None:
        return VehicleProfile(
            name=f'{row["year"]} {row["make"]} {row["model"]}',
            usable_battery_kwh=sourced["usable_battery_kwh"],
            driving_kwh_per_100_miles=(
                row["electricity_kwh_per_100_miles"]
            ),
            max_dc_charge_kw=sourced["max_dc_charge_kw"],
            connector=sourced["connector"],
            minimum_arrival_percent=minimum_arrival_percent,
        )

    # EPA electricity use is wall energy, not measured battery discharge.
    # Apply the same assumption to use and capacity so modeled full-charge
    # range remains this vehicle's EPA range.
    assumed_battery_fraction = 0.85
    estimated_use = (
        row["electricity_kwh_per_100_miles"]
        * assumed_battery_fraction
    )
    estimated_usable = row["epa_range_miles"] * estimated_use / 100

    return VehicleProfile(
        name=f'{row["year"]} {row["make"]} {row["model"]}',
        usable_battery_kwh=estimated_usable,
        driving_kwh_per_100_miles=estimated_use,
        max_dc_charge_kw=50.0,
        connector="Unverified",
        minimum_arrival_percent=minimum_arrival_percent,
    )


def read_charging_profile_ids():
    """Return IDs eligible for the conditional planning request."""
    catalog = load_catalog(CATALOG_PATH)
    registry = CATALOG_PATH.parent / "verified_vehicle_profiles.json"

    return {
        "vehicle_ids": sorted(
            load_profiles(registry, catalog)
        )
    }


class RouteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self):
        if self.path not in (
            "/api/vehicles",
            "/api/charging-profile-ids",
        ):
            return super().do_GET()

        try:
            if self.path == "/api/charging-profile-ids":
                body = read_charging_profile_ids()
            else:
                body = read_vehicle_choices()

            status = 200
        except (RuntimeError, ValueError, OSError) as exc:
            body = {"error": str(exc)}
            status = 503

        data = json.dumps(body, allow_nan=False).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path not in ("/api/route", "/api/conditional-plan"):
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if not 0 < length <= 4096:
                raise ValueError("Route request is empty or too large.")

            payload = json.loads(self.rfile.read(length))

            if not isinstance(payload, dict):
                raise ValueError("Select two locations before planning.")

            origin = payload.get("origin")
            destination = payload.get("destination")
            validate_point(origin)
            validate_point(destination)

            if self.path == "/api/conditional-plan":
                result = build_conditional_plan(payload)
            else:
                result = fetch_road_route(
                    origin,
                    destination,
                    os.environ.get("ORS_API_KEY"),
                )

            status = 200
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            result = {"error": str(exc)}
            status = 400
        except RuntimeError as exc:
            result = {"error": str(exc)}
            status = 503

        data = json.dumps(result).encode("utf-8")

        self.send_response(status)