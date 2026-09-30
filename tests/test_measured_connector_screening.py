from src.planning.measured_candidate_graph import _site_connector_status
from src.planning.vehicle_profile import VehicleProfile


def profile(connector):
    return VehicleProfile(
        "Test EV", 75, 30, 150, connector,
        minimum_arrival_percent=10,
    )


def test_sourced_connector_matches_any_colocated_station():
    site = {"station_ids": [1, 2]}
    records = {
        1: {"connector_types_reported": ["TESLA"]},
        2: {"connector_types_reported": ["J1772COMBO"]},
    }
    assert _site_connector_status(profile("CCS"), site, records) == (
        "reported_connector_match"
    )


def test_explicit_mismatch_is_excluded_but_missing_data_is_not():
    site = {"station_ids": [1]}
    assert _site_connector_status(
        profile("CCS"), site,
        {1: {"connector_types_reported": ["CHADEMO"]}},
    ) == "reported_connector_mismatch"
    assert _site_connector_status(
        profile("CCS"), site,
        {1: {"connector_types_reported": None}},
    ) == "connector_not_reported"


def test_estimated_vehicle_never_claims_connector_match():
    site = {"station_ids": [1]}
    records = {1: {"connector_types_reported": ["J1772COMBO"]}}
    assert _site_connector_status(profile("Unverified"), site, records) == (
        "vehicle_connector_unverified"
    )
