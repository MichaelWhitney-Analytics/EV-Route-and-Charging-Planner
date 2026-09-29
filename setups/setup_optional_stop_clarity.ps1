$ErrorActionPreference = 'Stop'
$reportPath = 'src/planning/planning_report.py'
$testPath = 'tests/test_planning_report.py'
$newPath = 'tests/test_optional_stop_presentation.py'
foreach ($path in @($reportPath, $testPath, '.venv/Scripts/python.exe')) {
    if (-not (Test-Path $path)) { throw "Missing $path. Run from the project root after the readable-report milestone." }
}
if (Test-Path $newPath) { throw "Refusing to overwrite $newPath" }
$report = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $reportPath)).Replace("`r`n", "`n")
$tests = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $testPath)).Replace("`r`n", "`n")
$oldEnergy = '    energy_text = f"; estimated energy to add {added:.1f} kWh" if isinstance(added, (int, float)) else ""'
$newEnergy = '    energy_text = f"; estimated energy to add {added:.1f} kWh" if isinstance(added, (int, float)) and added > 0 else ""'
$oldLabel = '("no_charging_needed", "No charging needed for the next leg under these assumptions"),'
$newLabel = '("no_charging_needed", "Charging not required for this assessed route under these assumptions; not a suggested stop"),'
$oldAssertion = '    assert "0.0 kWh" in report'
$newAssertion = '    assert "0.0 kWh" not in report'
foreach ($check in @(@($report, $oldEnergy), @($report, $oldLabel), @($tests, $oldAssertion))) {
    if (([regex]::Matches($check[0], [regex]::Escape($check[1]))).Count -ne 1) {
        throw "Expected report/test source differs at: $($check[1]). No files changed."
    }
}
$report = $report.Replace($oldEnergy, $newEnergy).Replace($oldLabel, $newLabel)
$tests = $tests.Replace($oldAssertion, $newAssertion)
$tests = $tests.Replace('assert "No charging needed" in report', 'assert "Charging not required" in report')
$newTests = @'
from src.planning.planning_report import format_planning_report


def test_optional_site_is_not_presented_as_a_stop():
    summary = {
        "vehicle_name": "Illustrative EV", "start_percent": 80.0,
        "route_distance_miles": 14.2, "discovered_record_count": 28,
        "reported_connector_match_record_count": 27,
        "distinct_reported_address_count": 21,
        "road_detours_assessed_count": 1, "not_assessed_count": 20,
        "categories": {
            "no_charging_needed": [{
                "station": {"id": 189344, "name": "Example site"},
                "arrival_estimate": {"estimated_arrival_percent": 79.4704},
                "charge_for_next_leg": {"energy_to_add_kwh": 0.0},
            }],
            "charging_needed_if_usable": [],
            "unreachable_with_reserve": [],
            "next_leg_exceeds_full_battery_with_reserve": [],
        },
        "disclaimer": "Exploratory only. Trip completion is unverified.",
    }
    report = format_planning_report(summary)
    assert "Charging not required for this assessed route" in report
    assert "not a suggested stop" in report
    assert "0.0 kWh" not in report
    assert "Not checked: 20" in report
    assert "Trip completion is unverified" in report
'@
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $reportPath), $report, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $testPath), $tests, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $newPath), $newTests, $utf8)
Write-Host "Updated $reportPath and $testPath; created $newPath"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. Zero-charge sites are explicitly not suggested stops.'