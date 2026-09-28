import pytest

from src.planning.connector_screening import screen_station_connectors
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile():
    return VehicleProfile(
        name="Test EV", usable_battery_kwh=75.0,
        driving_kwh_per_100_miles=30.0, max_dc_charge_kw=150.0,
        connector="CCS", minimum_arrival_percent=10.0,
    )


def test_matches_reported_ccs_only(profile):
    stations = [
        {"id": 1, "connector_types_reported": ["J1772COMBO", "TESLA"]},
        {"id": 2, "connector_types_reported": ["TESLA"]},
        {"id": 3, "connector_types_reported": ["J1772"]},
        {"id": 4, "connector_types_reported": None},
    ]
    result = screen_station_connectors(profile, stations)
    assert [s["id"] for s in result["possible_matches"]] == [1]
    assert [s["id"] for s in result["not_matched_or_unknown"]] == [2, 3, 4]
    assert "preliminary screen" in result["disclaimer"]


def test_nacs_label_maps_to_reported_tesla():
    vehicle = VehicleProfile("Test", 75, 30, 150, "NACS")
    result = screen_station_connectors(vehicle, [
        {"id": 1, "connector_types_reported": ["TESLA"]}
    ])
    assert result["required_reported_label"] == "TESLA"
    assert result["possible_matches"][0]["id"] == 1


def test_unknown_connector_fails_closed():
    vehicle = VehicleProfile("Test", 75, 30, 150, "unverified")
    with pytest.raises(ValueError, match="Unknown connector"):
        screen_station_connectors(vehicle, [])


def test_rejects_invalid_station_collection(profile):
    with pytest.raises(ValueError, match="stations must be a list"):
        screen_station_connectors(profile, None)


def test_rejects_invalid_station_record(profile):
    with pytest.raises(ValueError, match="station must be an object"):
        screen_station_connectors(profile, [None])