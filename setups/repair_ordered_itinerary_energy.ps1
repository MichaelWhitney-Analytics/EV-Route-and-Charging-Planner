$ErrorActionPreference = 'Stop'
$modulePath = 'src/planning/ordered_itinerary.py'
$testPath = 'tests/test_ordered_itinerary.py'
$setupPath = 'setups/setup_ordered_itinerary_energy.ps1'
foreach ($path in @($modulePath, $testPath, $setupPath, '.venv/Scripts/python.exe')) {
    if (-not (Test-Path $path)) { throw "Missing $path. Run from the project root after the itinerary setup." }
}
$module = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $modulePath))
$tests = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $testPath))
$setup = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $setupPath))
$old = 'profile.arrival_reserve_percent'
$new = 'profile.minimum_arrival_percent'
$assertion = '    assert result["total_road_miles"] == 100'
$extraAssertion = $assertion + "`n" + '    assert result["arrival_reserve_percent"] == 10'
if (([regex]::Matches($module, [regex]::Escape($old))).Count -ne 1 -or
    ([regex]::Matches($setup, [regex]::Escape($old))).Count -ne 1 -or
    ([regex]::Matches($tests, [regex]::Escape($assertion))).Count -ne 1 -or
    ([regex]::Matches($setup, [regex]::Escape($assertion))).Count -ne 1) {
    throw 'Expected original itinerary files differ. Nothing changed.'
}
$module = $module.Replace($old, $new)
$setup = $setup.Replace($old, $new)
$tests = $tests.Replace("`r`n", "`n").Replace($assertion, $extraAssertion)
$setup = $setup.Replace("`r`n", "`n").Replace($assertion, $extraAssertion)
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $modulePath), $module, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $testPath), $tests, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $setupPath), $setup, $utf8)
Write-Host 'Corrected module, regression test, and original setup script.'
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'All offline tests passed. No automatic stop selection or charger verification is claimed.'