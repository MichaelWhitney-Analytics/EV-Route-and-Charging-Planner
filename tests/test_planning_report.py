from src.planning.planning_report import format_planning_report


def base_summary():
    return {
        "vehicle_name": "Illustrative EV", "start_percent": 80.0,
        "route_distance_miles": 14.1545, "discovered_record_count": 28,
        "reported_connector_match_record_count": 27,
        "distinct_reported_address_count": 21,
        "road_detours_assessed_count": 1, "not_assessed_count": 20,
        "categories": {
            "no_charging_needed": [{
                "station": {"id": 189344, "name": "EMICH VW DCC 2", "address": "350 S Santa Fe Dr", "city": "Denver", "state": "CO"},
                "arrival_estimate": {"estimated_arrival_percent": 79.4704},
                "charge_for_next_leg": {"energy_to_add_kwh": 0.0},
            }],
            "charging_needed_if_usable": [],
            "unreachable_with_reserve": [],
            "next_leg_exceeds_full_battery_with_reserve": [],
        },
        "disclaimer": "Reported connector matches and charger availability are unverified.",
    }


def test_report_explains_optional_stop_and_unchecked_sites():
    report = format_planning_report(base_summary())
    assert "No charging needed" in report
    assert "Not checked: 20" in report
    assert "79.5%" in report
    assert "0.0 kWh" in report
    assert "not ranked" in report
    assert "availability are unverified" in report


def test_report_handles_empty_assessment():
    summary = base_summary()
    summary["categories"]["no_charging_needed"] = []
    report = format_planning_report(summary)
    assert "No candidate sites received an energy assessment" in report


def test_station_name_cannot_insert_fake_report_lines():
    summary = base_summary()
    summary["categories"]["no_charging_needed"][0]["station"]["name"] = "Site\nGUARANTEED CHARGE"
    report = format_planning_report(summary)
    assert "Site GUARANTEED CHARGE" in report
    assert "\nGUARANTEED CHARGE" not in report