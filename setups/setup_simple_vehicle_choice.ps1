$ErrorActionPreference = 'Stop'
$page = 'web/trip_planner_visual_prototype.html'
$testPath = 'tests/test_vehicle_controls_preview.py'
foreach ($path in @($page, $testPath, '.venv/Scripts/python.exe')) {
    if (-not (Test-Path $path)) { throw "Missing $path. Run from project root after vehicle and autocomplete previews." }
}
$html = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $page))
$tests = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $testPath))
$sectionPattern = '(?s)<section class="vehicle-card" aria-labelledby="vehicle-title">.*?</section>'
$scriptPattern = '(?s)const vehicleInputs=\["vehicle-name".*?for\(const id of vehicleInputs\)\{.*?addEventListener\("change",updateVehicleSummary\)\}'
if (([regex]::Matches($html, $sectionPattern)).Count -ne 1 -or
    ([regex]::Matches($html, $scriptPattern)).Count -ne 1 -or
    -not $html.Contains('<script src="place_autocomplete.js"></script>') -or
    -not $tests.Contains('test_custom_bev_controls_are_present_without_fake_model_specs')) {
    throw 'Prototype differs from expected version. No files changed.'
}
$section = @'
<section class="vehicle-card" aria-labelledby="vehicle-title"><h2 id="vehicle-title">Your electric vehicle</h2><p>Choose a vehicle, then set the battery level for this trip.</p><div class="vehicle-grid"><label class="wide" for="vehicle-mode">Vehicle choice<select id="vehicle-mode"><option value="" selected>Choose a vehicle</option><option value="catalog" disabled>Model catalog (coming later)</option><option value="custom">Add custom vehicle</option></select></label><label for="start-percent">Start battery (%)<input id="start-percent" type="number" min="0" max="100" step="any" placeholder="Enter %"></label><label for="reserve-percent">Arrival reserve (%)<input id="reserve-percent" type="number" min="0" max="100" step="any" placeholder="Enter %"></label></div><div id="custom-vehicle-details" hidden><p class="vehicle-warning">Only for a custom vehicle: enter your own estimates. No model specifications are assumed.</p><div class="vehicle-grid"><label class="wide" for="vehicle-name">Vehicle name<input id="vehicle-name" type="text" placeholder="e.g., My EV" maxlength="80" autocomplete="off"></label><label for="battery-kwh">Usable battery (kWh)<input id="battery-kwh" type="number" min="0.1" step="any" placeholder="Enter value"></label><label for="consumption">Energy use (kWh / 100 mi)<input id="consumption" type="number" min="0.1" step="any" placeholder="Enter value"></label><label for="charge-kw">Max charging power (kW)<input id="charge-kw" type="number" min="0.1" step="any" placeholder="Enter value"></label><label for="connector">Connector<select id="connector"><option value="">Choose connector</option><option value="CCS">CCS</option><option value="NACS">NACS</option><option value="CHADEMO">CHAdeMO</option></select></label></div></div><div class="vehicle-summary" id="vehicle-summary" role="status">Choose a vehicle to continue. The model catalog is not available yet.</div><p class="vehicle-warning">Design preview: these inputs do not recalculate the example timeline or map.</p></section>
'@
$behavior = @'
const vehicleInputs=["vehicle-name","battery-kwh","consumption","charge-kw","connector","start-percent","reserve-percent"];
const vehicleMode=document.getElementById("vehicle-mode"),customDetails=document.getElementById("custom-vehicle-details"),vehicleSummary=document.getElementById("vehicle-summary");
function updateVehicleSummary(){
  const custom=vehicleMode.value==="custom";
  customDetails.hidden=!custom;
  for(const input of customDetails.querySelectorAll("input,select")) input.disabled=!custom;
  const start=document.getElementById("start-percent"),reserve=document.getElementById("reserve-percent");
  if(!custom){vehicleSummary.textContent="Choose a vehicle to continue. The model catalog is not available yet.";return}
  const name=document.getElementById("vehicle-name").value.trim();
  const complete=["battery-kwh","consumption","charge-kw","connector"].every(id=>document.getElementById(id).value.trim());
  const percentages=start.value.trim()&&reserve.value.trim()&&start.checkValidity()&&reserve.checkValidity();
  vehicleSummary.textContent=name&&complete&&percentages?`${name} · custom BEV · ${document.getElementById("connector").value} · example itinerary unchanged`:"Complete custom vehicle details, starting battery, and reserve before planning. Example itinerary unchanged.";
}
vehicleMode.addEventListener("change",updateVehicleSummary);
for(const id of vehicleInputs){document.getElementById(id).addEventListener("input",updateVehicleSummary);document.getElementById(id).addEventListener("change",updateVehicleSummary)}
updateVehicleSummary();
'@
$html = [regex]::Replace($html, $sectionPattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $section })
$html = [regex]::Replace($html, $scriptPattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $behavior })
$testContent = @'
from pathlib import Path


PAGE = Path("web/trip_planner_visual_prototype.html")


def test_default_vehicle_form_shows_only_three_choices():
    page = PAGE.read_text(encoding="utf-8")
    assert 'id="vehicle-mode"' in page
    assert 'id="start-percent"' in page
    assert 'id="reserve-percent"' in page
    assert 'id="custom-vehicle-details" hidden' in page
    assert '<option value="" selected>Choose a vehicle</option>' in page


def test_advanced_fields_only_in_custom_path_without_fabricated_catalog():
    page = PAGE.read_text(encoding="utf-8")
    for control in ("vehicle-name", "battery-kwh", "consumption", "charge-kw", "connector"):
        assert f'id="{control}"' in page
    assert '<option value="custom">Add custom vehicle</option>' in page
    assert 'value="catalog" disabled' in page
    assert 'customDetails.hidden=!custom' in page
    assert 'input.disabled=!custom' in page


def test_form_does_not_claim_to_recalculate_demo_route():
    page = PAGE.read_text(encoding="utf-8")
    assert "these inputs do not recalculate the example timeline or map" in page
    assert "example itinerary unchanged" in page
    assert 'role="status"' in page
'@
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $page), $html, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $testPath), $testContent, $utf8)
Write-Host "Updated $page and $testPath"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. Inspect the default three-field form and the custom-vehicle reveal in the browser.'