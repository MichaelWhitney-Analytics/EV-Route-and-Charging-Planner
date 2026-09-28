from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class VehicleProfile:
    """User-provided inputs for a preliminary EV route estimate.

    These values are not inferred from the FuelEconomy.gov catalog.
    """

    name: str
    usable_battery_kwh: float
    driving_kwh_per_100_miles: float
    max_dc_charge_kw: float
    connector: str
    minimum_arrival_percent: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a nonempty string")

        if not isinstance(self.connector, str) or not self.connector.strip():
            raise ValueError("connector must be a nonempty string")

        numeric_fields = {
            "usable_battery_kwh": self.usable_battery_kwh,
            "driving_kwh_per_100_miles": self.driving_kwh_per_100_miles,
            "max_dc_charge_kw": self.max_dc_charge_kw,
            "minimum_arrival_percent": self.minimum_arrival_percent,
        }

        for field_name, value in numeric_fields.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(
                    f"{field_name} must be a finite number"
                )

        if self.usable_battery_kwh <= 0:
            raise ValueError(
                "usable_battery_kwh must be greater than zero"
            )

        if self.driving_kwh_per_100_miles <= 0:
            raise ValueError(
                "driving_kwh_per_100_miles must be greater than zero"
            )

        if self.max_dc_charge_kw <= 0:
            raise ValueError(
                "max_dc_charge_kw must be greater than zero"
            )

        if not 0 <= self.minimum_arrival_percent < 100:
            raise ValueError(
                "minimum_arrival_percent must be at least 0 "
                "and less than 100"
            )

        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(
            self,
            "connector",
            self.connector.strip(),
        )

    @property
    def energy_per_mile_kwh(self) -> float:
        """Driving-energy estimate for one mile."""
        return self.driving_kwh_per_100_miles / 100

    @property
    def reserve_energy_kwh(self) -> float:
        """Usable battery energy held in reserve on arrival."""
        return (
            self.usable_battery_kwh
            * self.minimum_arrival_percent
            / 100
        )