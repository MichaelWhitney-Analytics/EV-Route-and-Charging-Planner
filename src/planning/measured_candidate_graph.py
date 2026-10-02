"""Build a bounded, measured road graph from sparsely discovered stations.

Offline tests inject route and station functions. This does not verify chargers or
connect the result to the web preview. API failures are not interpreted as no path.
"""

from math import atan2, ceil, cos, isfinite, radians, sin, sqrt

from src.ingestion.live_road_route import get_road_route
from src.ingestion.live_stations import find_nearby_dc_stations
from src.ingestion.route_station_candidates import decode_polyline, sample_route
from src.planning.connector_screening import CONNECTOR_LABELS
from src.planning.station_sites import group_station_sites
from src.planning.stop_selection import select_fewest_stops


def _point(lat, lon):
    if (
        isinstance(lat, bool)
        or isinstance(lon, bool)
        or not isinstance(lat, (int, float))
        or not isinstance(lon, (int, float))
        or not isfinite(lat)
        or not isfinite(lon)
        or not -90 <= lat <= 90
        or not -180 <= lon <= 180
    ):
        raise ValueError("Coordinates must be finite valid latitude/longitude")
    return float(lat), float(lon)


def _distance(a, b):
    p, q = map(radians, (a[0], b[0]))
    dl = radians(b[1] - a[1])
    h = sin((q - p) / 2) ** 2 + cos(p) * cos(q) * sin(dl / 2) ** 2
    return 3958.7613 * 2 * atan2(sqrt(h), sqrt(max(0, 1 - h)))


def _position(point, geometry):
    """Approximate progress by nearest segment, in geometry-distance miles."""
    cumulative = 0.0
    best = None

    for a, b in zip(geometry, geometry[1:]):
        length = _distance(a, b)
        latitude_scale = 69.0
        longitude_scale = 69.0 * cos(radians((a[0] + b[0]) / 2))
        x = (b[1] - a[1]) * longitude_scale
        y = (b[0] - a[0]) * latitude_scale
        px = (point[1] - a[1]) * longitude_scale
        py = (point[0] - a[0]) * latitude_scale

        fraction = (
            max(0.0, min(1.0, (px * x + py * y) / (x * x + y * y)))
            if x * x + y * y
            else 0.0
        )

        projected = (
            a[0] + fraction * (b[0] - a[0]),
            a[1] + fraction * (b[1] - a[1]),
        )
        candidate = (_distance(point, projected), cumulative + fraction * length)

        if best is None or candidate < best:
            best = candidate

        cumulative += length

    return best


def _site_connector_status(profile, site, records_by_id):
    """Screen listed plugs; never claim live availability or adapter support."""
    required = CONNECTOR_LABELS.get(profile.connector.strip().upper())

    if required is None:
        return "vehicle_connector_unverified"

    labels = set()

    for station_id in site["station_ids"]:
        record = records_by_id.get(station_id, {})
        reported = record.get("connector_types_reported")

        if isinstance(reported, list):
            labels.update(
                label.strip().upper()
                for label in reported
                if isinstance(label, str) and label.strip()
            )

    if required in labels:
        return "reported_connector_match"

    if labels:
        return "reported_connector_mismatch"

    return "connector_not_reported"


