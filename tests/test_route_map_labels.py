from pathlib import Path

PAGE = Path("web/trip_planner_visual_prototype.html")

def test_direct_route_metrics_not_demo_values():
    text = PAGE.read_text(encoding="utf-8-sig")
    assert 'Direct road distance' in text
    assert 'Direct driving time' in text
    assert '342 mi' not in text
    assert 'id="from" value=' not in text and 'id="to" value=' not in text
    assert 'fetch("/api/route"' in text
    assert 'const hours = Math.floor(totalMinutes / 60);' in text
    assert '${hours} hr ${minutes} min' in text

def test_endpoint_labels_and_reset():
    text = PAGE.read_text(encoding="utf-8-sig")
    assert 'id="from-detail"' in text and 'id="to-detail"' in text
    assert 'el("from-detail").textContent = "Selected origin' in text
    assert 'el("to-detail").textContent = "Selected destination' in text
    assert 'el("from-detail").textContent = "Select a suggestion' in text
    assert 'el("to-detail").textContent = "Select a suggestion' in text

