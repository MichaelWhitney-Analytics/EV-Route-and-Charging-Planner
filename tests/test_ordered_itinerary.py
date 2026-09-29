import pytest

from src.planning.ordered_itinerary import build_ordered_itinerary
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def vehicle():
    return VehicleProfile("Illustrative EV", 75, 30, 150, "CCS", 10)


def test_direct_trip_has_no_phantom_charging_stop(vehicle):
    result = build_ordered_itinerary(vehicle, 80, "Origin", [
        {"name": "Destination", "kind": "destination", "distance_miles": 100}
    ])
    assert [step["kind"] for step in result["timeline"]] == ["origin", "destination"]
    assert result["timeline"][1]["arrival_percent"] == pytest.approx(40)
    assert result["total_road_miles"] == 100
    assert result["arrival_reserve_percent"] == 10


def test_one_ordered_site_carries_battery_to_destination(vehicle):
    result = build_ordered_itinerary(vehicle, 80, "Origin", [
        {"name": "Supplied site", "kind": "site", "distance_miles": 100},
        {"name": "Destination", "kind": "destination", "distance_miles": 100},
    ])
    site, destination = result["timeline"][1:]
    assert site["arrival_percent"] == pytest.approx(40)
    assert site["departure_percent"] == pytest.approx(50)
    assert site["energy_to_add_kwh"] == pytest.approx(7.5)
    assert site["charge_needed_for_next_leg"] is True
    assert site["site_usable"] == "unverified"
    assert destination["arrival_percent"] == pytest.approx(10)


def test_multiple_sites_carry_forward_percentages(vehicle):
    result = build_ordered_itinerary(vehicle, 80, "Origin", [
        {"name": "A", "kind": "site", "distance_miles": 100},
        {"name": "B", "kind": "site", "distance_miles": 100},
        {"name": "End", "kind": "destination", "distance_miles": 100},
    ])
    assert [step["arrival_percent"] for step in result["timeline"][1:]] == pytest.approx([40, 10, 10])
    assert result["timeline"][2]["departure_percent"] == pytest.approx(50)


def test_optional_site_is_not_called_charging_stop(vehicle):
    result = build_ordered_itinerary(vehicle, 80, "Origin", [
        {"name": "Optional", "kind": "site", "distance_miles": 20},
        {"name": "End", "kind": "destination", "distance_miles": 20},
    ])
    assert result["timeline"][1]["charge_needed_for_next_leg"] is False
    assert result["timeline"][1]["energy_to_add_kwh"] == 0


def test_unreachable_first_leg_fails(vehicle):
    with pytest.raises(ValueError, match="leg 1 cannot preserve"):
        build_ordered_itinerary(vehicle, 80, "Origin", [
            {"name": "End", "kind": "destination", "distance_miles": 200}
        ])


def test_next_leg_exceeds_full_battery(vehicle):
    with pytest.raises(ValueError, match="leg 2 exceeds a full battery"):
        build_ordered_itinerary(vehicle, 80, "Origin", [
            {"name": "Site", "kind": "site", "distance_miles": 50},
            {"name": "End", "kind": "destination", "distance_miles": 226},
        ])


@pytest.mark.parametrize("bad", [float("nan"), -1, True, "10"])
def test_invalid_road_leg_distance(vehicle, bad):
    with pytest.raises(ValueError, match="finite nonnegative"):
        build_ordered_itinerary(vehicle, 80, "Origin", [
            {"name": "End", "kind": "destination", "distance_miles": bad}
        ])


def test_rejects_wrong_order(vehicle):
    with pytest.raises(ValueError, match="kind must be site"):
        build_ordered_itinerary(vehicle, 80, "Origin", [
            {"name": "Early destination", "kind": "destination", "distance_miles": 20},
            {"name": "End", "kind": "destination", "distance_miles": 20},
        ])