def build_measured_candidate_graph(
    profile,
    start_percent,
    origin_name,
    origin,
    destination_name,
    destination,
    *,
    radius_miles=5,
    limit_per_sample=10,
    max_sites=8,
    max_route_samples=9,
    road_lookup_budget=18,
    road_lookup=None,
    station_lookup=None,
    destination_profile=None,
):
    """Build a bounded charging graph along one direct road-route corridor.

    The standard planner pass uses the defaults: up to eight selected station
    sites, up to nine route samples, and up to 18 additional road lookups.
    A later recovery pass may explicitly request higher—but still bounded—
    limits after the standard graph cannot establish a reserve-safe path.

    Site ranking is route-aware but does not verify charger quality,
    availability, access, or compatibility. A sampled search cannot establish
    that every relevant charging station was found.
    """
    origin = _point(*origin)
    destination = _point(*destination)

    if destination_profile is None:
        destination_profile = profile

    if (
        isinstance(max_sites, bool)
        or not isinstance(max_sites, int)
        or not 0 <= max_sites <= 16
    ):
        raise ValueError("max_sites must be an integer from 0 to 16")

    if (
        isinstance(max_route_samples, bool)
        or not isinstance(max_route_samples, int)
        or not 3 <= max_route_samples <= 18
    ):
        raise ValueError(
            "max_route_samples must be an integer from 3 to 18"
        )

    if (
        isinstance(road_lookup_budget, bool)
        or not isinstance(road_lookup_budget, int)
        or not 0 <= road_lookup_budget <= 48
    ):
        raise ValueError(
            "road_lookup_budget must be an integer from 0 to 48"
        )

    if (
        isinstance(limit_per_sample, bool)
        or not isinstance(limit_per_sample, int)
        or not 1 <= limit_per_sample <= 200
    ):
        raise ValueError(
            "limit_per_sample must be an integer from 1 to 200"
        )

    if (
        isinstance(radius_miles, bool)
        or not isinstance(radius_miles, (int, float))
        or not isfinite(radius_miles)
        or not 0 < radius_miles <= 500
    ):
        raise ValueError(
            "radius_miles must be finite and greater than 0, at most 500"
        )

    road = road_lookup if road_lookup is not None else get_road_route
    stations = (
        station_lookup
        if station_lookup is not None
        else find_nearby_dc_stations
    )

    baseline = road(*origin, *destination)
    geometry = decode_polyline(baseline["encoded_geometry"])

    sample_count = min(
        max_route_samples,
        max(3, ceil(baseline["distance_miles"] / 30) + 1),
    )
    samples = sample_route(geometry, count=sample_count)

    records = []

    for sample in samples:
        response = stations(
            *sample,
            radius_miles=radius_miles,
            limit=limit_per_sample,
        )

        if (
            not isinstance(response, dict)
            or not isinstance(response.get("stations"), list)
        ):
            raise RuntimeError(
                "Station lookup returned an invalid station list"
            )

        records.extend(response["stations"])

    unique = {}

    for item in records:
        if isinstance(item, dict) and item.get("id") is not None:
            unique.setdefault(item["id"], item)

    ranked = []
    connector_mismatches_excluded = 0

    for site in group_station_sites(list(unique.values())):
        connector_status = _site_connector_status(profile, site, unique)

        if connector_status == "reported_connector_mismatch":
            connector_mismatches_excluded += 1
            continue

        record = site["representative"]

        try:
            coordinates = _point(
                record["latitude"],
                record["longitude"],
            )
        except (KeyError, ValueError, TypeError):
            continue

        lateral, progress = _position(coordinates, geometry)

        if lateral <= radius_miles:
            ranked.append(
                (
                    lateral,
                    progress,
                    str(record.get("id")),
                    site,
                    coordinates,
                    connector_status,
                )
            )

    geometry_miles = sum(
        _distance(a, b)
        for a, b in zip(geometry, geometry[1:])
    )

    remaining = list(ranked)
    chosen = []

    for slot in range(min(max_sites, len(remaining))):
        target = geometry_miles * (slot + 1) / (max_sites + 1)

        best = min(
            remaining,
            key=lambda item: (
                abs(item[1] - target),
                item[0],
                item[2],
            ),
        )

        chosen.append(best)
        remaining.remove(best)

    chosen.sort(key=lambda row: (row[1], row[2]))

    coordinates = (
        [origin]
        + [row[4] for row in chosen]
        + [destination]
    )

    names = (
        [origin_name]
        + [
            str(
                row[3]["representative"].get("name")
                or "Station " + row[2]
            )
            for row in chosen
        ]
        + [destination_name]
    )

    matrix = [
        [None] * len(coordinates)
        for _ in coordinates
    ]

    # Measure adjacent hops first to preserve a chain, then prioritize long
    # skips within the remaining bounded road-lookup budget.
    size = len(coordinates)
    pairs = [(i, i + 1) for i in range(size - 1)]
    scheduled = set(pairs)

    # Approximate route progress prioritizes limited lookups. Measured road
    # distance—not this estimate—determines energy feasibility.
    if geometry_miles > 0:
        progress = (
            [0.0]
            + [
                row[1] / geometry_miles * baseline["distance_miles"]
                for row in chosen
            ]
            + [baseline["distance_miles"]]
        )
    else:
        progress = [
            baseline["distance_miles"] * index / (size - 1)
            for index in range(size)
        ]

    # Prioritize a connected long-hop chain, not isolated long edges.
    cursor = 0

    for _ in range(size - 1):
        next_node = None

        for j in range(size - 1, cursor, -1):
            leg_profile = (
                destination_profile
                if j == size - 1
                else profile
            )

            available_kwh = (
                leg_profile.usable_battery_kwh
                * (start_percent if cursor == 0 else 100.0)
                / 100
                - leg_profile.reserve_energy_kwh
            )

            approximate_miles = progress[j] - progress[cursor]
            straight_miles = _distance(
                coordinates[cursor],
                coordinates[j],
            )

            if (
                approximate_miles >= 0
                and approximate_miles * profile.energy_per_mile_kwh
                <= available_kwh + 1e-9
                and straight_miles * profile.energy_per_mile_kwh
                <= available_kwh + 1e-9
            ):
                next_node = j
                break

        if next_node is None:
            break

        pair = (cursor, next_node)

        if pair not in scheduled:
            pairs.append(pair)
            scheduled.add(pair)

        cursor = next_node

        if cursor == size - 1:
            break

    # Also test complete plausible one-stop options before other shortcuts.
    first_leg_kwh = (
        profile.usable_battery_kwh
        * start_percent
        / 100
        - profile.reserve_energy_kwh
    )

    final_leg_kwh = (
        destination_profile.usable_battery_kwh
        - destination_profile.reserve_energy_kwh
    )

    for j in range(size - 2, 0, -1):
        first = (
            _distance(coordinates[0], coordinates[j])
            * profile.energy_per_mile_kwh
        )

        last = (
            _distance(coordinates[j], coordinates[-1])
            * profile.energy_per_mile_kwh
        )

        if (
            first > first_leg_kwh + 1e-9
            or last > final_leg_kwh + 1e-9
        ):
            continue

        for pair in ((0, j), (j, size - 1)):
            if pair not in scheduled:
                pairs.append(pair)
                scheduled.add(pair)

    for pair in sorted(
        (
            (i, j)
            for i in range(size)
            for j in range(i + 1, size)
            if (i, j) not in scheduled
        ),
        key=lambda pair: (-(pair[1] - pair[0]), pair[0]),
    ):
        pairs.append(pair)

    road_lookups_used = 0

    for i, j in pairs:
        is_baseline = i == 0 and j == len(coordinates) - 1

        leg_profile = (
            destination_profile
            if j == len(coordinates) - 1
            else profile
        )

        available_kwh = (
            leg_profile.usable_battery_kwh
            * (start_percent if i == 0 else 100.0)
            / 100
            - leg_profile.reserve_energy_kwh
        )

        straight_line_kwh = (
            _distance(coordinates[i], coordinates[j])
            * profile.energy_per_mile_kwh
        )

        if straight_line_kwh > available_kwh + 1e-9:
            continue

        if (
            not is_baseline
            and road_lookups_used >= road_lookup_budget
        ):
            continue

        if is_baseline:
            result = baseline
        else:
            result = road(*coordinates[i], *coordinates[j])
            road_lookups_used += 1

        miles = result["distance_miles"]

        if (
            isinstance(miles, bool)
            or not isinstance(miles, (int, float))
            or not isfinite(miles)
            or miles < 0
        ):
            raise RuntimeError(
                "Road routing returned an invalid distance"
            )

        matrix[i][j] = miles

    selection = select_fewest_stops(
        profile,
        start_percent,
        origin_name,
        names[1:-1],
        destination_name,
        matrix,
        destination_profile=destination_profile,
    )

    return {
        "selection": selection,
        "search_coverage": {
            "route_samples": len(samples),
            "station_records_returned": len(records),
            "unique_station_records": len(unique),
            "sites_near_route": len(ranked),
            "sites_excluded_reported_connector_mismatch": (
                connector_mismatches_excluded
            ),
            "sites_measured": len(chosen),
            "additional_road_lookups": road_lookups_used,
            "additional_road_lookup_budget": road_lookup_budget,
        },
        "ordered_sites": [
            {
                "station_ids": row[3]["station_ids"],
                "name": names[index + 1],
                "connector_screen": row[5],
                "address": row[3]["representative"].get("address"),
                "city": row[3]["representative"].get("city"),
                "state": row[3]["representative"].get("state"),
                "latitude": row[4][0],
                "longitude": row[4][1],
                "approximate_geometry_progress_miles": row[1],
                "approximate_geometry_offset_miles": row[0],
            }
            for index, row in enumerate(chosen)
        ],
        "road_miles": matrix,
        "baseline_road_miles": baseline["distance_miles"],
        "disclaimer": (
            "Exploratory conditional graph: route samples and candidate "
            "sites are bounded; geometry ordering is approximate; pairwise "
            "routes may backtrack; connector compatibility, access, live "
            "availability, charging time, and fastest trip are unverified."
        ),
    }