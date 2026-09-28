import pandas as pd
import pytest

from src.ingestion.audit_vehicle_catalog import select_bevs


def test_selects_electricity_only_vehicle_with_missing_second_fuel():
    vehicles = pd.DataFrame({
        "id": [1],
        "fuelType1": ["Electricity"],
        "fuelType2": [None],
    })

    result = select_bevs(vehicles)

    assert result["id"].tolist() == [1]


def test_selects_electricity_only_vehicle_with_blank_second_fuel():
    vehicles = pd.DataFrame({
        "id": [1],
        "fuelType1": [" Electricity "],
        "fuelType2": ["  "],
    })

    result = select_bevs(vehicles)

    assert result["id"].tolist() == [1]


def test_rejects_vehicle_with_two_fuel_types():
    vehicles = pd.DataFrame({
        "id": [1],
        "fuelType1": ["Electricity"],
        "fuelType2": ["Gasoline"],
    })

    result = select_bevs(vehicles)

    assert result.empty


def test_rejects_gasoline_vehicle():
    vehicles = pd.DataFrame({
        "id": [1],
        "fuelType1": ["Gasoline"],
        "fuelType2": [None],
    })

    result = select_bevs(vehicles)

    assert result.empty


def test_reports_missing_required_column():
    vehicles = pd.DataFrame({
        "id": [1],
        "fuelType1": ["Electricity"],
    })

    with pytest.raises(ValueError, match="fuelType2"):
        select_bevs(vehicles)