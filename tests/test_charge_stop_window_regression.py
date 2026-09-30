from dataclasses import replace

from src.planning.measured_candidate_graph import build_measured_candidate_graph
from src.planning.vehicle_profile import VehicleProfile


GEOMETRY = "???_ibE?_ibE"


def test_long_trip_does_not_count_early_pass_through_as_charge():
    profile = VehicleProfile("Illustrative EV", 75, 30, 150, "CCS", 10)
    positions = [51, 108, 183, 218, 269, 320, 362, 435]
    records = [
        {
            "id": index,
            "name": f"Site {index}",
            "address": f"{index} Test Road",
            "city": "Test",
            "state": "WA",
            "latitude": 0.0,
            "longitude": miles / 245.0,
        }
        for index, miles in enumerate(positions, 1)
    ]

    def road(lat1, lon1, lat2, lon2):
        return {
            "distance_miles": 245.0 * (lon2 - lon1),
            "encoded_geometry": GEOMETRY,
        }

    result = build_measured_candidate_graph(
        profile, 90, "Start", (0, 0), "End", (0, 2),
        radius_miles=100,
        max_sites=8,
        destination_profile=replace(profile, minimum_arrival_percent=25),
        road_lookup=road,
        station_lookup=lambda *args, **kwargs: {"stations": records},
    )

    selection = result["selection"]
    assert selection["status"] == "conditional_energy_path"
    stops = [
        entry for entry in selection["itinerary"]["timeline"]
        if entry["kind"] == "site"
    ]
    assert len(stops) == 2, [s["name"] for s in stops]
    assert all(s["charge_needed_for_next_leg"] for s in stops), stops
    assert all(10 - 1e-9 <= s["arrival_percent"] <= 20 for s in stops), stops
    assert selection["itinerary"]["timeline"][-1]["arrival_percent"] >= 25 - 1e-9
    assert result["search_coverage"]["additional_road_lookups"] <= 18
