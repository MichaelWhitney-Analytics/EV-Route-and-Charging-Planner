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