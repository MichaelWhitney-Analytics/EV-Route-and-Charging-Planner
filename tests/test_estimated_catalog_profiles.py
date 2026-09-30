import pytest

from src import web_route_server as server


def test_every_displayed_car_has_an_energy_profile():
    choices = server.read_vehicle_choices()["vehicles"]
    assert len(choices) == 1437
    for row in choices:
        profile = server.profile_for_catalog_id(row["vehicle_id"])
        assert profile.usable_battery_kwh > 0
        assert profile.driving_kwh_per_100_miles > 0


def test_estimate_uses_this_cars_epa_range_not_the_audis_battery():
    rows = server.read_vehicle_choices()["vehicles"]
    other = next(row for row in rows if row["vehicle_id"] == 50182)
    profile = server.profile_for_catalog_id(other["vehicle_id"], 50)
    assert profile.connector == "Unverified"
    assert profile.minimum_arrival_percent == 50
    assert profile.usable_battery_kwh == pytest.approx(
        other["epa_range_miles"]
        * other["electricity_kwh_per_100_miles"] * 0.85 / 100
    )
    assert (
        profile.usable_battery_kwh / profile.energy_per_mile_kwh
    ) == pytest.approx(other["epa_range_miles"])


def test_sourced_audi_spec_is_preserved():
    profile = server.profile_for_catalog_id(49612)
    assert profile.usable_battery_kwh == 77
    assert profile.max_dc_charge_kw == 175
    assert profile.connector == "CCS"
