import pytest

import src.planning.candidate_assessment as module
from src.planning.candidate_assessment import assess_candidates
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile():
    return VehicleProfile("Test", 75, 30, 150, "CCS")


def test_caps_detour_calls_and_screens_labels(monkeypatch, profile):
    stations = [
        {"id": 1, "latitude": 39.71, "longitude": -105.01, "connector_types_reported": ["J1772COMBO"]},
        {"id": 2, "latitude": 39.72, "longitude": -105.02, "connector_types_reported": ["TESLA"]},
        {"id": 3, "latitude": 39.73, "longitude": -105.03, "connector_types_reported": ["J1772COMBO"]},
        {"id": 4, "latitude": 39.74, "longitude": -105.04, "connector_types_reported": ["J1772COMBO"]},
    ]
    monkeypatch.setattr(module, "find_route_station_candidates", lambda *a: {
        "route_distance_miles": 20, "candidate_stations": stations,
    })
    calls = []

    def fake_detour(*coords):
        calls.append(coords)
        return {"additional_driving_miles": 2}

    monkeypatch.setattr(module, "compare_station_detour", fake_detour)
    result = assess_candidates(profile, 39.7, -105, 39.8, -104.9)
    assert result["discovered_count"] == 4
    assert result["reported_connector_match_count"] == 3
    assert [a["station"]["id"] for a in result["assessments"]] == [1, 3]
    assert len(calls) == 2
    assert "Not ranked" in result["disclaimer"]


def test_empty_candidates_make_no_detour_requests(monkeypatch, profile):
    monkeypatch.setattr(module, "find_route_station_candidates", lambda *a: {
        "route_distance_miles": 10, "candidate_stations": [],
    })
    result = assess_candidates(profile, 39.7, -105, 39.8, -104.9)
    assert result["assessments"] == []


@pytest.mark.parametrize("cap", [0, 4, True, 1.5])
def test_rejects_invalid_cap_before_network(profile, cap):
    with pytest.raises(ValueError, match="max_detour_checks"):
        assess_candidates(profile, 39.7, -105, 39.8, -104.9, max_detour_checks=cap)


def test_rejects_invalid_coordinates_before_network(profile):
    with pytest.raises(ValueError, match="start_lat"):
        assess_candidates(profile, 91, -105, 39.8, -104.9)