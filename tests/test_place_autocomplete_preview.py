from pathlib import Path


def test_autocomplete_wired_to_existing_fields():
    html = Path("web/trip_planner_visual_prototype.html").read_text(encoding="utf-8")
    js = Path("web/place_autocomplete.js").read_text(encoding="utf-8")
    assert '<script src="place_autocomplete.js"></script>' in html
    assert 'const fields = ["from", "to"]' in js
    assert 'role", "combobox"' in js
    assert 'role", "listbox"' in js
    assert 'aria-activedescendant' in js


def test_search_is_debounced_and_selected_places_store_coordinates():
    js = Path("web/place_autocomplete.js").read_text(encoding="utf-8")
    assert 'query.length < 4' in js
    assert '}, 450)' in js
    assert 'nextRequestAt' in js
    assert 'new AbortController()' in js
    assert 'countrycode' in js
    assert 'selectedPlaces[id] = {label: labelFor(feature), latitude: lat, longitude: lon}' in js
    assert 'textContent = labelFor(feature)' in js
    assert 'innerHTML' not in js