from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import requests


SOURCE_URL = "https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip"
RAW_OUTPUT_PATH = Path("data/raw/fueleconomy_vehicles.csv")
REPORT_OUTPUT_PATH = Path("docs/vehicle_data_audit.md")

REQUIRED_COLUMNS = {
    "id",
    "year",
    "make",
    "model",
    "fuelType1",
    "fuelType2",
    "combE",
}


def select_bevs(vehicles: pd.DataFrame) -> pd.DataFrame:
    """Select electricity-only records using the audited fuel-type fields."""
    required = {"fuelType1", "fuelType2"}
    missing = required - set(vehicles.columns)

    if missing:
        raise ValueError(f"Missing fuel-type columns: {sorted(missing)}")

    primary_fuel = (
        vehicles["fuelType1"]
        .astype("string")
        .fillna("")
        .str.strip()
    )
    secondary_fuel = (
        vehicles["fuelType2"]
        .astype("string")
        .fillna("")
        .str.strip()
    )

    return vehicles.loc[
        primary_fuel.eq("Electricity") & secondary_fuel.eq("")
    ].copy()


def main() -> None:
    print("Downloading FuelEconomy.gov vehicle data...")

    response = requests.get(SOURCE_URL, timeout=120)
    response.raise_for_status()

    with ZipFile(BytesIO(response.content)) as archive:
        csv_files = [
            name
            for name in archive.namelist()
            if name.lower().endswith("vehicles.csv")
        ]

        if len(csv_files) != 1:
            raise ValueError(
                f"Expected one vehicles.csv in the ZIP; found: {csv_files}"
            )

        with archive.open(csv_files[0]) as csv_file:
            vehicles = pd.read_csv(csv_file, low_memory=False)

    missing_columns = REQUIRED_COLUMNS - set(vehicles.columns)
    if missing_columns:
        raise ValueError(
            f"Missing expected columns: {sorted(missing_columns)}"
        )

    RAW_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    vehicles.to_csv(RAW_OUTPUT_PATH, index=False)

    bev = select_bevs(vehicles)

    bev["year"] = pd.to_numeric(bev["year"], errors="coerce")
    bev["combE"] = pd.to_numeric(bev["combE"], errors="coerce")

    total_bev_records = len(bev)
    distinct_vehicle_ids = bev["id"].nunique()
    usable_efficiency = bev["combE"].gt(0).sum()
    missing_efficiency = total_bev_records - usable_efficiency
    missing_vehicle_ids = bev["id"].isna().sum()
    duplicate_vehicle_ids = bev["id"].duplicated().sum()

    first_year = int(bev["year"].min())
    last_year = int(bev["year"].max())

    examples = (
        bev[["year", "make", "model", "combE"]]
        .sort_values(
            ["year", "make", "model"],
            ascending=[False, True, True],
        )
        .head(10)
        .fillna("missing")
    )

    example_rows = "\n".join(
        f"| {row.year} | {row.make} | {row.model} | {row.combE} |"
        for row in examples.itertuples(index=False)
    )

    report = f"""# BEV vehicle-data audit

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

## Source

- Dataset: [FuelEconomy.gov vehicle data]({SOURCE_URL})
- Local raw snapshot: `{RAW_OUTPUT_PATH.as_posix()}`

## BEV selection rule

A record is included when:

- `fuelType1 = Electricity`
- `fuelType2` is blank or missing

This is an initial electricity-only classification rule. It should be
validated against source records before being treated as a complete
classification of every BEV and plug-in hybrid.

## Coverage

| Check | Result |
|---|---:|
| Total vehicle records downloaded | {len(vehicles):,} |
| Records matching BEV selection rule | {total_bev_records:,} |
| Distinct vehicle IDs | {distinct_vehicle_ids:,} |
| Model years represented | {first_year}–{last_year} |
| Selected records with positive `combE` | {usable_efficiency:,} |
| Selected records without positive `combE` | {missing_efficiency:,} |
| Missing vehicle IDs | {missing_vehicle_ids:,} |
| Duplicate vehicle IDs | {duplicate_vehicle_ids:,} |

## Sample selected records

| Year | Make | Model | Combined electricity use (kWh/100 mi) |
|---:|---|---|---:|
{example_rows}

## Interpretation and limitations

This audit establishes a reproducible starting catalog. It does not make
every record trip-ready. The source may include future model-year vehicles,
and the planner still needs usable battery capacity, connector
compatibility, DC fast-charging behavior, and station data.

`combE` is a published electricity-use measure and can include charging
losses. The planner must document how it uses this value rather than
silently treating it as direct battery energy consumption.
"""

    REPORT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT_PATH.write_text(report, encoding="utf-8")

    print(f"Downloaded {len(vehicles):,} vehicle records.")
    print(f"Found {total_bev_records:,} records matching the BEV rule.")
    print(f"Selected records with positive combE: {usable_efficiency:,}.")
    print(f"Saved raw data to {RAW_OUTPUT_PATH}.")
    print(f"Saved audit report to {REPORT_OUTPUT_PATH}.")


if __name__ == "__main__":
    main()