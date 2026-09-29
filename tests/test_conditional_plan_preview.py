from html.parser import HTMLParser
from pathlib import Path

PAGE = Path("web/trip_planner_visual_prototype.html")


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
    def handle_starttag(self, tag, attrs):
        value = dict(attrs).get("id")
        if value:
            self.ids.add(value)


def test_optional_conditional_panel_is_distinct_from_direct_map():
    content = PAGE.read_text(encoding="utf-8")
    parser = Elements()
    parser.feed(content)
    assert {"conditional-plan", "conditional-status", "conditional-result",
            "conditional-warning", "conditional-timeline"} <= parser.ids
    assert 'fetch("/api/route"' in content
    assert 'fetch("/api/conditional-plan"' in content
    assert "button.addEventListener(\"click\", async" in content


def test_preview_does_not_claim_verified_charging_or_draw_stops():
    content = PAGE.read_text(encoding="utf-8")
    assert "No charger is verified" in content
    assert "does not prove the trip is impossible" in content
    assert 'item.textContent =' in content
    assert 'timeline.replaceChildren()' in content
    assert "run !== revision" in content
