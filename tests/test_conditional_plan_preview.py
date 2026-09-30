from pathlib import Path


def test_route_uses_numbered_charging_stops_and_red_pin_markers():
    text = Path(
        "web/trip_planner_visual_prototype.html"
    ).read_text(encoding="utf-8-sig")

    assert "<h2>Route</h2>" in text
    assert 'id="route-kind"' in text
    assert 'Charging stop ${stopNumber}' in text
    assert "function stationAddress(candidate)" in text
    assert "function chargingPin(stopNumber)" in text
    assert 'className: "charging-pin"' in text
    assert 'background:#cf3f38' in text
    assert "L.marker(" in text
    assert "icon: chargingPin(stopNumber)" in text
    assert "Math.floor(site.arrival_percent)" in text
    assert "destination.arrival_percent" in text
    assert "Blue: direct road route. Red pins" in text
    assert 'id="estimate-stops"' not in text


def test_verbose_charging_disclaimer_is_not_a_large_result_panel():
    text = Path(
        "web/trip_planner_visual_prototype.html"
    ).read_text(encoding="utf-8-sig")

    assert 'id="charging-note" class="charging-note"' in text
    assert "Orange markers show reported station locations" not in text
    assert "suggested charging stop among sampled candidates" not in text
    assert "Exploratory conditional graph:" not in text
