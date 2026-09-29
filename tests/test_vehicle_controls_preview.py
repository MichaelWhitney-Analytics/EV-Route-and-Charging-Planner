from pathlib import Path

PAGE = Path("web/trip_planner_visual_prototype.html")

def test_model_dropdown_and_optional_battery_fields():
    text = PAGE.read_text(encoding="utf-8-sig")
    assert 'id="vehicle-mode"' in text
    assert 'fetch("/api/vehicles")' in text
    assert 'option.textContent = `${record.year} ${record.make} ${record.model}`' in text
    assert 'id="start-percent"' in text and 'id="reserve-percent"' in text
    for hidden_spec in ('battery-kwh', 'charge-kw', 'connector', 'consumption', 'vehicle-name'):
        assert f'id="{hidden_spec}"' not in text
    assert 'id="custom-vehicle-details"' not in text

def test_no_fabricated_energy_claim():
    text = PAGE.read_text(encoding="utf-8-sig")
    assert 'No battery or charging outcome is calculated' in text
    assert 'Add custom vehicle' not in text

