"""Build a bounded, measured road graph from sparsely discovered stations.

Offline tests inject route and station functions. This does not verify chargers or
connect the result to the web preview. API failures are not interpreted as no path.
"""

from math import atan2, ceil, cos, isfinite, radians, sin, sqrt

from src.ingestion.live_road_route import get_road_route
from src.ingestion.live_stations import find_nearby_dc_stations
from src.ingestion.route_station_candidates import decode_polyline, sample_route
from src.planning.station_sites import group_station_sites
from src.planning.stop_selection import select_fewest_stops


def _point(lat, lon):
    if (isinstance(lat, bool) or isinstance(lon, bool)
            or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
            or not isfinite(lat) or not isfinite(lon)
            or not -90 <= lat <= 90 or not -180 <= lon <= 180):
        raise ValueError('Coordinates must be finite valid latitude/longitude')
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
        fraction = max(0.0, min(1.0, (px*x + py*y) / (x*x + y*y))) if x*x + y*y else 0.0
        projected = (a[0] + fraction*(b[0] - a[0]), a[1] + fraction*(b[1] - a[1]))
        candidate = (_distance(point, projected), cumulative + fraction*length)
        if best is None or candidate < best:
            best = candidate
        cumulative += length
    return best


def build_measured_candidate_graph(profile, start_percent, origin_name, origin,
                                   destination_name, destination, *, radius_miles=5,
                                   limit_per_sample=10, max_sites=8,
                                   road_lookup=None, station_lookup=None,
                                   destination_profile=None):
    """Discover at three samples, order up to eight sites, measure all forward legs.

    Site ranking is by proximity to the baseline route, not charger quality.
    A sampled/limited search cannot establish that all relevant sites were found.
    """
    origin = _point(*origin)
    destination = _point(*destination)
    if destination_profile is None:
        destination_profile = profile
    if isinstance(max_sites, bool) or not isinstance(max_sites, int) or not 0 <= max_sites <= 8:
        raise ValueError('max_sites must be an integer from 0 to 8')
    if isinstance(limit_per_sample, bool) or not isinstance(limit_per_sample, int) or not 1 <= limit_per_sample <= 200:
        raise ValueError('limit_per_sample must be an integer from 1 to 200')
    if isinstance(radius_miles, bool) or not isinstance(radius_miles, (int, float)) or not isfinite(radius_miles) or not 0 < radius_miles <= 500:
        raise ValueError('radius_miles must be finite and greater than 0, at most 500')
    road = road_lookup if road_lookup is not None else get_road_route
    stations = station_lookup if station_lookup is not None else find_nearby_dc_stations
    baseline = road(*origin, *destination)
    geometry = decode_polyline(baseline['encoded_geometry'])
    sample_count = min(9, max(3, ceil(baseline['distance_miles'] / 30) + 1))
    samples = sample_route(geometry, count=sample_count)
    records = []
    for sample in samples:
        response = stations(
            *sample, radius_miles=radius_miles, limit=limit_per_sample
        )
        if not isinstance(response, dict) or not isinstance(response.get('stations'), list):
            raise RuntimeError('Station lookup returned an invalid station list')
        records.extend(response['stations'])
    unique = {}
    for item in records:
        if isinstance(item, dict) and item.get('id') is not None:
            unique.setdefault(item['id'], item)
    ranked = []
    for site in group_station_sites(list(unique.values())):
        record = site['representative']
        try:
            coordinates = _point(record['latitude'], record['longitude'])
        except (KeyError, ValueError, TypeError):
            continue
        lateral, progress = _position(coordinates, geometry)
        if lateral <= radius_miles:
            ranked.append((lateral, progress, str(record.get('id')), site, coordinates))
    geometry_miles = sum(
        _distance(a, b) for a, b in zip(geometry, geometry[1:])
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
    chosen.sort(key=lambda x: (x[1], x[2]))
    coordinates = [origin] + [row[4] for row in chosen] + [destination]
    names = [origin_name] + [str(row[3]['representative'].get('name') or 'Station ' + row[2]) for row in chosen] + [destination_name]
    matrix = [[None] * len(coordinates) for _ in coordinates]
    # Prioritize short forward hops. A long route needs a connected chain
    # before it needs every possible shortcut between distant sites.
    pairs = sorted(
        ((i, j) for i in range(len(coordinates))
         for j in range(i + 1, len(coordinates))),
        key=lambda pair: (pair[1] - pair[0], pair[0]),
    )
    road_lookup_budget = 18
    road_lookups_used = 0
    for i, j in pairs:
        is_baseline = i == 0 and j == len(coordinates) - 1
        leg_profile = destination_profile if j == len(coordinates) - 1 else profile
        available_kwh = (
            leg_profile.usable_battery_kwh
            * (start_percent if i == 0 else 100.0) / 100
            - leg_profile.reserve_energy_kwh
        )
        straight_line_kwh = (
            _distance(coordinates[i], coordinates[j])
            * profile.energy_per_mile_kwh
        )
        if straight_line_kwh > available_kwh + 1e-9:
            continue
        if not is_baseline and road_lookups_used >= road_lookup_budget:
            continue
        if is_baseline:
            result = baseline
        else:
            result = road(*coordinates[i], *coordinates[j])
            road_lookups_used += 1
        miles = result['distance_miles']
        if (isinstance(miles, bool) or not isinstance(miles, (int, float))
                or not isfinite(miles) or miles < 0):
            raise RuntimeError('Road routing returned an invalid distance')
        matrix[i][j] = miles
    selection = select_fewest_stops(
        profile, start_percent, origin_name, names[1:-1],
        destination_name, matrix, destination_profile=destination_profile,
    )
    return {
        'selection': selection,
        'search_coverage': {
            'route_samples': len(samples),
            'station_records_returned': len(records),
            'unique_station_records': len(unique),
            'sites_near_route': len(ranked),
            'sites_measured': len(chosen),
            'additional_road_lookups': road_lookups_used,
            'additional_road_lookup_budget': road_lookup_budget,
        },
        'ordered_sites': [{'station_ids': row[3]['station_ids'], 'name': names[index + 1],
                           'address': row[3]['representative'].get('address'),
                           'city': row[3]['representative'].get('city'),
                           'state': row[3]['representative'].get('state'),
                           'latitude': row[4][0], 'longitude': row[4][1],
                           'approximate_geometry_progress_miles': row[1],
                           'approximate_geometry_offset_miles': row[0]}
                          for index, row in enumerate(chosen)],
        'road_miles': matrix,
        'baseline_road_miles': baseline['distance_miles'],
        'disclaimer': 'Exploratory conditional graph: at most nine route samples and a bounded subset; '
                      'geometry ordering is approximate; pairwise routes may backtrack; '
                      'connector compatibility, access, live availability, charging time, and fastest trip unverified.',
    }
