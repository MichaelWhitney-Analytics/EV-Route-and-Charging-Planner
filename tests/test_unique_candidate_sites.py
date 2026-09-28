import pytest

import src.planning.candidate_assessment as module
from src.planning.station_sites import group_station_sites
from src.planning.vehicle_profile import VehicleProfile


def test_groups_same_address_case_insensitively():
    stations = [
        {"id": 1, "address": "350 S Santa Fe Dr", "city": "Denver", "state": "CO"},
        {"id": 2, "address": " 350 s santa fe dr ", "city": "DENVER", "state": "co"},
        {"id": 3, "address": "Elsewhere", "city": "Denver", "state": "CO"},
    ]
    sites = group_station_sites(stations)
    assert len(sites) == 2
    assert sites[0]["station_ids"] == [1, 2]
    assert sites[1]["station_ids"] == [3]


def test_missing_addresses_remain_separate():
    sites = group_station_sites([{"id": 1}, {"id": 2}])
    assert len(sites) == 2


def test_assessment_checks_distinct_sites(monkeypatch):
    stations = [
        {"id": 1, "address": "Same", "city": "Denver", "state": "CO", "latitude": 39.71, "longitude": -105.01, "connector_types_reported": ["J1772COMBO"]},
        {"id": 2, "address": "Same", "city": "Denver", "state": "CO", "latitude": 39.72, "longitude": -105.02, "connector_types_reported": ["J1772COMBO"]},
        {"id": 3, "address": "Different", "city": "Denver", "state": "CO", "latitude": 39.73, "longitude": -105.03, "connector_types_reported": ["J1772COMBO"]},
    ]
    monkeypatch.setattr(module, "find_route_station_candidates", lambda *a: {"route_distance_miles": 20, "candidate_stations": stations})
    calls = []

    def fake_detour(*coords):
        calls.append(coords)
        return {"additional_driving_miles": 1}

    monkeypatch.setattr(module, "compare_station_detour", fake_detour)
    result = module.assess_candidates(VehicleProfile("Test", 75, 30, 150, "CCS"), 39.7, -105, 39.8, -104.9)
    assert result["distinct_reported_address_count"] == 2
    assert len(calls) == 2
    assert result["assessments"][0]["co_located_station_ids"] == [1, 2]
    assert result["assessments"][1]["station"]["id"] == 3


def test_rejects_invalid_collection():
    with pytest.raises(ValueError, match="stations must be a list"):
        group_station_sites(None)