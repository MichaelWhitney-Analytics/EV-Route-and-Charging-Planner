import pandas as pd
import pytest

from src.ingestion.build_vehicle_catalog import build_catalog


def sample_vehicles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [10, 20, 30, 40],
            "year": [2025, 2027, 2025, 2025],
            "make": [" Example ", "Future", "Hybrid", "Invalid"],
            "model": [" BEV ", "BEV", "PHEV", "No Range"],
            "fuelType1": [
                "Electricity",
                "Electricity",
                "Electricity",
                "Electricity",
            ],
            "fuelType2": [None, None, "Gasoline", None],
            "combE": [30.0, 28.0, 35.0, 32.0],
            "range": [250, 280, 220, 0],
        }
    )


def test_builds_clean_catalog_and_excludes_ineligible_records():
    catalog = build_catalog(
        sample_vehicles(),
        latest_model_year=2026,
    )

    assert catalog.to_dict("records") == [
        {
            "vehicle_id": 10,
            "year": 2025,
            "make": "Example",
            "model": "BEV",
            "electricity_kwh_per_100_miles": 30.0,
            "epa_range_miles": 250,
        }
    ]


def test_future_model_can_be_included_when_year_allows_it():
    catalog = build_catalog(
        sample_vehicles(),
        latest_model_year=2027,
    )

    assert catalog["vehicle_id"].tolist() == [20, 10]


def test_excludes_missing_or_nonpositive_efficiency():
    vehicles = sample_vehicles().iloc[[0, 1]].copy()
    vehicles["year"] = 2025
    vehicles["combE"] = [None, 0]

    catalog = build_catalog(
        vehicles,
        latest_model_year=2026,
    )

    assert catalog.empty


def test_rejects_duplicate_vehicle_ids():
    vehicles = pd.concat(
        [
            sample_vehicles().iloc[[0]],
            sample_vehicles().iloc[[0]],
        ],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="Duplicate vehicle IDs"):
        build_catalog(
            vehicles,
            latest_model_year=2026,
        )


def test_reports_missing_source_column():
    vehicles = sample_vehicles().drop(columns="range")

    with pytest.raises(ValueError, match="range"):
        build_catalog(
            vehicles,
            latest_model_year=2026,
        )