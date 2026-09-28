import pytest

from src.planning.charging_stop import calculate_charging_stop
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile():
    return VehicleProfile(
        name="Test EV",
        usable_battery_kwh=75.0,
        driving_kwh_per_100_miles=30.0,
        max_dc_charge_kw=150.0,
        connector="CCS",
        minimum_arrival_percent=10.0,
    )


def test_calculates_charge_for_next_leg_and_reserve(profile):
    result = calculate_charging_stop(profile, arrival_percent=20, next_leg_miles=100)
    assert result.energy_to_add_kwh == pytest.approx(22.5)
    assert result.departure_percent == pytest.approx(50)
    assert result.charge_needed is True


def test_does_not_charge_if_arrival_energy_is_enough(profile):
    result = calculate_charging_stop(profile, arrival_percent=80, next_leg_miles=100)
    assert result.energy_to_add_kwh == pytest.approx(0)
    assert result.departure_percent == pytest.approx(80)
    assert result.charge_needed is False


def test_exact_full_battery_leg_is_allowed(profile):
    result = calculate_charging_stop(profile, arrival_percent=20, next_leg_miles=225)
    assert result.energy_to_add_kwh == pytest.approx(60)
    assert result.departure_percent == pytest.approx(100)


def test_rejects_leg_longer_than_full_battery_allows(profile):
    with pytest.raises(ValueError, match="cannot preserve arrival reserve"):
        calculate_charging_stop(profile, arrival_percent=20, next_leg_miles=226)


@pytest.mark.parametrize("value", [-1, 101, float("nan"), float("inf"), True])
def test_rejects_invalid_arrival_charge(profile, value):
    with pytest.raises(ValueError, match="arrival_percent"):
        calculate_charging_stop(profile, arrival_percent=value, next_leg_miles=100)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_rejects_invalid_leg_distance(profile, value):
    with pytest.raises(ValueError, match="next_leg_miles"):
        calculate_charging_stop(profile, arrival_percent=20, next_leg_miles=value)


def test_rejects_non_profile():
    with pytest.raises(TypeError, match="VehicleProfile"):
        calculate_charging_stop(None, arrival_percent=20, next_leg_miles=100)