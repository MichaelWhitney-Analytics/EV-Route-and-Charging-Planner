import pytest

from src.planning.route_itinerary import build_itinerary
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile():
    return VehicleProfile(
        name="Test EV", usable_battery_kwh=75.0,
        driving_kwh_per_100_miles=30.0, max_dc_charge_kw=150.0,
        connector="CCS", minimum_arrival_percent=10.0,
    )


def test_single_leg_needs_no_stop(profile):
    result = build_itinerary(profile, (100,), 80, ())
    assert len(result.legs) == 1
    assert result.stops == ()
    assert result.final_percent == pytest.approx(40)
    assert result.total_charge_kwh == 0


def test_two_legs_carry_charge_forward(profile):
    result = build_itinerary(profile, (100, 100), 80, (75,))
    assert len(result.legs) == 2
    assert result.legs[0].estimated_arrival_percent == pytest.approx(40)
    assert result.stops[0].charge.departure_percent == pytest.approx(50)
    assert result.stops[0].charge.energy_to_add_kwh == pytest.approx(7.5)
    assert result.total_estimated_charging_minutes == pytest.approx(6)
    assert result.final_percent == pytest.approx(10)
    assert result.total_distance_miles == 200


def test_three_legs_carry_state_across_two_stops(profile):
    result = build_itinerary(profile, (100, 100, 50), 80, (75, 75))
    assert len(result.stops) == 2
    assert result.stops[0].after_leg_number == 1
    assert result.stops[1].after_leg_number == 2
    assert result.total_charge_kwh == pytest.approx(22.5)
    assert result.total_estimated_charging_minutes == pytest.approx(18)
    assert result.final_percent == pytest.approx(10)


def test_stop_with_sufficient_charge_adds_nothing(profile):
    result = build_itinerary(profile, (50, 50), 100, (75,))
    assert result.stops[0].charge.charge_needed is False
    assert result.total_estimated_charging_minutes == 0


def test_rejects_unreachable_first_leg(profile):
    with pytest.raises(ValueError, match="leg 1"):
        build_itinerary(profile, (230,), 100, ())


def test_rejects_unreachable_next_leg_even_from_full(profile):
    with pytest.raises(ValueError, match="next leg cannot preserve"):
        build_itinerary(profile, (50, 226), 100, (75,))


@pytest.mark.parametrize("legs, powers", [((), ()), ((50, 50), ()), ((50,), (75,))])
def test_rejects_invalid_leg_stop_structure(profile, legs, powers):
    with pytest.raises(ValueError):
        build_itinerary(profile, legs, 100, powers)


def test_rejects_invalid_stop_power(profile):
    with pytest.raises(ValueError, match="effective_power_kw"):
        build_itinerary(profile, (50, 50), 100, (151,))


def test_rejects_invalid_start_percent(profile):
    with pytest.raises(ValueError, match="start_percent"):
        build_itinerary(profile, (50,), float("nan"), ())