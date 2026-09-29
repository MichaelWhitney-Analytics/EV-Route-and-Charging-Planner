from pathlib import Path


PAGE = Path("web/trip_planner_visual_prototype.html")


def test_default_vehicle_form_shows_only_three_choices():
    page = PAGE.read_text(encoding="utf-8")
    assert 'id="vehicle-mode"' in page
    assert 'id="start-percent"' in page
    assert 'id="reserve-percent"' in page
    assert 'id="custom-vehicle-details" hidden' in page
    assert '<option value="" selected>Choose a vehicle</option>' in page


def test_advanced_fields_only_in_custom_path_without_fabricated_catalog():
    page = PAGE.read_text(encoding="utf-8")
    for control in ("vehicle-name", "battery-kwh", "consumption", "charge-kw", "connector"):
        assert f'id="{control}"' in page
    assert '<option value="custom">Add custom vehicle</option>' in page
    assert 'value="catalog" disabled' in page
    assert 'customDetails.hidden=!custom' in page
    assert 'input.disabled=!custom' in page


def test_form_does_not_claim_to_recalculate_demo_route():
    page = PAGE.read_text(encoding="utf-8")
    assert "these inputs do not recalculate the example timeline or map" in page
    assert "example itinerary unchanged" in page
    assert 'role="status"' in page