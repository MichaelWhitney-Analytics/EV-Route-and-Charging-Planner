import pytest

from src.planning.measured_candidate_graph import build_measured_candidate_graph
from src.planning.vehicle_profile import VehicleProfile


PROFILE = VehicleProfile('Test EV', 75, 30, 150, 'CCS', 10)
GEOMETRY = '???_ibE?_ibE'  # (0,0) -> (0,1) -> (0,2), precision-5


def station(id, longitude, name=None):
    return {'id': id, 'name': name or str(id), 'address': str(id) + ' Main',
            'city': 'Test', 'state': 'CO', 'latitude': 0., 'longitude': longitude}


def test_measures_forward_pairs_and_selects_stop():
    calls = []
    records = [station(2, 1.3, 'Later'), station(1, 0.7, 'Earlier')]
    def road(a, b, c, d):
        calls.append((b, d))
        miles = {(0., 2.): 200., (0., .7): 100., (0., 1.3): 170.,
                 (.7, 1.3): 60., (.7, 2.): 100., (1.3, 2.): 40.}[(b, d)]
        return {'distance_miles': miles, 'encoded_geometry': GEOMETRY}
    def lookup(lat, lon, **kwargs):
        return {'stations': records}
    result = build_measured_candidate_graph(PROFILE, 80, 'Start', (0, 0), 'End', (0, 2),
                                            radius_miles=100, road_lookup=road, station_lookup=lookup)
    assert [s['station_ids'] for s in result['ordered_sites']] == [[1], [2]]
    assert result['ordered_sites'][0]['address'] == '1 Main'
    assert result['ordered_sites'][0]['city'] == 'Test'
    assert result['ordered_sites'][0]['state'] == 'CO'
    assert result['selection']['selected_site_names'] == ['Later']
    assert len(calls) == 6  # baseline reused; all six forward pairs measured
    assert result['road_miles'][1][0] is None


def test_no_station_still_measures_baseline_once():
    calls = []
    def road(*args):
        calls.append(args)
        return {'distance_miles': 20., 'encoded_geometry': GEOMETRY}
    result = build_measured_candidate_graph(PROFILE, 80, 'Start', (0, 0), 'End', (0, 2),
                                            road_lookup=road, station_lookup=lambda *a, **k: {'stations': []})
    assert len(calls) == 1
    assert result['selection']['site_count'] == 0


def test_route_failures_are_not_silently_marked_unreachable():
    def road(*args):
        raise RuntimeError('routing offline')
    with pytest.raises(RuntimeError, match='routing offline'):
        build_measured_candidate_graph(PROFILE, 80, 'Start', (0, 0), 'End', (0, 2), road_lookup=road)


def test_invalid_bounds_rejected_before_calls():
    with pytest.raises(ValueError, match='max_sites'):
        build_measured_candidate_graph(PROFILE, 80, 'A', (0, 0), 'B', (0, 2), max_sites=9)



def test_denser_samples_find_station_between_old_sample_points():
    records = [station(10, 0.5, "Between samples")]
    calls = []

    def road(lat1, lon1, lat2, lon2):
        return {
            "distance_miles": 115.0 * (lon2 - lon1),
            "encoded_geometry": GEOMETRY,
        }

    def lookup(lat, lon, **kwargs):
        calls.append(lon)
        found = [
            item for item in records
            if abs(item["longitude"] - lon) * 69 <= kwargs["radius_miles"]
        ]
        return {"stations": found}

    result = build_measured_candidate_graph(
        PROFILE, 80, "Start", (0, 0), "End", (0, 2),
        radius_miles=5,
        max_sites=1,
        road_lookup=road,
        station_lookup=lookup,
    )
    assert len(calls) > 3
    assert result["search_coverage"]["unique_station_records"] == 1
    assert result["selection"]["selected_site_names"] == [
        "Between samples"
    ]


def test_candidates_are_spread_along_route_not_only_closest_to_line():
    records = [
        station(1, 0.20, "Near start 1"),
        station(2, 0.25, "Near start 2"),
        {**station(3, 1.0, "Middle"), "latitude": 0.02},
        {**station(4, 1.8, "Later"), "latitude": 0.02},
    ]

    def road(lat1, lon1, lat2, lon2):
        return {
            "distance_miles": 140.0 * (lon2 - lon1),
            "encoded_geometry": GEOMETRY,
        }

    result = build_measured_candidate_graph(
        PROFILE, 80, "Start", (0, 0), "End", (0, 2),
        radius_miles=10,
        max_sites=2,
        road_lookup=road,
        station_lookup=lambda *args, **kwargs: {"stations": records},
    )
    chosen_names = [item["name"] for item in result["ordered_sites"]]
    assert "Middle" in chosen_names
    assert chosen_names != ["Near start 1", "Near start 2"]
    assert result["selection"]["status"] == "conditional_energy_path"


def test_bounded_graph_measures_farther_feasible_one_stop_skip():
    records = [
        station(index, index * 0.2, f"Site {index}")
        for index in range(1, 9)
    ]

    def road(lat1, lon1, lat2, lon2):
        return {
            "distance_miles": 140.0 * (lon2 - lon1),
            "encoded_geometry": GEOMETRY,
        }

    result = build_measured_candidate_graph(
        PROFILE, 80, "Start", (0, 0), "End", (0, 2),
        radius_miles=100,
        max_sites=8,
        road_lookup=road,
        station_lookup=lambda *args, **kwargs: {"stations": records},
    )

    assert result["selection"]["status"] == "conditional_energy_path"
    assert result["selection"]["site_count"] == 1
    assert result["selection"]["selected_site_names"] == ["Site 6"]
    assert result["search_coverage"]["additional_road_lookups"] <= 18
