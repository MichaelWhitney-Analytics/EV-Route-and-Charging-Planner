import csv
from pathlib import Path
import pytest
import src.web_route_server as server

def test_catalog_reader_supplies_identity_not_charging_spec(tmp_path):
    path = tmp_path / "vehicles.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["vehicle_id", "year", "make", "model", "electricity_kwh_per_100_miles", "epa_range_miles"])
        writer.writeheader()
        writer.writerow({"vehicle_id": 17, "year": 2025, "make": "Test", "model": "EV", "electricity_kwh_per_100_miles": 29.5, "epa_range_miles": 250})
    choice = server.read_vehicle_choices(path)["vehicles"][0]
    assert choice["vehicle_id"] == 17
    assert choice["model"] == "EV"
    assert "connector" not in choice
    assert "usable_battery_kwh" not in choice

def test_missing_catalog_is_explicit(tmp_path):
    with pytest.raises(RuntimeError, match="unavailable"):
        server.read_vehicle_choices(tmp_path / "missing.csv")

def test_single_direct_route_action():
    text = Path("web/trip_planner_visual_prototype.html").read_text(encoding="utf-8-sig")
    assert 'fetch("/api/route"' in text
    assert 'fetch("/api/conditional-plan"' not in text
    assert 'Calculate trip distance' in text
    assert 'id="conditional-plan"' not in text
