$ErrorActionPreference = 'Stop'
$modulePath = 'src/planning/planning_summary.py'
$testPath = 'tests/test_planning_summary.py'
$newTestPath = 'tests/test_no_charge_needed_summary.py'
foreach ($path in @($modulePath, $testPath, '.venv/Scripts/python.exe')) {
    if (-not (Test-Path $path)) { throw "Missing $path. Run from the project root after the planning-summary step." }
}
if (Test-Path $newTestPath) { throw "Refusing to overwrite $newTestPath" }
$module = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $modulePath))
$tests = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $testPath))
$oldCategory = '"energy_feasible_if_charging_available": [],'
$oldBranch = @'
        else:
            categories["energy_feasible_if_charging_available"].append(candidate)
'@
$newBranch = @'
        elif candidate["charge_for_next_leg"] is not None and candidate["charge_for_next_leg"]["charge_needed"]:
            categories["charging_needed_if_usable"].append(candidate)
        else:
            categories["no_charging_needed"].append(candidate)
'@
$oldFixture = '"station_reachable_with_reserve": True, "next_leg_possible_from_full": True},'
$newFixture = '"station_reachable_with_reserve": True, "next_leg_possible_from_full": True, "charge_for_next_leg": {"charge_needed": True}},'
$oldAssertion = 'result["categories"]["energy_feasible_if_charging_available"]'
$newAssertion = 'result["categories"]["charging_needed_if_usable"]'
if (([regex]::Matches($module, [regex]::Escape($oldCategory))).Count -ne 1 -or
    ([regex]::Matches($module, [regex]::Escape($oldBranch))).Count -ne 1 -or
    ([regex]::Matches($tests, [regex]::Escape($oldFixture))).Count -ne 1 -or
    ([regex]::Matches($tests, [regex]::Escape($oldAssertion))).Count -ne 1) {
    throw 'Expected source/test text differs from the prior bundle. No files changed.'
}
$module = $module.Replace($oldCategory, '"no_charging_needed": [],' + "`n" + '        "charging_needed_if_usable": [],').Replace($oldBranch, $newBranch)
$tests = $tests.Replace($oldFixture, $newFixture).Replace($oldAssertion, $newAssertion)
$newTests = @'
"""Regression tests for clear, honest labels when a charging stop is optional."""

import src.planning.planning_summary as summary
from src.planning.vehicle_profile import VehicleProfile


def test_live_smoke_scenario_does_not_claim_charge_needed(monkeypatch):
    profile = VehicleProfile("Illustrative EV", 75, 30, 150, "CCS", 10)
    station = {"id": 189344, "name": "Example site"}

    def fake_assessment(*args, **kwargs):
        return {
            "route_distance_miles": 14.15452507357035,
            "discovered_count": 28,
            "reported_connector_match_count": 27,
            "distinct_reported_address_count": 21,
            "assessments": [{"station": station, "detour": {
                "start_to_station_distance_miles": 1.3239555993000873,
                "station_to_end_distance_miles": 12.826903384236061,
            }}],
        }

    monkeypatch.setattr(summary, "assess_candidates", fake_assessment)
    result = summary.plan_candidate_summary(profile, 80, 39.7, -105.0, 39.8, -104.9, max_detour_checks=1)
    assert result["not_assessed_count"] == 20
    assert len(result["categories"]["no_charging_needed"]) == 1
    assert result["categories"]["charging_needed_if_usable"] == []
    candidate = result["categories"]["no_charging_needed"][0]
    assert candidate["charge_for_next_leg"]["charge_needed"] is False
    assert candidate["charge_for_next_leg"]["energy_to_add_kwh"] == 0


def test_empty_summary_keeps_both_clear_labels(monkeypatch):
    monkeypatch.setattr(summary, "assess_candidates", lambda *a, **k: {
        "route_distance_miles": 1, "discovered_count": 0,
        "reported_connector_match_count": 0,
        "distinct_reported_address_count": 0, "assessments": [],
    })
    monkeypatch.setattr(summary, "assess_candidate_reachability", lambda *a: {"candidates": []})
    result = summary.plan_candidate_summary(
        VehicleProfile("Test", 75, 30, 150, "CCS"), 80, 39.7, -105, 39.8, -104.9
    )
    assert result["categories"]["no_charging_needed"] == []
    assert result["categories"]["charging_needed_if_usable"] == []
'@
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $modulePath), $module, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $testPath), $tests, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $newTestPath), $newTests, $utf8)
Write-Host "Updated $modulePath and $testPath; created $newTestPath"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. Optional charging stops now have an explicit category.'