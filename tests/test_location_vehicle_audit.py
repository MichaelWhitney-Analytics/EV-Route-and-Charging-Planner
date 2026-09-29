import json
from pathlib import Path
from src.ingestion.audit_vehicle_fields import audit_csv, audit_sources

JS = Path("web/place_autocomplete.js")

def test_audit_counts_values_without_inventing_charging_specs(tmp_path):
    raw = tmp_path / "raw.csv"
    catalog = tmp_path / "catalog.csv"
    raw.write_text("id,year,batteryCapacity,connector,other\n1,2024,,,x\n2,2023,75,CCS,y\n", encoding="utf-8")
    catalog.write_text("vehicle_id,make,model,electricity_kwh_per_100_miles,epa_range_miles\n1,Test,EV,30,250\n", encoding="utf-8")
    data = audit_sources(raw, catalog)
    assert data["raw"]["rows"] == 2
    assert data["raw"]["relevant_columns_nonempty_counts"]["batteryCapacity"] == 1
    assert data["raw"]["relevant_columns_nonempty_counts"]["connector"] == 1
    assert "not establish accuracy" in data["limitations"]
    assert "batteryCapacity" not in data["processed"]["all_columns"]

def test_place_labels_are_short_and_deduped_after_filtering():
    js = JS.read_text(encoding="utf-8-sig")
    assert 'p.country].filter(Boolean)' not in js
    assert 'function uniquePlaces(features)' in js
    assert '.filter(feature => feature.properties' in js
    assert 'uniquePlaces(valid).slice(0, 5)' in js
    assert 'url.searchParams.set("countrycode", "US")' in js
    assert 'selectedPlaces[id] = {label: labelFor(feature)' in js
    assert 'const city = p.city ||' in js
