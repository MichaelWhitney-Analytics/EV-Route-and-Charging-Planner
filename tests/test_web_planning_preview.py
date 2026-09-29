from html.parser import HTMLParser
from pathlib import Path


PAGE = Path("web/planning-preview.html")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])


def test_preview_has_accessible_input_and_result_regions():
    html = PAGE.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(html)
    assert {"json-input", "show-result", "error", "result", "sites", "limitations"} <= parser.ids
    assert 'role="alert"' in html
    assert 'name="viewport"' in html
    assert "--format json" in html


def test_preview_keeps_remote_content_as_text_and_marks_uncertainty():
    html = PAGE.read_text(encoding="utf-8")
    assert "textContent" in html
    assert "innerHTML" not in html
    assert "not a suggested stop" in html
    assert "not ranked" in html
    assert "not a reservation" in html
    assert "does not store your input" in html