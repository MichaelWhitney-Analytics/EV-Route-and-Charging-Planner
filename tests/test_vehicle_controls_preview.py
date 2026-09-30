from pathlib import Path

PAGE = Path("web/trip_planner_visual_prototype.html")


def test_model_dropdown_and_optional_battery_fields():
    text = PAGE.read_text(encoding="utf-8-sig")

    assert 'id="vehicle-mode"' in text
    assert 'fetch("/api/vehicles")' in text
    assert "`${record.make} ${record.model}`" in text
    assert 'id="start-percent"' in text
    assert 'id="reserve-percent"' in text

    for hidden_spec in (
        "battery-kwh",
        "charge-kw",
        "connector",
        "consumption",
        "vehicle-name",
    ):
        assert f'id="{hidden_spec}"' not in text

    assert 'id="custom-vehicle-details"' not in text


def test_unsourced_vehicle_has_no_fabricated_charging_claim():
    text = PAGE.read_text(encoding="utf-8-sig")

    assert "eligibleIds.has(mode.value)" in text
    assert "if (!eligibleIds.has(mode.value))" in text
    assert "Charging stops are not calculated for this route yet." in text
    assert "Add custom vehicle" not in text