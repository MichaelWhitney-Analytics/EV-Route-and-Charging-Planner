import json
from pathlib import Path
import pytest
from src.planning.verified_vehicle_profiles import (coverage, load_catalog, load_profiles, validate_record)

CATALOG = {17: (2025, "Example", "EV Long Range")}

def record(**changes):
    item = {"vehicle_id": 17, "year": 2025, "make": "Example", "model": "EV Long Range",
            "usable_battery_kwh": 70.0, "max_dc_charge_kw": 120.0, "connector": "CCS",
            "source_urls": {"usable_battery_kwh": "https://example.org/battery", "max_dc_charge_kw": "https://example.org/dc-charging", "connector": "https://example.org/connector"}, "verified_on": "2026-09-01"}
    item.update(changes)
    return item

def test_matches_exact_catalog_identity_and_records_provenance():
    assert validate_record(record(), CATALOG)["vehicle_id"] == 17

@pytest.mark.parametrize("change", [
    {"vehicle_id": True}, {"vehicle_id": 18}, {"year": 2024},
    {"model": "EV"}, {"connector": "unknown"},
    {"usable_battery_kwh": True}, {"usable_battery_kwh": 0},
    {"max_dc_charge_kw": float("nan")}, {"source_urls": {"usable_battery_kwh": "http://example.org/spec", "max_dc_charge_kw": "https://example.org/dc-charging", "connector": "https://example.org/connector"}},
    {"verified_on": "2030-01-01"},
])
def test_rejects_unmatched_unsourced_or_invalid_profile(change):
    with pytest.raises(ValueError):
        validate_record(record(**change), CATALOG)

def test_empty_registry_keeps_vehicle_direct_route_only(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("[]", encoding="utf-8")
    result = load_profiles(path, CATALOG)
    assert result == {}
    assert coverage(CATALOG, result)["direct_route_only_count"] == 1

def test_rejects_duplicate_profile_ids(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps([record(), record()]), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        load_profiles(path, CATALOG)

def test_current_catalog_and_empty_registry_have_explicit_coverage():
    root = Path(__file__).resolve().parents[1]
    catalog = load_catalog(root / "data/processed/vehicle_catalog.csv")
    profiles = load_profiles(root / "data/processed/verified_vehicle_profiles.json", catalog)
    assert coverage(catalog, profiles)["catalog_vehicle_count"] >= 1
    assert coverage(catalog, profiles)["source_backed_profile_count"] == 0


@pytest.mark.parametrize("bad_sources", [
    {},
    {"usable_battery_kwh": "https://example.org/battery"},
    {
        "usable_battery_kwh": "https://example.org/battery",
        "max_dc_charge_kw": "https://example.org/dc-charging",
        "connector": "http://example.org/connector",
    },
    {
        "usable_battery_kwh": "https://example.org/battery",
        "max_dc_charge_kw": "https://example.org/dc-charging",
        "connector": "https://example.org/connector",
        "extra": "https://example.org/extra",
    },
    None,
])
def test_rejects_incomplete_field_sources(bad_sources):
    with pytest.raises(ValueError):
        validate_record(record(source_urls=bad_sources), CATALOG)
