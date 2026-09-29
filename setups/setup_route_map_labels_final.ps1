$ErrorActionPreference = 'Stop'
$page = 'web/trip_planner_visual_prototype.html'
$testPath = 'tests/test_route_map_labels.py'
if (-not (Test-Path $page) -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the project root after installing the real route map.'
}
if (Test-Path $testPath) { throw "Refusing to overwrite $testPath" }
$html = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $page))
$replacements = [ordered]@{
    '<span>Illustrative only</span>' = '<span>Direct route only</span>'
    '<span>Example order</span>' = '<span>Route endpoints</span>'
    '<span class="detail">Select a suggestion from the From field.</span>' = '<span class="detail" id="from-detail">Select a suggestion from the From field.</span>'
    '<span class="detail">Select a suggestion from the To field.</span>' = '<span class="detail" id="to-detail">Select a suggestion from the To field.</span>'
    'metricCards[2].innerHTML="<strong>0</strong><span>Planned charge stops</span>";' = 'metricCards[2].innerHTML="<strong>--</strong><span>Charging stops not planned</span>";'
    'document.getElementById("from-label").textContent=selected.from.label;' = 'document.getElementById("from-label").textContent=selected.from.label;document.getElementById("from-detail").textContent="Selected origin on the direct road route.";'
    'document.getElementById("to-label").textContent=selected.to.label;' = 'document.getElementById("to-label").textContent=selected.to.label;document.getElementById("to-detail").textContent="Selected destination on the direct road route.";'
    'document.getElementById("from-label").textContent="Choose your starting place";' = 'document.getElementById("from-label").textContent="Choose your starting place";document.getElementById("from-detail").textContent="Select a suggestion from the From field.";'
    'document.getElementById("to-label").textContent="Choose your destination"});' = 'document.getElementById("to-label").textContent="Choose your destination";document.getElementById("to-detail").textContent="Select a suggestion from the To field."});'
}
foreach ($pair in $replacements.GetEnumerator()) {
    if (([regex]::Matches($html, [regex]::Escape($pair.Key))).Count -ne 1) {
        throw "Unexpected page content at: $($pair.Key). No files changed."
    }
}
foreach ($pair in $replacements.GetEnumerator()) {
    $html = $html.Replace($pair.Key, $pair.Value)
}
$tests = @'
from pathlib import Path


PAGE = Path("web/trip_planner_visual_prototype.html")


def test_real_route_labels_not_demo_labels():
    html = PAGE.read_text(encoding="utf-8")
    assert "Direct route only" in html
    assert "Route endpoints" in html
    assert "Illustrative only</span>" not in html
    assert "Example order</span>" not in html
    assert "Charging stops not planned" in html
    assert "Planned charge stops" not in html


def test_endpoint_details_update_and_reset():
    html = PAGE.read_text(encoding="utf-8")
    assert 'id="from-detail"' in html and 'id="to-detail"' in html
    assert 'getElementById("from-detail").textContent="Selected origin' in html
    assert 'getElementById("to-detail").textContent="Selected destination' in html
    assert 'getElementById("from-detail").textContent="Select a suggestion' in html
    assert 'getElementById("to-detail").textContent="Select a suggestion' in html
'@
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $page), $html, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $testPath), $tests, $utf8)
Write-Host "Updated $page; created $testPath"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. Refresh the local page and verify route-only labels.'