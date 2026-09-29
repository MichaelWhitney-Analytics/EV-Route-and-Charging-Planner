from pathlib import Path


PAGE = Path("web/trip_planner_visual_prototype.html")


def test_real_route_labels_not_demo_labels():
    html = PAGE.read_text(encoding="utf-8")
    assert "Direct route only" in html
    assert "Route endpoints" in html
    assert "Illustrative only</span>" not in html
    assert "Example order</span>" not in html
    assert "Charging stops not planned" in html
    assert "Planned charge stops" not in html


def test_endpoint_details_update_and_reset():
    html = PAGE.read_text(encoding="utf-8")
    assert 'id="from-detail"' in html and 'id="to-detail"' in html
    assert 'getElementById("from-detail").textContent="Selected origin' in html
    assert 'getElementById("to-detail").textContent="Selected destination' in html
    assert 'getElementById("from-detail").textContent="Select a suggestion' in html
    assert 'getElementById("to-detail").textContent="Select a suggestion' in html