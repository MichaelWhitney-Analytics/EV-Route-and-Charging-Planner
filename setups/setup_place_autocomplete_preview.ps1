$ErrorActionPreference = 'Stop'
$page = 'web/trip_planner_visual_prototype.html'
$script = 'web/place_autocomplete.js'
$tests = 'tests/test_place_autocomplete_preview.py'
if (-not (Test-Path $page) -or -not (Test-Path '.venv/Scripts/python.exe')) { throw 'Run from the project root after saving the updated vehicle-controls prototype in web/.' }
foreach ($path in @($script, $tests)) { if (Test-Path $path) { throw "Refusing to overwrite $path" } }
$html = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $page))
$anchor = '</body>'
if (([regex]::Matches($html, [regex]::Escape($anchor))).Count -ne 1 -or -not $html.Contains('id="vehicle-name"')) { throw 'Expected vehicle prototype differs. No files changed.' }
$html = $html.Replace($anchor, '<script src="place_autocomplete.js"></script>' + "`n" + $anchor)
$js = @'
"use strict";
// Limited demo use of Photon: do not use the public server as a production SLA.
(() => {
  const fields = ["from", "to"];
  const cache = new Map();
  const selectedPlaces = {from: null, to: null};
  let nextRequestAt = 0;
  const MAX_CACHE = 30;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  function labelFor(feature) {
    const p = feature.properties || {};
    const street = [p.housenumber, p.street].filter(Boolean).join(" ");
    return [p.name && p.name !== p.city ? p.name : null, street, p.city || p.name, p.state, p.country].filter(Boolean).join(", ");
  }
  async function suggest(query, signal) {
    const key = query.toLowerCase();
    if (cache.has(key)) return cache.get(key);
    const wait = Math.max(0, nextRequestAt - Date.now());
    nextRequestAt = Date.now() + wait + 1100;
    if (wait) await sleep(wait);
    if (signal.aborted) throw new DOMException("Cancelled", "AbortError");
    const url = new URL("https://photon.komoot.io/api/");
    url.searchParams.set("q", query);
    url.searchParams.set("limit", "8");
    const response = await fetch(url, {signal});
    if (!response.ok) throw new Error("Location search is temporarily unavailable.");
    const data = await response.json();
    const results = (Array.isArray(data.features) ? data.features : [])
      .filter(feature => feature.properties && String(feature.properties.countrycode || "").toUpperCase() === "US"
        && Array.isArray(feature.geometry?.coordinates)
        && feature.geometry.coordinates.length >= 2
        && Number.isFinite(feature.geometry.coordinates[0])
        && Number.isFinite(feature.geometry.coordinates[1]))
      .slice(0, 5);
    cache.set(key, results);
    if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value);
    return results;
  }
  for (const id of fields) {
    const input = document.getElementById(id);
    const box = document.createElement("div");
    box.className = "place-list";
    box.id = `${id}-suggestions`;
    box.setAttribute("role", "listbox");
    box.hidden = true;
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", box.id);
    input.setAttribute("aria-expanded", "false");
    input.parentElement.append(box);
    const status = document.createElement("span");
    status.className = "place-status";
    status.setAttribute("role", "status");
    input.parentElement.append(status);
    let timer, controller, sequence = 0, activeIndex = -1;
    function close() { box.hidden = true; box.replaceChildren(); activeIndex = -1; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); }
    function activate(index) {
      const items = [...box.querySelectorAll('[role="option"]')];
      if (!items.length) return;
      activeIndex = (index + items.length) % items.length;
      items.forEach((item, i) => item.setAttribute("aria-selected", String(i === activeIndex)));
      input.setAttribute("aria-activedescendant", items[activeIndex].id);
    }
    function choose(feature) {
      const [lon, lat] = feature.geometry.coordinates;
      selectedPlaces[id] = {label: labelFor(feature), latitude: lat, longitude: lon};
      input.value = selectedPlaces[id].label;
      status.textContent = `Selected: ${selectedPlaces[id].label}. Coordinates saved for a future route-planning step.`;
      close();
    }
    function show(results) {
      close();
      if (!results.length) { status.textContent = "No matching US places found. Try a more specific city or address."; return; }
      for (const [index, feature] of results.entries()) {
        const option = document.createElement("button");
        option.type = "button";
        option.id = `${id}-suggestion-${index}`;
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        option.textContent = labelFor(feature);
        option.addEventListener("pointerdown", event => event.preventDefault());
        option.addEventListener("click", () => choose(feature));
        box.append(option);
      }
      box.hidden = false;
      input.setAttribute("aria-expanded", "true");
      status.textContent = `${results.length} suggestions. Use arrow keys and Enter to select.`;
    }
    input.addEventListener("input", () => {
      selectedPlaces[id] = null;
      sequence++;
      clearTimeout(timer);
      if (controller) controller.abort();
      close();
      const query = input.value.trim();
      if (query.length < 4) { status.textContent = "Type at least four characters to search US locations."; return; }
      const requestNumber = sequence;
      timer = setTimeout(async () => {
        controller = new AbortController();
        status.textContent = "Searching locations...";
        try {
          const results = await suggest(query, controller.signal);
          if (requestNumber === sequence) show(results);
        } catch (error) {
          if (requestNumber === sequence && error.name !== "AbortError") status.textContent = "Location search unavailable. Check your connection and try again.";
        }
      }, 450);
    });
    input.addEventListener("keydown", event => {
      if (event.key === "Escape") { close(); return; }
      if (box.hidden) return;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault(); activate(activeIndex + (event.key === "ArrowDown" ? 1 : -1));
      } else if (event.key === "Enter" && activeIndex >= 0) {
        event.preventDefault(); box.querySelectorAll('[role="option"]')[activeIndex].click();
      }
    });
    input.addEventListener("blur", () => setTimeout(close, 150));
  }
  window.addEventListener("beforeunload", () => { selectedPlaces.from = null; selectedPlaces.to = null; });
  const style = document.createElement("style");
  style.textContent = `.trip-fields label{position:relative}.place-list{position:absolute;top:100%;left:0;right:0;z-index:20;max-height:240px;overflow:auto;background:white;border:1px solid #bdced9;border-radius:9px;box-shadow:0 12px 28px #15374b22}.place-list button{display:block;width:100%;border:0;border-bottom:1px solid #ebf0f3;padding:11px 13px;text-align:left;background:white;color:#173648;font-size:.85rem}.place-list button:hover,.place-list button[aria-selected="true"]{background:#e5f3f8}.place-status{display:block;font-size:.72rem;color:#527087;margin-top:5px}`;
  document.head.append(style);
  window.routewiseSelectedPlaces = selectedPlaces;
})();
'@
$testContent = @'
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
'@
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $page), $html, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $script), $js, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $tests), $testContent, $utf8)
Write-Host "Updated $page; created $script and $tests"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. Browser-check a typed US city and a street address; public Photon demo availability is not guaranteed.'