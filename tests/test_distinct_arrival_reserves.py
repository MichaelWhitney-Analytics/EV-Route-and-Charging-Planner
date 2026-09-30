from src.planning.vehicle_profile import VehicleProfile
from src.planning.stop_selection import select_fewest_stops


def test_stop_minimum_and_destination_reserve_are_distinct():
    stop_profile = VehicleProfile(
        name="Test EV",
        usable_battery_kwh=100,
        driving_kwh_per_100_miles=100,
        max_dc_charge_kw=100,
        connector="CCS",
        minimum_arrival_percent=10,
    )
    destination_profile = VehicleProfile(
        name="Test EV",
        usable_battery_kwh=100,
        driving_kwh_per_100_miles=100,
        max_dc_charge_kw=100,
        connector="CCS",
        minimum_arrival_percent=15,
    )
    matrix = [
        [None, 90, 175],
        [None, None, 85],
        [None, None, None],
    ]
    result = select_fewest_stops(
        stop_profile, 100, "Start", ["Charger"], "Finish", matrix,
        destination_profile=destination_profile,
    )
    assert result["status"] == "conditional_energy_path"
    itinerary = result["itinerary"]
    assert itinerary["charging_stop_arrival_minimum_percent"] == 10
    assert itinerary["arrival_reserve_percent"] == 15
    assert itinerary["timeline"][1]["arrival_percent"] == 10
    assert itinerary["timeline"][2]["arrival_percent"] >= 15 - 1e-9


def test_destination_reserve_still_blocks_an_undercharged_final_leg():
    stop_profile = VehicleProfile(
        name="Test EV",
        usable_battery_kwh=100,
        driving_kwh_per_100_miles=100,
        max_dc_charge_kw=100,
        connector="CCS",
        minimum_arrival_percent=10,
    )
    destination_profile = VehicleProfile(
        name="Test EV",
        usable_battery_kwh=100,
        driving_kwh_per_100_miles=100,
        max_dc_charge_kw=100,
        connector="CCS",
        minimum_arrival_percent=15,
    )
    matrix = [
        [None, 90, 176],
        [None, None, 86],
        [None, None, None],
    ]
    result = select_fewest_stops(
        stop_profile, 100, "Start", ["Charger"], "Finish", matrix,
        destination_profile=destination_profile,
    )
    assert result["status"] == "no_feasible_path_in_supplied_graph"
