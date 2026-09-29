$ErrorActionPreference = 'Stop'
$cliPath = 'src/planning/planning_summary.py'
$newModule = 'src/planning/planning_report.py'
$newTests = 'tests/test_planning_report.py'
foreach ($path in @($cliPath, '.venv/Scripts/python.exe')) {
    if (-not (Test-Path $path)) { throw "Missing $path. Run from the project root after the previous milestone." }
}
foreach ($path in @($newModule, $newTests)) {
    if (Test-Path $path) { throw "Refusing to overwrite $path" }
}
$source = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $cliPath)).Replace("`r`n", "`n")
$oldImport = 'from src.planning.candidate_reachability import assess_candidate_reachability'
$oldArgument = '    parser.add_argument("--max-checks", type=int, choices=(1, 2, 3), default=2)'
$oldPrint = '    print(json.dumps(result, indent=2))'
foreach ($token in @($oldImport, $oldArgument, $oldPrint)) {
    if (([regex]::Matches($source, [regex]::Escape($token))).Count -ne 1) {
        throw "Expected planning-summary source differs at: $token. No files changed."
    }
}
$source = $source.Replace($oldImport, $oldImport + "`n" + 'from src.planning.planning_report import format_planning_report')
$source = $source.Replace($oldArgument, $oldArgument + "`n" + '    parser.add_argument("--format", choices=("text", "json"), default="text")')
$source = $source.Replace($oldPrint, '    print(format_planning_report(result) if args.format == "text" else json.dumps(result, indent=2))')
$report = @'
"""Human-readable, uncertainty-aware display of a limited EV planning summary."""


def _clean(value: object) -> str:
    """Keep untrusted station labels to one terminal line."""
    text = " ".join(str(value if value is not None else "Unknown").split())
    return text[:100] + ("..." if len(text) > 100 else "")


def _station_line(candidate: dict, label: str) -> str:
    station = candidate["station"]
    name = _clean(station.get("name") or "Unnamed site")
    parts = [station.get("address"), station.get("city"), station.get("state")]
    location = ", ".join(_clean(part) for part in parts if part)
    label_text = f"{name} ({location})" if location else name
    arrival = candidate.get("arrival_estimate", {}).get("estimated_arrival_percent")
    arrival_text = f"; estimated arrival {arrival:.1f}%" if isinstance(arrival, (int, float)) else ""
    charge = candidate.get("charge_for_next_leg")
    added = charge.get("energy_to_add_kwh") if isinstance(charge, dict) else None
    energy_text = f"; estimated energy to add {added:.1f} kWh" if isinstance(added, (int, float)) else ""
    return f"- {label_text} [ID: {_clean(station.get('id'))}]: {label}{arrival_text}{energy_text}"


def format_planning_report(summary: dict) -> str:
    """Render counts and every assessed candidate without claiming recommendations."""
    groups = summary["categories"]
    lines = [
        "EV ROUTE AND CHARGING CHECK",
        "Exploratory estimate - not a charger reservation or a trip guarantee.",
        f"Vehicle: {_clean(summary['vehicle_name'])} | Starting charge: {summary['start_percent']:.1f}%",
        f"Direct driving route: {summary['route_distance_miles']:.1f} miles",
        f"Station records: {summary['discovered_record_count']} found; {summary['reported_connector_match_record_count']} reported connector matches; {summary['distinct_reported_address_count']} distinct reported addresses.",
        f"Road-detour sites checked: {summary['road_detours_assessed_count']} | Not checked: {summary['not_assessed_count']}",
        "Not checked may include sites beyond the check limit or sites without usable coordinates.",
        "",
        "ASSESSED SITES (grouped by outcome, not ranked)",
    ]
    labels = (
        ("no_charging_needed", "No charging needed for the next leg under these assumptions"),
        ("charging_needed_if_usable", "Charging needed for the next leg; charger usability unverified"),
        ("unreachable_with_reserve", "Station not reachable with the configured reserve"),
        ("next_leg_exceeds_full_battery_with_reserve", "Next leg exceeds a full battery with the configured reserve"),
    )
    count = 0
    for key, label in labels:
        for candidate in groups[key]:
            lines.append(_station_line(candidate, label))
            count += 1
    if not count:
        lines.append("No candidate sites received an energy assessment.")
    lines.extend(("", "LIMITATIONS", summary["disclaimer"]))
    return "\n".join(lines)
'@
$tests = @'
from src.planning.planning_report import format_planning_report


def base_summary():
    return {
        "vehicle_name": "Illustrative EV", "start_percent": 80.0,
        "route_distance_miles": 14.1545, "discovered_record_count": 28,
        "reported_connector_match_record_count": 27,
        "distinct_reported_address_count": 21,
        "road_detours_assessed_count": 1, "not_assessed_count": 20,
        "categories": {
            "no_charging_needed": [{
                "station": {"id": 189344, "name": "EMICH VW DCC 2", "address": "350 S Santa Fe Dr", "city": "Denver", "state": "CO"},
                "arrival_estimate": {"estimated_arrival_percent": 79.4704},
                "charge_for_next_leg": {"energy_to_add_kwh": 0.0},
            }],
            "charging_needed_if_usable": [],
            "unreachable_with_reserve": [],
            "next_leg_exceeds_full_battery_with_reserve": [],
        },
        "disclaimer": "Reported connector matches and charger availability are unverified.",
    }


def test_report_explains_optional_stop_and_unchecked_sites():
    report = format_planning_report(base_summary())
    assert "No charging needed" in report
    assert "Not checked: 20" in report
    assert "79.5%" in report
    assert "0.0 kWh" in report
    assert "not ranked" in report
    assert "availability are unverified" in report


def test_report_handles_empty_assessment():
    summary = base_summary()
    summary["categories"]["no_charging_needed"] = []
    report = format_planning_report(summary)
    assert "No candidate sites received an energy assessment" in report


def test_station_name_cannot_insert_fake_report_lines():
    summary = base_summary()
    summary["categories"]["no_charging_needed"][0]["station"]["name"] = "Site\nGUARANTEED CHARGE"
    report = format_planning_report(summary)
    assert "Site GUARANTEED CHARGE" in report
    assert "\nGUARANTEED CHARGE" not in report
'@
$utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $cliPath), $source, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $newModule), $report, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $newTests), $tests, $utf8)
Write-Host "Updated $cliPath; created $newModule and $newTests"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. The CLI defaults to a readable report; --format json preserves machine-readable output.'