from src.planning.planning_report import format_planning_report


def test_optional_site_is_not_presented_as_a_stop():
    summary = {
        "vehicle_name": "Illustrative EV", "start_percent": 80.0,
        "route_distance_miles": 14.2, "discovered_record_count": 28,
        "reported_connector_match_record_count": 27,
        "distinct_reported_address_count": 21,
        "road_detours_assessed_count": 1, "not_assessed_count": 20,
        "categories": {
            "no_charging_needed": [{
                "station": {"id": 189344, "name": "Example site"},
                "arrival_estimate": {"estimated_arrival_percent": 79.4704},
                "charge_for_next_leg": {"energy_to_add_kwh": 0.0},
            }],
            "charging_needed_if_usable": [],
            "unreachable_with_reserve": [],
            "next_leg_exceeds_full_battery_with_reserve": [],
        },
        "disclaimer": "Exploratory only. Trip completion is unverified.",
    }
    report = format_planning_report(summary)
    assert "Charging not required for this assessed route" in report
    assert "not a suggested stop" in report
    assert "0.0 kWh" not in report
    assert "Not checked: 20" in report
    assert "Trip completion is unverified" in report