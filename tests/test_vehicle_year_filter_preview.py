from pathlib import Path


PAGE = Path("web/trip_planner_visual_prototype.html").read_text(
    encoding="utf-8-sig"
)


def test_year_and_make_model_controls_exist():
    assert 'id="vehicle-year"' in PAGE
    assert "Vehicle Year" in PAGE
    assert 'id="vehicle-mode"' in PAGE
    assert "Vehicle make / model" in PAGE


def test_year_options_and_filter_are_bounded():
    assert "year = 2026; year >= 2014; year--" in PAGE
    assert 'String(record.year) !== yearMode.value' in PAGE
    assert "mode.replaceChildren();" in PAGE
    assert "mode.disabled = !yearMode.value;" in PAGE


def test_year_change_invalidates_existing_charging_plan():
    assert 'yearMode.addEventListener("change", () => {' in PAGE
    assert "clearCharging();" in PAGE
    assert "showVehiclesForYear();" in PAGE
