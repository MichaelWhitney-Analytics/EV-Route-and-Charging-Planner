$ErrorActionPreference = 'Stop'

if (-not (Test-Path 'src/planning/vehicle_profile.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run this script from the EV-Route-and-Charging-Planner project root, with the existing .venv.'
}

$files = @{
    'src/planning/charging_stop.py' = @'
from dataclasses import dataclass
from math import isfinite

from src.planning.vehicle_profile import VehicleProfile


@dataclass(frozen=True)
class ChargingStopResult:
    arrival_percent: float
    next_leg_miles: float
    departure_percent: float
    energy_to_add_kwh: float
    charge_needed: bool


def calculate_charging_stop(
    profile: VehicleProfile,
    arrival_percent: float,
    next_leg_miles: float,
) -> ChargingStopResult:
    """Find minimum charge needed for one next leg plus arrival reserve.

    This is an energy estimate, not a charge-time or charger-availability estimate.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")

    for name, value, minimum, maximum in (
        ("arrival_percent", arrival_percent, 0, 100),
        ("next_leg_miles", next_leg_miles, 0, None),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            or value < minimum
            or (maximum is not None and value > maximum)
        ):
            bound = "0 to 100" if maximum is not None else "0 or greater"
            raise ValueError(f"{name} must be a finite number from {bound}")

    energy_for_leg = next_leg_miles * profile.energy_per_mile_kwh
    required_departure_kwh = energy_for_leg + profile.reserve_energy_kwh
    battery_kwh = profile.usable_battery_kwh

    if required_departure_kwh > battery_kwh + 1e-9:
        raise ValueError(
            "next leg cannot preserve arrival reserve even from 100% charge"
        )

    arrival_kwh = battery_kwh * arrival_percent / 100
    energy_to_add_kwh = max(0.0, required_departure_kwh - arrival_kwh)
    departure_kwh = arrival_kwh + energy_to_add_kwh

    return ChargingStopResult(
        arrival_percent=arrival_percent,
        next_leg_miles=next_leg_miles,
        departure_percent=min(100.0, departure_kwh / battery_kwh * 100),
        energy_to_add_kwh=energy_to_add_kwh,
        charge_needed=energy_to_add_kwh > 1e-9,
    )
'@
    'tests/test_charging_stop.py' = @'
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
'@
}

foreach ($path in $files.Keys) {
    if (Test-Path $path) {
        throw "Refusing to overwrite existing file: $path"
    }
}

foreach ($path in $files.Keys) {
    $parent = Split-Path $path -Parent
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [System.IO.File]::WriteAllText(
        (Join-Path (Get-Location).Path $path),
        $files[$path],
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Host "Created $path"
}

& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) {
    throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet."
}
Write-Host 'All tests passed. Review the two new files before committing.'