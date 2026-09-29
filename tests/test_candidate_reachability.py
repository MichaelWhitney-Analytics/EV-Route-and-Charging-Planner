import pytest

from src.planning.candidate_reachability import assess_candidate_reachability
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile():
    return VehicleProfile("Test EV", 75, 30, 150, "CCS", 10)


def assessed(first, second):
    return {"assessments": [{
        "station": {"id": 123, "name": "Example"},
        "detour": {
            "start_to_station_distance_miles": first,
            "station_to_end_distance_miles": second,
        },
    }]}


def test_reachable_station_reports_charge_needed(profile):
    result = assess_candidate_reachability(profile, 80, assessed(100, 100))
    candidate = result["candidates"][0]
    assert candidate["station_reachable_with_reserve"] is True
    assert candidate["arrival_estimate"]["estimated_arrival_percent"] == pytest.approx(40)
    assert candidate["charge_for_next_leg"]["energy_to_add_kwh"] == pytest.approx(7.5)
    assert candidate["next_leg_possible_from_full"] is True


def test_unreachable_station_does_not_assume_a_charge(profile):
    result = assess_candidate_reachability(profile, 80, assessed(200, 10))
    candidate = result["candidates"][0]
    assert candidate["station_reachable_with_reserve"] is False
    assert candidate["charge_for_next_leg"] is None
    assert candidate["next_leg_possible_from_full"] is None


def test_leg_too_long_even_with_full_battery(profile):
    result = assess_candidate_reachability(profile, 80, assessed(50, 226))
    candidate = result["candidates"][0]
    assert candidate["station_reachable_with_reserve"] is True
    assert candidate["next_leg_possible_from_full"] is False
    assert candidate["charge_for_next_leg"] is None


def test_empty_assessment_is_valid(profile):
    result = assess_candidate_reachability(profile, 80, {"assessments": []})
    assert result["candidates"] == []


@pytest.mark.parametrize("value", [-1, 101, True, float("nan")])
def test_rejects_invalid_start_percent(profile, value):
    with pytest.raises(ValueError, match="start_percent"):
        assess_candidate_reachability(profile, value, assessed(100, 100))


def test_rejects_bad_distance(profile):
    with pytest.raises(ValueError, match="start_to_station_distance_miles"):
        assess_candidate_reachability(profile, 80, assessed(-1, 100))