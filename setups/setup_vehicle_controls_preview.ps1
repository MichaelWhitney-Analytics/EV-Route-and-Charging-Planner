$ErrorActionPreference = 'Stop'
$target = 'web/trip_planner_visual_prototype.html'
$testPath = 'tests/test_vehicle_controls_preview.py'
if (-not (Test-Path $target) -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Save trip_planner_visual_prototype.html inside web/ and run from the project root.'
}
if (Test-Path $testPath) { throw "Refusing to overwrite $testPath" }
$html = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $target))
$cssAnchor = '</style>'
$fieldsAnchor = '<form id="trip-form" class="trip-fields">'
$scriptAnchor = 'document.getElementById("trip-form").addEventListener("submit",event=>'
foreach ($anchor in @($cssAnchor, $fieldsAnchor, $scriptAnchor)) {
    if (([regex]::Matches($html, [regex]::Escape($anchor))).Count -ne 1) {
        throw "Prototype differs at $anchor. No files changed."
    }
}
$css = @'
.vehicle-card{border:1px solid #dae7ed;border-radius:12px;background:#f8fbfc;padding:15px;margin:18px 0}.vehicle-card h2{font-size:1rem;margin:0 0 5px}.vehicle-card p{font-size:.76rem;color:#617583;margin:0 0 12px}.vehicle-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.vehicle-grid label{font-size:.72rem;color:#52687a;font-weight:750}.vehicle-grid input,.vehicle-grid select{display:block;width:100%;margin-top:5px;padding:9px;border:1px solid #bdced9;border-radius:7px;background:white;color:#183144}.vehicle-grid .wide{grid-column:1/-1}.vehicle-summary{font-size:.75rem;color:#2d6077;margin-top:11px}.vehicle-card .vehicle-warning{margin-top:10px;margin-bottom:0;color:#835b1d}
'@
$fields = @'
<section class="vehicle-card" aria-labelledby="vehicle-title"><h2 id="vehicle-title">Your electric vehicle</h2><p>Select a profile before planning a trip. No model specifications are prefilled or assumed.</p><div class="vehicle-grid"><label class="wide" for="vehicle-mode">Vehicle choice<select id="vehicle-mode"><option value="custom">Custom battery-electric vehicle</option><option value="catalog" disabled>Model catalog (not connected yet)</option></select></label><label class="wide" for="vehicle-name">Vehicle name<input id="vehicle-name" type="text" placeholder="e.g., My EV" maxlength="80" autocomplete="off"></label><label for="battery-kwh">Usable battery (kWh)<input id="battery-kwh" type="number" min="0.1" step="any" placeholder="Enter value"></label><label for="consumption">Energy use (kWh / 100 mi)<input id="consumption" type="number" min="0.1" step="any" placeholder="Enter value"></label><label for="charge-kw">Max charging power (kW)<input id="charge-kw" type="number" min="0.1" step="any" placeholder="Enter value"></label><label for="connector">Connector<select id="connector"><option value="">Choose connector</option><option value="CCS">CCS</option><option value="NACS">NACS</option><option value="CHADEMO">CHAdeMO</option></select></label><label for="start-percent">Start battery (%)<input id="start-percent" type="number" min="0" max="100" step="any" placeholder="Enter value"></label><label for="reserve-percent">Arrival reserve (%)<input id="reserve-percent" type="number" min="0" max="100" step="any" placeholder="Enter value"></label></div><div class="vehicle-summary" id="vehicle-summary" role="status">Custom vehicle details have not been entered.</div><p class="vehicle-warning">This is an input preview. Editing a profile does not recalculate the example timeline or map.</p></section>
'@
$js = @'
const vehicleInputs=["vehicle-name","battery-kwh","consumption","charge-kw","connector","start-percent","reserve-percent"];
function updateVehicleSummary(){const name=document.getElementById("vehicle-name").value.trim(),values=vehicleInputs.slice(1).map(id=>document.getElementById(id).value.trim());document.getElementById("vehicle-summary").textContent=name&&values.every(Boolean)?`${name} · custom BEV · ${document.getElementById("connector").value} · example itinerary unchanged`:"Custom vehicle details have not been fully entered. Example itinerary unchanged."}
for(const id of vehicleInputs){document.getElementById(id).addEventListener("input",updateVehicleSummary);document.getElementById(id).addEventListener("change",updateVehicleSummary)}
'@
$html = $html.Replace($cssAnchor, $css + "`n" + $cssAnchor)
$html = $html.Replace($fieldsAnchor, $fields + "`n" + $fieldsAnchor)
$html = $html.Replace($scriptAnchor, $js + "`n" + $scriptAnchor)
$tests = @'
from pathlib import Path


PAGE = Path("web/trip_planner_visual_prototype.html")


def test_custom_bev_controls_are_present_without_fake_model_specs():
    page = PAGE.read_text(encoding="utf-8")
    for control in ("vehicle-mode", "vehicle-name", "battery-kwh", "consumption", "charge-kw", "connector", "start-percent", "reserve-percent"):
        assert f'id="{control}"' in page
    assert 'value="catalog" disabled' in page
    assert "No model specifications are prefilled or assumed" in page


def test_editing_vehicle_does_not_pretend_to_recompute_trip():
    page = PAGE.read_text(encoding="utf-8")
    assert "does not recalculate the example timeline or map" in page
    assert "example itinerary unchanged" in page
    assert 'role="status"' in page
'@
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $target), $html, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $testPath), $tests, $utf8)
Write-Host "Updated $target; created $testPath"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline checks passed. Open the prototype to inspect the custom EV form.'