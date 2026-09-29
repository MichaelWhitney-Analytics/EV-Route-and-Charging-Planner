import pytest

import src.planning.planning_summary as module
from src.planning.vehicle_profile import VehicleProfile


def test_summary_categories_and_unassessed_count(monkeypatch):
    profile = VehicleProfile("Example", 75, 30, 150, "CCS", 10)
    calls = []

    def assessment(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "route_distance_miles": 40,
            "discovered_count": 8,
            "reported_connector_match_count": 5,
            "distinct_reported_address_count": 4,
            "assessments": [{"station": {"id": i}, "detour": {}} for i in (1, 2, 3)],
        }

    def energy(*args):
        assert args[0] is profile and args[1] == 80
        return {"candidates": [
            {"station": {"id": 1}, "station_reachable_with_reserve": True, "next_leg_possible_from_full": True},
            {"station": {"id": 2}, "station_reachable_with_reserve": False, "next_leg_possible_from_full": None},
            {"station": {"id": 3}, "station_reachable_with_reserve": True, "next_leg_possible_from_full": False},
        ]}

    monkeypatch.setattr(module, "assess_candidates", assessment)
    monkeypatch.setattr(module, "assess_candidate_reachability", energy)
    result = module.plan_candidate_summary(profile, 80, 39.7, -105, 39.8, -104.9, max_detour_checks=3)
    assert len(calls) == 1
    assert calls[0][1] == {"max_detour_checks": 3}
    assert result["not_assessed_count"] == 1
    assert result["road_detours_assessed_count"] == 3
    assert result["categories"]["energy_feasible_if_charging_available"][0]["station"]["id"] == 1
    assert result["categories"]["unreachable_with_reserve"][0]["station"]["id"] == 2
    assert result["categories"]["next_leg_exceeds_full_battery_with_reserve"][0]["station"]["id"] == 3


def test_empty_candidates(monkeypatch):
    monkeypatch.setattr(module, "assess_candidates", lambda *a, **k: {
        "route_distance_miles": 10, "discovered_count": 0,
        "reported_connector_match_count": 0,
        "distinct_reported_address_count": 0, "assessments": [],
    })
    monkeypatch.setattr(module, "assess_candidate_reachability", lambda *a: {"candidates": []})
    result = module.plan_candidate_summary(
        VehicleProfile("Example", 75, 30, 150, "CCS"), 80, 39.7, -105, 39.8, -104.9
    )
    assert result["not_assessed_count"] == 0
    assert all(not entries for entries in result["categories"].values())