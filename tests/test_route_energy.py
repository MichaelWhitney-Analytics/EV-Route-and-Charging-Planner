import pytest

from src.planning.route_energy import estimate_route_energy
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile() -> VehicleProfile:
    return VehicleProfile(
        name="Test EV",
        usable_battery_kwh=75.0,
        driving_kwh_per_100_miles=30.0,
        max_dc_charge_kw=150.0,
        connector="CCS",
        minimum_arrival_percent=10.0,
    )


def test_reachable_route_preserves_reserve(profile):
    result = estimate_route_energy(
        profile,
        distance_miles=100,
        start_percent=80,
    )

    assert result.energy_needed_kwh == pytest.approx(30)
    assert result.energy_available_above_reserve_kwh == pytest.approx(
        52.5
    )
    assert result.estimated_arrival_percent == pytest.approx(40)
    assert result.shortfall_kwh == pytest.approx(0)
    assert result.reachable_without_charging is True


def test_route_exactly_at_reserve_is_reachable(profile):
    result = estimate_route_energy(
        profile,
        distance_miles=175,
        start_percent=80,
    )

    assert result.estimated_arrival_percent == pytest.approx(10)
    assert result.shortfall_kwh == pytest.approx(0)
    assert result.reachable_without_charging is True


def test_route_below_reserve_reports_shortfall(profile):
    result = estimate_route_energy(
        profile,
        distance_miles=200,
        start_percent=80,
    )

    assert result.energy_needed_kwh == pytest.approx(60)
    assert result.estimated_arrival_percent == pytest.approx(0)
    assert result.shortfall_kwh == pytest.approx(7.5)
    assert result.reachable_without_charging is False


def test_starting_below_reserve_is_not_marked_reachable(profile):
    result = estimate_route_energy(
        profile,
        distance_miles=0,
        start_percent=5,
    )

    assert result.energy_available_above_reserve_kwh == 0
    assert result.shortfall_kwh == pytest.approx(3.75)
    assert result.reachable_without_charging is False


def test_route_can_report_energy_beyond_battery(profile):
    result = estimate_route_energy(
        profile,
        distance_miles=300,
        start_percent=80,
    )

    assert result.estimated_arrival_percent == pytest.approx(-40)
    assert result.reachable_without_charging is False


@pytest.mark.parametrize(
    "distance",
    [-1, float("nan"), float("inf"), True],
)
def test_rejects_invalid_distance(profile, distance):
    with pytest.raises(ValueError, match="distance_miles"):
        estimate_route_energy(
            profile,
            distance_miles=distance,
            start_percent=80,
        )


@pytest.mark.parametrize(
    "start",
    [-1, 101, float("nan"), float("inf"), True],
)
def test_rejects_invalid_start_charge(profile, start):
    with pytest.raises(ValueError, match="start_percent"):
        estimate_route_energy(
            profile,
            distance_miles=100,
            start_percent=start,
        )


def test_rejects_non_profile_input():
    with pytest.raises(TypeError, match="VehicleProfile"):
        estimate_route_energy(
            profile=None,
            distance_miles=100,
            start_percent=80,
        )