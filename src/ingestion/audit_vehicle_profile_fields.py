from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.ingestion.audit_vehicle_catalog import select_bevs


RAW_PATH = Path("data/raw/fueleconomy_vehicles.csv")
REPORT_PATH = Path("docs/vehicle_profile_field_audit.md")

PROFILE_TERMS = (
    "battery",
    "capacity",
    "charge",
    "connector",
    "plug",
    "range",
    "electric",
    "fuel",
)


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"Raw vehicle file not found: {RAW_PATH}. "
            "Run audit_vehicle_catalog.py first."
        )

    vehicles = pd.read_csv(RAW_PATH, low_memory=False)
    bev = select_bevs(vehicles)

    bev["year"] = pd.to_numeric(bev["year"], errors="coerce")
    current_year = datetime.now(timezone.utc).year

    current_or_earlier = bev["year"].le(current_year).sum()
    future_year = bev["year"].gt(current_year).sum()
    missing_year = bev["year"].isna().sum()

    candidate_columns = [
        column
        for column in vehicles.columns
        if any(term in column.lower() for term in PROFILE_TERMS)
    ]

    field_rows = []
    for column in candidate_columns:
        nonmissing = bev[column].notna().sum()
        field_rows.append(
            f"| `{column}` | {nonmissing:,} | "
            f"{nonmissing / len(bev):.1%} |"
        )

    field_table = "\n".join(field_rows)

    year_counts = (
        bev["year"]
        .value_counts()
        .sort_index(ascending=False)
        .head(10)
    )
    year_rows = "\n".join(
        f"| {int(year)} | {count:,} |"
        for year, count in year_counts.items()
    )

    report = f"""# Vehicle profile-field audit

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

Source: `{RAW_PATH.as_posix()}`

## Model-year coverage

The source catalog may include vehicles with model years later than the
calendar year in which this audit runs. A future model year does not by
itself establish whether a vehicle is available to a driver.

| Check | Records |
|---|---:|
| Records matching the electricity-only selection rule | {len(bev):,} |
| Model year {current_year} or earlier | {current_or_earlier:,} |
| Model year after {current_year} | {future_year:,} |
| Missing model year | {missing_year:,} |

### Most recent model years in the source

| Model year | Records |
|---:|---:|
{year_rows}

## Potential vehicle-profile fields

The names below matched terms such as battery, charge, connector, range,
electric, or fuel. This is a field-name search, **not** a claim that each
field is suitable for route planning.

| Source column | Nonmissing selected records | Coverage |
|---|---:|---:|
{field_table}

## Questions for review

- Is usable battery capacity present, or must we source it separately?
- Is connector compatibility present and specific to model year/variant?
- Is DC fast-charging capability or a charging curve present?
- Which fields describe driving energy versus wall-outlet energy?
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"Reviewed {len(bev):,} selected vehicle records.")
    print(f"Model year {current_year} or earlier: {current_or_earlier:,}.")
    print(f"Future model years: {future_year:,}.")
    print(f"Found {len(candidate_columns)} potentially relevant columns.")
    print(f"Saved report to {REPORT_PATH}.")


if __name__ == "__main__":
    main()