$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'src/planning/planning_summary.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the EV-Route-and-Charging-Planner project root after the planning-summary milestone.'
}
$files = @{
    'web/planning-preview.html' = @'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EV route check | Planning preview</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, -apple-system, Segoe UI, sans-serif; background: #f3f6f9; color: #162536; }
    * { box-sizing: border-box; }
    body { margin: 0; line-height: 1.5; }
    main { max-width: 1020px; margin: auto; padding: 2rem 1rem 4rem; }
    header { padding: 1.3rem 0; border-bottom: 1px solid #cfdae3; }
    h1 { font-size: clamp(1.65rem, 4vw, 2.6rem); line-height: 1.15; margin: .4rem 0; }
    h2 { font-size: 1.2rem; margin: 0 0 .65rem; }
    p { margin: .4rem 0 1rem; }
    .eyebrow { color: #345b74; font-size: .86rem; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
    .muted { color: #415366; }
    .notice { background: #fff4de; border-left: 4px solid #aa6800; padding: .8rem 1rem; border-radius: .3rem; }
    .panel { background: white; border: 1px solid #d5e0e9; border-radius: .8rem; padding: 1.3rem; margin-top: 1rem; box-shadow: 0 3px 18px rgba(18, 43, 66, .04); }
    textarea { display: block; width: 100%; min-height: 10rem; resize: vertical; padding: .8rem; border-radius: .4rem; border: 1px solid #73869b; font: .9rem/1.5 ui-monospace, Consolas, monospace; }
    button { margin-top: .75rem; padding: .7rem 1.1rem; border: 0; border-radius: .4rem; background: #064c72; color: white; font: inherit; font-weight: 700; cursor: pointer; }
    button:hover { background: #073c59; }
    button:focus-visible, textarea:focus-visible { outline: 3px solid #dc8d00; outline-offset: 3px; }
    .error { color: #a0172b; font-weight: 700; }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .7rem; margin-top: .8rem; }
    .stat { background: #f2f7fa; border-radius: .45rem; padding: .8rem; }
    .stat strong { display: block; font-size: 1.35rem; }
    .stat span { color: #415366; }
    .site { border-top: 1px solid #dae3eb; padding: 1rem 0 .2rem; }
    .site h3 { margin: 0; font-size: 1rem; }
    .tag { display: inline-block; background: #e9f1f7; padding: .1rem .5rem; border-radius: 100px; font-weight: 700; font-size: .85rem; }
    .empty { background: #f2f7fa; border-radius: .4rem; padding: .8rem; }
    [hidden] { display: none !important; }
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">Planning preview</div>
      <h1>Understand your route check</h1>
      <p class="muted">Explore the planner's results without mistaking a listed site for a confirmed charging stop.</p>
    </header>
    <section class="panel" aria-labelledby="input-title">
      <h2 id="input-title">View a planning result</h2>
      <p>Paste JSON from <code>python -m src.planning.planning_summary ... --format json</code>. This page does not contact route or charger services, and does not store your input.</p>
      <label for="json-input">Planning summary JSON</label>
      <textarea id="json-input" spellcheck="false" placeholder="Paste the complete JSON result here"></textarea>
      <button type="button" id="show-result">Show result</button>
      <p id="error" class="error" role="alert" hidden></p>
    </section>
    <section class="panel" id="result" aria-labelledby="result-title" hidden>
      <h2 id="result-title">Route overview</h2>
      <p class="notice">Exploratory estimate, not a reservation, charger recommendation, or trip guarantee.</p>
      <p id="vehicle"></p>
      <div id="stats" class="stats"></div>
      <p id="unchecked" class="muted"></p>
      <h2>Assessed sites</h2>
      <p class="muted">Grouped by energy outcome, not ranked. A site that needs no charging is not a suggested stop.</p>
      <div id="sites"></div>
      <h2>Limitations</h2>
      <p id="limitations"></p>
    </section>
  </main>
  <script>
    "use strict";
    const labels = [
      ["no_charging_needed", "Charging not required here; not a suggested stop"],
      ["charging_needed_if_usable", "Charging needed; charger usability unverified"],
      ["unreachable_with_reserve", "Site not reachable with reserve"],
      ["next_leg_exceeds_full_battery_with_reserve", "Next leg exceeds a full battery with reserve"]
    ];
    const byId = id => document.getElementById(id);
    function finiteNumber(value, label) {
      if (typeof value !== "number" || !Number.isFinite(value) || value < 0) throw new Error(`Invalid ${label} in planning result.`);
      return value;
    }
    function text(value, fallback = "Not reported") {
      return value === null || value === undefined || String(value).trim() === "" ? fallback : String(value);
    }
    function stat(label, value) {
      const box = document.createElement("div");
      box.className = "stat";
      const strong = document.createElement("strong");
      strong.textContent = value;
      const caption = document.createElement("span");
      caption.textContent = label;
      box.append(strong, caption);
      byId("stats").append(box);
    }
    function render(data) {
      if (!data || typeof data !== "object" || !data.categories || typeof data.categories !== "object") throw new Error("This is not a planning-summary JSON result.");
      const routeMiles = finiteNumber(data.route_distance_miles, "route distance");
      const start = finiteNumber(data.start_percent, "starting charge");
      if (start > 100) throw new Error("Invalid starting charge in planning result.");
      const checked = finiteNumber(data.road_detours_assessed_count, "checked-site count");
      const unchecked = finiteNumber(data.not_assessed_count, "unchecked-site count");
      const groups = labels.map(([key, label]) => {
        if (!Array.isArray(data.categories[key])) throw new Error(`Missing ${key} category in planning result.`);
        return [data.categories[key], label];
      });
      if (groups.reduce((total, [items]) => total + items.length, 0) !== checked) throw new Error("Checked-site count does not match the listed results.");
      byId("stats").replaceChildren();
      byId("sites").replaceChildren();
      byId("vehicle").textContent = `${text(data.vehicle_name, "Unnamed vehicle")} | Starting charge ${start.toFixed(1)}%`;
      stat("Direct road route", `${routeMiles.toFixed(1)} mi`);
      stat("Sites checked", String(checked));
      stat("Sites not checked", String(unchecked));
      stat("Reported connector matches", String(finiteNumber(data.reported_connector_match_record_count, "connector-match count")));
      byId("unchecked").textContent = text(data.not_assessed_note, "Unchecked sites have not received road-detour or energy screening.");
      let displayed = 0;
      for (const [items, label] of groups) {
        for (const item of items) {
          if (!item || !item.station || typeof item.station !== "object") throw new Error("A listed site is missing its station record.");
          const card = document.createElement("article");
          card.className = "site";
          const title = document.createElement("h3");
          title.textContent = text(item.station.name, "Unnamed site");
          const place = document.createElement("p");
          place.className = "muted";
          place.textContent = [item.station.address, item.station.city, item.station.state].filter(Boolean).map(value => text(value)).join(", ") || "Address not reported";
          const status = document.createElement("p");
          status.className = "tag";
          status.textContent = label;
          card.append(title, place, status);
          const arrival = item.arrival_estimate && item.arrival_estimate.estimated_arrival_percent;
          if (typeof arrival === "number" && Number.isFinite(arrival)) {
            const detail = document.createElement("p");
            detail.textContent = `Estimated arrival charge: ${arrival.toFixed(1)}%`;
            card.append(detail);
          }
          const add = item.charge_for_next_leg && item.charge_for_next_leg.energy_to_add_kwh;
          if (typeof add === "number" && Number.isFinite(add) && add > 0) {
            const detail = document.createElement("p");
            detail.textContent = `Estimated energy to add: ${add.toFixed(1)} kWh`;
            card.append(detail);
          }
          byId("sites").append(card);
          displayed++;
        }
      }
      if (!displayed) {
        const empty = document.createElement("p");
        empty.className = "empty";
        empty.textContent = "No sites received an energy assessment. This is not evidence that no stations exist.";
        byId("sites").append(empty);
      }
      byId("limitations").textContent = text(data.disclaimer, "Charger access and trip completion have not been verified.");
      byId("result").hidden = false;
    }
    byId("show-result").addEventListener("click", () => {
      byId("error").hidden = true;
      byId("result").hidden = true;
      try { render(JSON.parse(byId("json-input").value)); }
      catch (error) {
        byId("stats").replaceChildren();
        byId("sites").replaceChildren();
        byId("error").textContent = error instanceof SyntaxError ? "Paste a valid JSON planning summary, then try again." : error.message;
        byId("error").hidden = false;
      }
    });
  </script>
</body>
</html>
'@
    'tests/test_web_planning_preview.py' = @'
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
'@
}
foreach ($path in $files.Keys) {
    if (Test-Path $path) { throw "Refusing to overwrite existing file: $path" }
}
$utf8 = [System.Text.UTF8Encoding]::new($false)
foreach ($path in $files.Keys) {
    New-Item -ItemType Directory -Force -Path (Split-Path $path -Parent) | Out-Null
    [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $path), $files[$path], $utf8)
    Write-Host "Created $path"
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. Open web/planning-preview.html locally and paste a --format json result to inspect the preview.'