$ErrorActionPreference = 'Stop'

if (-not (Test-Path 'src/planning/charging_stop.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run this script from the EV-Route-and-Charging-Planner project root with the existing .venv.'
}

$files = @{
    'src/planning/charging_time.py' = @'
from dataclasses import dataclass
from math import isfinite

from src.planning.charging_stop import ChargingStopResult
from src.planning.vehicle_profile import VehicleProfile


@dataclass(frozen=True)
class ChargingTimeEstimate:
    energy_to_add_kwh: float
    effective_power_kw: float
    estimated_minutes: float


def estimate_charging_time(
    profile: VehicleProfile,
    stop: ChargingStopResult,
    effective_power_kw: float,
) -> ChargingTimeEstimate:
    """Estimate energy-addition time using an explicitly supplied average power.

    Effective power must be a realistic user-supplied average across this stop,
    not advertised peak power. Excludes plug-in, queues, and other overhead.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    if not isinstance(stop, ChargingStopResult):
        raise TypeError("stop must be a ChargingStopResult")
    if (
        isinstance(effective_power_kw, bool)
        or not isinstance(effective_power_kw, (int, float))
        or not isfinite(effective_power_kw)
        or effective_power_kw <= 0
        or effective_power_kw > profile.max_dc_charge_kw
    ):
        raise ValueError(
            "effective_power_kw must be finite, positive, and no greater "
            "than the vehicle's max_dc_charge_kw"
        )
    if (
        not isfinite(stop.energy_to_add_kwh)
        or stop.energy_to_add_kwh < 0
        or stop.energy_to_add_kwh > profile.usable_battery_kwh + 1e-9
    ):
        raise ValueError("stop energy_to_add_kwh is invalid for this profile")

    return ChargingTimeEstimate(
        energy_to_add_kwh=stop.energy_to_add_kwh,
        effective_power_kw=effective_power_kw,
        estimated_minutes=stop.energy_to_add_kwh / effective_power_kw * 60,
    )
'@
    'tests/test_charging_time.py' = @'
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