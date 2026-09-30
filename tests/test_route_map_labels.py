from pathlib import Path

PAGE = Path("web/trip_planner_visual_prototype.html")


def test_direct_route_metrics_not_demo_values():
    text = PAGE.read_text(encoding="utf-8-sig")

    assert "Direct road distance" in text
    assert "Direct driving time" in text
    assert "342 mi" not in text
    assert 'id="from" value=' not in text
    assert 'id="to" value=' not in text
    assert 'fetch("/api/route"' in text
    assert "const hours = Math.floor(totalMinutes / 60);" in text
    assert "${hours} hr ${minutes} min" in text


def test_route_timeline_handles_endpoints_and_reset():
    text = PAGE.read_text(encoding="utf-8-sig")

    assert 'id="route-timeline"' in text
    assert "function showEndpoints(selected)" in text
    assert "selected.from.label" in text
    assert "selected.to.label" in text
    assert "Selected origin on the direct road route." in text
    assert "Selected destination on the direct road route." in text
    assert 'Charging stop ${stopNumber}' in text
    assert "function stationAddress(candidate)" in text
    assert '"Choose your starting place"' in text
    assert '"Choose your destination"' in text
    assert 'el("reset").addEventListener("click"' in text
    assert "timeline.replaceChildren();" in text