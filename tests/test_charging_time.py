from dataclasses import replace

import pytest

from src.planning.charging_stop import calculate_charging_stop
from src.planning.charging_time import estimate_charging_time
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


def test_estimates_time_using_supplied_effective_power(profile):
    stop = calculate_charging_stop(profile, arrival_percent=20, next_leg_miles=100)
    result = estimate_charging_time(profile, stop, effective_power_kw=75)
    assert result.energy_to_add_kwh == pytest.approx(22.5)
    assert result.estimated_minutes == pytest.approx(18)


def test_no_charge_means_zero_minutes(profile):
    stop = calculate_charging_stop(profile, arrival_percent=80, next_leg_miles=100)
    result = estimate_charging_time(profile, stop, effective_power_kw=75)
    assert result.estimated_minutes == 0


def test_accepts_power_at_vehicle_maximum(profile):
    stop = calculate_charging_stop(profile, arrival_percent=20, next_leg_miles=100)
    result = estimate_charging_time(profile, stop, effective_power_kw=150)
    assert result.estimated_minutes == pytest.approx(9)


@pytest.mark.parametrize("power", [0, -1, 151, float("nan"), float("inf"), True])
def test_rejects_invalid_effective_power(profile, power):
    stop = calculate_charging_stop(profile, arrival_percent=20, next_leg_miles=100)
    with pytest.raises(ValueError, match="effective_power_kw"):
        estimate_charging_time(profile, stop, effective_power_kw=power)


def test_rejects_invalid_profile():
    with pytest.raises(TypeError, match="VehicleProfile"):
        estimate_charging_time(None, None, effective_power_kw=75)


def test_rejects_invalid_stop(profile):
    with pytest.raises(TypeError, match="ChargingStopResult"):
        estimate_charging_time(profile, None, effective_power_kw=75)


def test_rejects_stop_exceeding_battery(profile):
    stop = calculate_charging_stop(profile, arrival_percent=20, next_leg_miles=100)
    invalid_stop = replace(stop, energy_to_add_kwh=100)
    with pytest.raises(ValueError, match="energy_to_add_kwh"):
        estimate_charging_time(profile, invalid_stop, effective_power_kw=75)