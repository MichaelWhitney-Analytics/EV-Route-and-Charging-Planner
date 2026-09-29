from pathlib import Path

def test_direct_only_ui_does_not_suggest_charging_outcomes():
    text = Path("web/trip_planner_visual_prototype.html").read_text(encoding="utf-8-sig")
    assert 'id="plan-result"' not in text
    assert 'id="plan-timeline"' not in text
    assert 'id="conditional-plan"' not in text
    assert 'Charging stops are not calculated' in text
    assert 'Direct driving time' in text
    assert 'textContent' in text
