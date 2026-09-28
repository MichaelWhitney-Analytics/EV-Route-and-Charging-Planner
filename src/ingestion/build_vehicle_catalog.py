from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.ingestion.audit_vehicle_catalog import select_bevs


RAW_PATH = Path("data/raw/fueleconomy_vehicles.csv")
OUTPUT_PATH = Path("data/processed/vehicle_catalog.csv")

SOURCE_COLUMNS = {
    "id",
    "year",
    "make",
    "model",
    "combE",
    "range",
}

OUTPUT_COLUMNS = [
    "vehicle_id",
    "year",
    "make",
    "model",
    "electricity_kwh_per_100_miles",
    "epa_range_miles",
]


def build_catalog(
    vehicles: pd.DataFrame,
    latest_model_year: int,
) -> pd.DataFrame:
    """Build a validated, app-sized catalog from raw vehicle records."""
    missing = SOURCE_COLUMNS - set(vehicles.columns)

    if missing:
        raise ValueError(f"Missing source columns: {sorted(missing)}")

    bev = select_bevs(vehicles)

    catalog = bev[
        ["id", "year", "make", "model", "combE", "range"]
    ].copy()

    for column in ("id", "year", "combE", "range"):
        catalog[column] = pd.to_numeric(
            catalog[column],
            errors="coerce",
        )

    for column in ("make", "model"):
        catalog[column] = (
            catalog[column]
            .astype("string")
            .str.strip()
        )

    valid = (
        catalog["id"].notna()
        & catalog["year"].notna()
        & catalog["year"].le(latest_model_year)
        & catalog["combE"].gt(0)
        & catalog["range"].gt(0)
        & catalog["make"].notna()
        & catalog["make"].ne("")
        & catalog["model"].notna()
        & catalog["model"].ne("")
    )

    catalog = catalog.loc[valid].copy()

    if catalog["id"].duplicated().any():
        duplicates = (
            catalog.loc[
                catalog["id"].duplicated(keep=False),
                "id",
            ]
            .tolist()
        )
        raise ValueError(f"Duplicate vehicle IDs: {duplicates}")

    catalog["id"] = catalog["id"].astype("int64")
    catalog["year"] = catalog["year"].astype("int64")

    catalog = catalog.rename(
        columns={
            "id": "vehicle_id",
            "combE": "electricity_kwh_per_100_miles",
            "range": "epa_range_miles",
        }
    )

    return (
        catalog[OUTPUT_COLUMNS]
        .sort_values(
            ["year", "make", "model", "vehicle_id"],
            ascending=[False, True, True, True],
        )
        .reset_index(drop=True)
    )


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"Raw vehicle file not found: {RAW_PATH}. "
            "Run audit_vehicle_catalog.py first."
        )

    vehicles = pd.read_csv(RAW_PATH, low_memory=False)
    current_year = datetime.now(timezone.utc).year

    catalog = build_catalog(
        vehicles,
        latest_model_year=current_year,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(OUTPUT_PATH, index=False)

    print(f"Read {len(vehicles):,} raw vehicle records.")
    print(
        f"Saved {len(catalog):,} eligible BEV records "
        f"through model year {current_year}."
    )
    print(f"Saved processed catalog to {OUTPUT_PATH}.")
    print(
        "Note: published electricity use and EPA range are "
        "reference values, not a verified trip-energy model."
    )


if __name__ == "__main__":
    main()