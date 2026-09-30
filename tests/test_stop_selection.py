import pytest

from src.planning.stop_selection import select_fewest_stops
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def vehicle():
    return VehicleProfile("Test EV", 75, 30, 150, "CCS", 10)


def graph(size, edges):
    matrix = [[None] * size for _ in range(size)]
    for (i, j), miles in edges.items():
        matrix[i][j] = miles
    return matrix


def test_direct_feasible_route_has_no_stops(vehicle):
    result = select_fewest_stops(vehicle, 80, "Start", ["Candidate"], "End",
                                graph(3, {(0, 1): 20, (1, 2): 20, (0, 2): 40}))
    assert result["status"] == "conditional_energy_path"
    assert result["site_count"] == 0
    assert [step["kind"] for step in result["itinerary"]["timeline"]] == ["origin", "destination"]


def test_long_route_uses_one_supplied_site(vehicle):
    result = select_fewest_stops(vehicle, 80, "Start", ["Candidate"], "End",
                                graph(3, {(0, 1): 100, (1, 2): 100, (0, 2): 200}))
    assert result["selected_site_names"] == ["Candidate"]
    assert result["itinerary"]["timeline"][-1]["arrival_percent"] == pytest.approx(10)
    assert "unverified" in result["note"]


def test_equal_stop_paths_prefer_further_progress_over_shorter_miles(vehicle):
    result = select_fewest_stops(vehicle, 80, "Start", ["A", "B"], "End",
                                graph(4, {(0, 1): 100, (1, 2): 20, (2, 3): 100,
                                          (0, 2): 150, (1, 3): 110, (0, 3): 300}))
    assert result["site_count"] == 1
    assert result["selected_site_names"] == ["B"]


def test_equal_stop_paths_prefer_further_first_stop(vehicle):
    result = select_fewest_stops(
        vehicle, 80, "Start", ["Earlier", "Later"], "End",
        graph(4, {(0, 1): 100, (1, 3): 100,
                  (0, 2): 170, (2, 3): 40}),
    )
    assert result["selected_site_names"] == ["Later"]
    assert result["site_count"] == 1


def test_unmeasured_or_unreachable_edges_return_no_path(vehicle):
    result = select_fewest_stops(vehicle, 80, "Start", ["A"], "End",
                                graph(3, {(0, 1): 200, (1, 2): 10}))
    assert result["itinerary"] is None
    assert result["status"] == "no_feasible_path_in_supplied_graph"


def test_rejects_invalid_matrix(vehicle):
    with pytest.raises(ValueError, match="forward road distances"):
        select_fewest_stops(vehicle, 80, "Start", [], "End", graph(2, {(1, 0): 2}))

def test_uncharged_pass_through_is_not_counted_as_charging_stop(vehicle):
    result = select_fewest_stops(
        vehicle, 80, "Start", ["Pass-through", "Actual charge"], "End",
        graph(4, {(0, 1): 20, (1, 2): 80, (2, 3): 100}),
    )
    assert result["status"] == "conditional_energy_path"
    assert result["site_count"] == 1
    assert result["selected_site_names"] == ["Actual charge"]
    sites = [item for item in result["itinerary"]["timeline"]
             if item["kind"] == "site"]
    assert sites[0]["name"] == "Pass-through"
    assert sites[0]["energy_to_add_kwh"] == 0
    assert sites[0]["charge_needed_for_next_leg"] is False
    assert sites[1]["charge_needed_for_next_leg"] is True
