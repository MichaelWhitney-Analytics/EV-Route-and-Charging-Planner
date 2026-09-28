from dataclasses import FrozenInstanceError

import pytest

from src.planning.vehicle_profile import VehicleProfile


def sample_profile(**changes) -> VehicleProfile:
    values = {
        "name": "Custom EV",
        "usable_battery_kwh": 75.0,
        "driving_kwh_per_100_miles": 30.0,
        "max_dc_charge_kw": 150.0,
        "connector": "CCS",
        "minimum_arrival_percent": 10.0,
    }
    values.update(changes)

    return VehicleProfile(**values)


def test_calculates_energy_per_mile_and_reserve():
    profile = sample_profile()

    assert profile.energy_per_mile_kwh == pytest.approx(0.3)
    assert profile.reserve_energy_kwh == pytest.approx(7.5)


def test_trims_name_and_connector():
    profile = sample_profile(
        name="  My EV  ",
        connector="  CCS  ",
    )

    assert profile.name == "My EV"
    assert profile.connector == "CCS"


@pytest.mark.parametrize(
    "field_name",
    [
        "usable_battery_kwh",
        "driving_kwh_per_100_miles",
        "max_dc_charge_kw",
    ],
)
def test_rejects_nonpositive_required_numbers(field_name):
    with pytest.raises(ValueError, match=field_name):
        sample_profile(**{field_name: 0})


@pytest.mark.parametrize(
    "reserve",
    [-1, 100],
)
def test_rejects_reserve_outside_allowed_range(reserve):
    with pytest.raises(ValueError, match="minimum_arrival_percent"):
        sample_profile(minimum_arrival_percent=reserve)


def test_allows_zero_percent_reserve():
    profile = sample_profile(minimum_arrival_percent=0)

    assert profile.reserve_energy_kwh == 0


@pytest.mark.parametrize(
    "field_name",
    [
        "name",
        "connector",
    ],
)
def test_rejects_blank_text(field_name):
    with pytest.raises(ValueError, match=field_name):
        sample_profile(**{field_name: "   "})


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), True],
)
def test_rejects_invalid_numeric_values(value):
    with pytest.raises(ValueError, match="usable_battery_kwh"):
        sample_profile(usable_battery_kwh=value)


def test_profile_cannot_be_modified_after_creation():
    profile = sample_profile()

    with pytest.raises(FrozenInstanceError):
        profile.usable_battery_kwh = 50.0